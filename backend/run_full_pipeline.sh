#!/bin/bash
# ============================================================================
# Full Instagram Analysis Pipeline
# ============================================================================
# This script orchestrates the complete data flow:
#   1. Web Scraping     → Instagram data collection
#   2. NLP Analysis     → Sentiment, emotion, distortion detection
#   3. Risk Profiling   → Aggregate signals into case_risk_profiles
#   4. Case Sync        → Sync to dellinnovate.scs_cases with LLM analysis
#
# Pipeline Flow:
#   Instagram → Scraper → text_units_signals (instagram_scraper)
#                            ↓
#                    NLP Analysis
#                            ↓
#               case_risk_profiles (instagram_scraper)
#                            ↓
#               LLM-Enhanced Sync
#                            ↓
#               scs_cases (dellinnovate) → Frontend
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$SCRIPT_DIR"
CASE_SERVICE_DIR="$PROJECT_ROOT/case-service"
LOG_DIR="$PROJECT_ROOT/logs"
ENV_FILE="$PROJECT_ROOT/.env"

# Runtime defaults and effective values.
# Precedence: CLI flag > .env > DEFAULT_*
DEFAULT_INSTAGRAM_DB_NAME="instagram_scraper"
DEFAULT_SCS_DB_NAME="dellinnovate"
DEFAULT_CASE_SERVICE_PORT="8003"
DEFAULT_IMAGE_SERVICE_PORT="8004"

INSTAGRAM_DB_NAME=""
SCS_DB_NAME=""
CASE_SERVICE_PORT=""
IMAGE_SERVICE_PORT=""
SYNC_WITH_LLM=true
SYNC_TIMEOUT_SECONDS=1200
MAX_POSTS_PER_USER=2

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Timestamp for logs
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PIPELINE_LOG="$LOG_DIR/pipeline_$TIMESTAMP.log"

# ============================================================================
# Helper Functions
# ============================================================================

log_step() {
    echo -e "${BLUE}[PIPELINE]${NC} $1" | tee -a "$PIPELINE_LOG"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1" | tee -a "$PIPELINE_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$PIPELINE_LOG"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$PIPELINE_LOG"
}

load_env() {
    if [ -f "$ENV_FILE" ]; then
        log_step "Loading environment from $ENV_FILE"
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    else
        log_warn "No .env found at $ENV_FILE; using script defaults"
    fi

    INSTAGRAM_DB_NAME="${INSTAGRAM_DB_NAME:-${MONGODB_DB_NAME:-$DEFAULT_INSTAGRAM_DB_NAME}}"
    SCS_DB_NAME="${SCS_DB_NAME:-$DEFAULT_SCS_DB_NAME}"
    CASE_SERVICE_PORT="${CASE_SERVICE_PORT:-$DEFAULT_CASE_SERVICE_PORT}"
    IMAGE_SERVICE_PORT="${IMAGE_SERVICE_PORT:-$DEFAULT_IMAGE_SERVICE_PORT}"

    log_step "Source DB (scrape/NLP/features/images): $INSTAGRAM_DB_NAME"
    log_step "Target DB (synced cases): $SCS_DB_NAME"
}

resolve_image_service_port() {
    # Prefer configured port first, then common alternatives.
    local candidates=()
    candidates+=("$IMAGE_SERVICE_PORT")
    candidates+=("8006")
    candidates+=("8004")

    local port
    for port in "${candidates[@]}"; do
        [ -z "$port" ] && continue
        local health
        health=$(curl -fsS "http://localhost:${port}/health" 2>/dev/null || true)
        if echo "$health" | grep -qi 'image-service'; then
            IMAGE_SERVICE_PORT="$port"
            return 0
        fi
    done
    return 1
}

# ============================================================================
# Step 1: Web Scraping (Optional - pass usernames as arguments)
# ============================================================================
run_scraping() {
    log_step "Step 1: Web Scraping"
    log_step "  Writing scraped data into MongoDB database: $INSTAGRAM_DB_NAME"
    
    if [ $# -eq 0 ]; then
        log_warn "No usernames provided. Skipping scraping step."
        log_warn "Usage: $0 [username1] [username2] ..."
        return 0
    fi
    
    cd "$BACKEND_DIR"
    
    for username in "$@"; do
        log_step "  Scraping @$username..."
        MONGODB_DB_NAME="$INSTAGRAM_DB_NAME" python3 -c "
import asyncio
import sys
sys.path.append('$BACKEND_DIR')
from services.scraper_service import ScraperService
from config.database import MongoDB

MAX_POSTS = ${MAX_POSTS_PER_USER}

async def scrape():
    await MongoDB.connect_db()
    scraper = ScraperService()
    try:
        await scraper.scrape_user_profile('$username')
        posts = await scraper.scrape_user_posts('$username', max_posts=MAX_POSTS)
        print(f'Scraped profile + {len(posts)} posts for $username')
    except Exception as e:
        print(f'Error scraping $username: {e}')
    finally:
        await MongoDB.close_db()

asyncio.run(scrape())
" 2>&1 | tee -a "$PIPELINE_LOG"
        
        if [ ${PIPESTATUS[0]} -eq 0 ]; then
            log_success "Scraped @$username"
        else
            log_error "Failed to scrape @$username"
        fi
    done
}

# ============================================================================
# Step 1b: Image Analysis Pipeline (optional - runs if image-service is up)
# ============================================================================
run_image_analysis() {
    log_step "Step 1b: Image Analysis Pipeline"
    log_step "  Reading downloaded images and storing image signals in: $INSTAGRAM_DB_NAME"

    if resolve_image_service_port; then
        log_step "  image-service detected on :${IMAGE_SERVICE_PORT}, triggering /run"

        local image_tmp
        local image_status
        image_tmp=$(mktemp)
        image_status=$(curl -sS -o "$image_tmp" -w "%{http_code}" -X POST "http://localhost:${IMAGE_SERVICE_PORT}/run" \
            -H "Content-Type: application/json" \
            -d '{"overwrite": false, "max_images": 0}')

        cat "$image_tmp" | tee -a "$PIPELINE_LOG"

        if [ "$image_status" = "200" ]; then
            log_success "Image analysis triggered"
        else
            log_warn "image-service /run returned HTTP $image_status; image analysis may not have run"
            rm -f "$image_tmp"
            return 1
        fi

        rm -f "$image_tmp"
    else
        log_warn "image-service not detected on expected ports (configured, 8006, 8004); skipping image analysis step"
    fi
}

# ============================================================================
# Step 2: NLP Analysis - Process all unanalyzed text units
# ============================================================================
run_nlp_analysis() {
    log_step "Step 2: NLP Analysis"
    log_step "  Reading/writing NLP collections in: $INSTAGRAM_DB_NAME"
    
    cd "$BACKEND_DIR"
    
    MONGODB_DB_NAME="$INSTAGRAM_DB_NAME" python3 -c "
import asyncio
import sys
sys.path.append('$BACKEND_DIR')
from analytics.signal_extraction import NLPSignalExtractor
from config.database import MongoDB

async def run_nlp():
    await MongoDB.connect_db()
    extractor = NLPSignalExtractor(db_client=MongoDB.get_db())
    result = await extractor.run_pipeline(export_csv=False)
    print('NLP extraction result:', result)
    await MongoDB.close_db()

asyncio.run(run_nlp())
" 2>&1 | tee -a "$PIPELINE_LOG"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_error "NLP Analysis failed"
        return 1
    fi
    
    log_success "NLP Analysis complete"
}

# ============================================================================
# Step 3: Feature Engineering - Build case risk profiles
# ============================================================================
run_feature_engineering() {
    log_step "Step 3: Feature Engineering & Risk Profiling"
    log_step "  Building case_risk_profiles in: $INSTAGRAM_DB_NAME"
    
    cd "$BACKEND_DIR"
    
    MONGODB_DB_NAME="$INSTAGRAM_DB_NAME" python3 -c "
import asyncio
import sys
sys.path.append('$BACKEND_DIR')
from analytics.feature_engineering import BehavioralFeatureEngineer
from config.database import MongoDB

async def build_profiles():
    await MongoDB.connect_db()
    
    engineer = BehavioralFeatureEngineer()
    
    # Get all case users
    case_users = await engineer.get_case_users()
    print(f'Processing {len(case_users)} case users')
    
    success_count = 0
    for user in case_users:
        try:
            profile = await engineer.compute_risk_profile(user)
            if profile:
                await engineer.store_risk_profile(profile)
                success_count += 1
        except Exception as e:
            print(f'Error processing {user}: {e}')
    
    print(f'Created/updated {success_count} risk profiles in case_risk_profiles')
    await MongoDB.close_db()

asyncio.run(build_profiles())
" 2>&1 | tee -a "$PIPELINE_LOG"

    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_error "Feature engineering failed"
        return 1
    fi
    
    log_success "Risk profiles created in instagram_scraper.case_risk_profiles"
}

# ============================================================================
# Step 4: Sync to SCS Cases with LLM Analysis
# ============================================================================
sync_to_scs() {
    log_step "Step 4: Sync to SCS Cases (dellinnovate cluster)"
    log_step "  Sync source DB: $INSTAGRAM_DB_NAME -> target DB: $SCS_DB_NAME"
    
    # Check if case-service is running
    if ! curl -s "http://localhost:${CASE_SERVICE_PORT}/health" > /dev/null 2>&1; then
        log_warn "Case service not running. Starting it..."
        cd "$CASE_SERVICE_DIR"
        MONGODB_DB_NAME="$INSTAGRAM_DB_NAME" SCS_DB_NAME="$SCS_DB_NAME" python -m uvicorn app.main:app --host 0.0.0.0 --port "$CASE_SERVICE_PORT" &
        sleep 5
    fi
    
    local sync_endpoint
    if [ "$SYNC_WITH_LLM" = true ]; then
        sync_endpoint="sync-risk-profiles-llm"
        log_step "  Calling /cases/${sync_endpoint} (can take several minutes for many profiles)..."
    else
        sync_endpoint="sync-risk-profiles"
        log_step "  Calling /cases/${sync_endpoint} (faster, no LLM generation)..."
    fi

    RESPONSE=$(curl -sS --max-time "$SYNC_TIMEOUT_SECONDS" -X POST "http://localhost:${CASE_SERVICE_PORT}/cases/${sync_endpoint}" \
        -H "X-User-Id: pipeline_script" \
        -H "X-User-Role: Admin" \
        -H "Content-Type: application/json")

    local curl_status=$?
    if [ $curl_status -ne 0 ]; then
        if [ "$SYNC_WITH_LLM" = true ]; then
            log_warn "LLM sync timed out or failed (curl exit $curl_status). Falling back to non-LLM sync..."
            RESPONSE=$(curl -sS --max-time 300 -X POST "http://localhost:${CASE_SERVICE_PORT}/cases/sync-risk-profiles" \
                -H "X-User-Id: pipeline_script" \
                -H "X-User-Role: Admin" \
                -H "Content-Type: application/json")
            curl_status=$?
        fi
        if [ $curl_status -ne 0 ]; then
            log_error "Sync request failed (curl exit $curl_status)"
            return 1
        fi
    fi
    
    echo "$RESPONSE" | tee -a "$PIPELINE_LOG"
    
    # Check for success (accept both compact and pretty JSON spacing)
    if echo "$RESPONSE" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"success"'; then
        if [ "$SYNC_WITH_LLM" = true ]; then
            log_success "Cases synced to dellinnovate.scs_cases with LLM analysis"
        else
            log_success "Cases synced to dellinnovate.scs_cases (non-LLM mode)"
        fi
    else
        log_error "Failed to sync cases"
        return 1
    fi
}

# ============================================================================
# Step 5: Verify Frontend Data
# ============================================================================
verify_data() {
    log_step "Step 5: Verify Frontend Data"
    
    # Get case count from API
    CASES=$(curl -s "http://localhost:${CASE_SERVICE_PORT}/cases" \
        -H "X-User-Id: pipeline_script" \
        -H "X-User-Role: Admin" 2>/dev/null)
    
    CASE_COUNT=$(echo "$CASES" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    
    log_success "Total cases available for frontend: $CASE_COUNT"
    
    # Count cases with LLM data
    LLM_COUNT=$(echo "$CASES" | python3 -c "
import json,sys
data = json.load(sys.stdin)
count = sum(1 for c in data if c.get('ai_explanation_paragraph'))
print(count)
" 2>/dev/null || echo "0")
    
    log_success "Cases with LLM analysis: $LLM_COUNT"
}

# ============================================================================
# Main Pipeline Execution
# ============================================================================
main() {
    echo ""
    echo "=============================================="
    echo "  Instagram Analysis Pipeline"
    echo "  $(date)"
    echo "=============================================="
    echo ""
    
    log_step "Starting full pipeline..."
    log_step "Log file: $PIPELINE_LOG"
    log_step "Max posts per user: $MAX_POSTS_PER_USER"
    echo ""
    
    # Load .env first so CLI flags can override it
    load_env

    # Parse arguments
    SKIP_SCRAPING=false
    SKIP_NLP=false
    SKIP_IMAGE_ANALYSIS=false
    USERNAMES=()
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-scraping)
                SKIP_SCRAPING=true
                shift
                ;;
            --skip-nlp)
                SKIP_NLP=true
                shift
                ;;
            --sync-only)
                SKIP_SCRAPING=true
                SKIP_NLP=true
                SKIP_IMAGE_ANALYSIS=true
                shift
                ;;
            --sync-no-llm)
                SYNC_WITH_LLM=false
                shift
                ;;
            --sync-timeout)
                SYNC_TIMEOUT_SECONDS="$2"
                shift 2
                ;;
            --max-posts)
                MAX_POSTS_PER_USER="$2"
                shift 2
                ;;
            --skip-image-analysis)
                SKIP_IMAGE_ANALYSIS=true
                shift
                ;;
            --instagram-db)
                INSTAGRAM_DB_NAME="$2"
                shift 2
                ;;
            --scs-db)
                SCS_DB_NAME="$2"
                shift 2
                ;;
            *)
                USERNAMES+=("$1")
                shift
                ;;
        esac
    done

    # Run pipeline steps
    if [ "$SKIP_SCRAPING" = false ]; then
        run_scraping "${USERNAMES[@]}"
    else
        log_warn "Skipping scraping step"
    fi

    if [ "$SKIP_IMAGE_ANALYSIS" = false ]; then
        run_image_analysis
    else
        log_warn "Skipping image analysis step"
    fi
    
    if [ "$SKIP_NLP" = false ]; then
        run_nlp_analysis
    else
        log_warn "Skipping NLP analysis step"
    fi
    
    run_feature_engineering
    sync_to_scs
    verify_data
    
    echo ""
    log_success "Pipeline completed successfully!"
    echo ""
    echo "=============================================="
    echo "  Pipeline Summary"
    echo "=============================================="
    echo "  1. Scraped Instagram data"
    echo "  2. NLP signals stored in instagram_scraper.text_units_signals"
    echo "  3. Risk profiles stored in instagram_scraper.case_risk_profiles"
    echo "  4. Cases synced to dellinnovate.scs_cases"
    echo "  5. Frontend data verified"
    echo ""
    echo "  Log file: $PIPELINE_LOG"
    echo "=============================================="
}

# Show usage if --help
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS] [USERNAME...]"
    echo ""
    echo "Options:"
    echo "  --skip-scraping    Skip the web scraping step"
    echo "  --skip-image-analysis  Skip image-service analysis step"
    echo "  --skip-nlp         Skip the NLP analysis step"
    echo "  --sync-only        Only run sync to SCS (skip scraping + NLP)"
    echo "  --sync-no-llm      Use fast sync endpoint without LLM generation"
    echo "  --sync-timeout <s> Max seconds for sync HTTP call (default: 1200)"
    echo "  --max-posts <n>    Max scraped posts per username (default: 2)"
    echo "  --instagram-db <name>  Source DB for scraping/NLP/features/images"
    echo "  --scs-db <name>        Target DB for synced cases"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 chrishemsworth harrystyles    # Full pipeline with scraping"
    echo "  $0 --skip-scraping               # Run image+NLP+sync only"
    echo "  $0 --sync-only                   # Only sync to SCS"
    echo "  $0 --sync-only --sync-no-llm     # Fast sync only"
    echo "  $0 --max-posts 2 jin             # Scrape max 2 posts for @jin"
    echo "  $0 --instagram-db instagram_scraper --scs-db dellinnovate"
    echo ""
    exit 0
fi

# Run main
main "$@"
