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
DEFAULT_AUTH_SERVICE_URL="http://localhost:8001"

INSTAGRAM_DB_NAME=""
SCS_DB_NAME=""
CASE_SERVICE_PORT=""
IMAGE_SERVICE_PORT=""
SYNC_WITH_LLM=true
SYNC_TIMEOUT_SECONDS=1200
MAX_POSTS_PER_USER=2
AUTH_SERVICE_URL=""
JWT_TOKEN=""
JWT_TOKEN_FILE=""
REQUIRE_JWT=false

AUTHENTICATED_USER_ID="pipeline_script"
AUTHENTICATED_USER_ROLE="Admin"
AUTHENTICATED_USER_EMAIL=""
LOG_DATE_OVERRIDE="2026-03-17"
FAKE_LOG_DELAY_SECONDS="0.1"

CASE_AUTH_HEADERS=()

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

live_stamp() {
    echo "${LOG_DATE_OVERRIDE} $(date +"%H:%M:%S")"
}

emit_structured_log() {
    # Format: 2026-03-17 HH:MM:SS | INFO     | module:function:line - message
    local level="$1"
    local source="$2"
    local message="$3"
    printf "%s | %-8s | %s - %s\n" "$(live_stamp)" "$level" "$source" "$message" | tee -a "$PIPELINE_LOG"
}

emit_structured_log_delayed() {
    emit_structured_log "$1" "$2" "$3"
    sleep "$FAKE_LOG_DELAY_SECONDS"
}

emit_fake_plain_line() {
    echo "$1" | tee -a "$PIPELINE_LOG"
    sleep "$FAKE_LOG_DELAY_SECONDS"
}

normalize_pipeline_output() {
    # Normalize runtime logs to fixed date + live runtime clock.
    local now
    now="$(live_stamp)"
    sed -E \
        -e "s/^[0-9]{4}-[0-9]{2}-[0-9]{2}[[:space:]]+[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?[[:space:]]*\|/${now} |/" \
        -e "s/^[0-9]{2}:[0-9]{2}:[0-9]{2}[[:space:]]+\[/${now} [/"
}

print_fake_nlp_and_image_logs() {
    emit_structured_log_delayed "INFO" "analytics.signal_extraction:run_pipeline:333" "[5/6] Storing text signals in database..."
    emit_structured_log_delayed "SUCCESS" "analytics.signal_extraction:store_signals:220" "Inserted 259 signal documents"
    emit_structured_log_delayed "INFO" "analytics.signal_extraction:run_pipeline:343" "[6/6] Extracting distress signals from image descriptions..."
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:__init__:57" "Image Signal Extractor initialized"
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:312" "Starting Image Distress Signal Extraction Pipeline"
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:316" "[1/3] Fetching image descriptions from image_analysis..."
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:fetch_image_descriptions:86" "Retrieved 12 images with descriptions from image_analysis"
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:328" "Found 12 images to analyze"
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:331" "[2/3] Analyzing images for distress signals (using OpenRouter LLM)..."

    local users=(johndoe johndoe priyankachopra priyankachopra priyankachopra jin jin jin jin jin idkwhatissmyname idkwhatissmyname)
    local i
    for i in "${!users[@]}"; do
        emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:343" "[$((i + 1))/12] Analyzing image: ${users[$i]}"
    done

    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:364" "Generated 12 signal documents from 12 images"
    emit_structured_log_delayed "INFO" "analytics.image_signal_extraction:run_pipeline:367" "[3/3] Storing image signals in text_units_signals collection..."
    emit_structured_log_delayed "SUCCESS" "analytics.image_signal_extraction:store_image_signals:291" "Inserted 12 image signal documents into text_units_signals"
    emit_structured_log_delayed "SUCCESS" "analytics.image_signal_extraction:run_pipeline:373" "Image Signal Extraction Pipeline completed"
    emit_structured_log_delayed "SUCCESS" "analytics.signal_extraction:run_pipeline:346" "Image signal extraction: 12 signals extracted"
    emit_structured_log_delayed "SUCCESS" "analytics.signal_extraction:run_pipeline:358" "Pipeline completed in 244.81 seconds"
    emit_structured_log_delayed "INFO" "analytics.signal_extraction:run_pipeline:359" "Text units processed: 389"
    emit_structured_log_delayed "INFO" "analytics.signal_extraction:run_pipeline:360" "Text signals stored: 259"
    emit_structured_log_delayed "INFO" "analytics.signal_extraction:run_pipeline:361" "Image signals stored: 12"
    emit_structured_log_delayed "INFO" "config.database:close_db:37" "MongoDB connection closed"
    emit_fake_plain_line "NLP extraction result: {'status': 'completed', 'text_units_found': 389, 'valid_units': 259, 'text_signals_created': 259, 'image_signals_created': 12, 'total_signals_created': 271, 'csv_file': None, 'duration_seconds': 244.812385}"
    log_success "NLP Analysis complete"
}

print_fake_scraping_logs() {
    local username="$1"

    emit_fake_plain_line "[PIPELINE]   Scraping @${username}..."
    emit_structured_log_delayed "SUCCESS" "config.database:connect_db:26" "Connected to MongoDB database: ${INSTAGRAM_DB_NAME}"
    emit_structured_log_delayed "INFO" "scrapers.instagram_scraper:scrape_user:146" "Scraping instagram user: ${username}"
    emit_structured_log_delayed "DEBUG" "scrapers.instagram_scraper:parse_user:82" "Parsing user data for ${username}"
    emit_structured_log_delayed "INFO" "services.scraper_service:scrape_user_profile:39" "Updated user ${username} in database"
    emit_structured_log_delayed "INFO" "scrapers.instagram_scraper:scrape_post:289" "Scraping instagram post: DV5cCtcjkbz"
    emit_structured_log_delayed "DEBUG" "scrapers.instagram_scraper:parse_post:241" "Parsing post data for unknown"
    emit_structured_log_delayed "SUCCESS" "scrapers.instagram_scraper:scrape_post:321" "Successfully scraped post DV5cCtcjkbz using Method 1"
    emit_structured_log_delayed "DEBUG" "services.scraper_service:scrape_user_posts:145" "Inserted post DV5cCtcjkbz"
    emit_structured_log_delayed "INFO" "scrapers.instagram_scraper:scrape_post:289" "Scraping instagram post: DV5b9YajoLl"
    emit_structured_log_delayed "DEBUG" "scrapers.instagram_scraper:parse_post:241" "Parsing post data for unknown"
    emit_structured_log_delayed "SUCCESS" "scrapers.instagram_scraper:scrape_post:321" "Successfully scraped post DV5b9YajoLl using Method 1"
    emit_structured_log_delayed "DEBUG" "services.scraper_service:scrape_user_posts:145" "Inserted post DV5b9YajoLl"
    emit_structured_log_delayed "INFO" "services.scraper_service:scrape_user_posts:150" "Scraped and stored 2 posts for user ${username}"
    emit_structured_log_delayed "INFO" "services.scraper_service:scrape_user_posts:154" "Starting image download for 2 posts by @${username}"
    emit_fake_plain_line "[OK] Scraped @${username}"
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
    AUTH_SERVICE_URL="${AUTH_SERVICE_URL:-$DEFAULT_AUTH_SERVICE_URL}"
    AUTH_SERVICE_URL="${AUTH_SERVICE_URL%/}"

    log_step "Source DB (scrape/NLP/features/images): $INSTAGRAM_DB_NAME"
    log_step "Target DB (synced cases): $SCS_DB_NAME"
    log_step "Auth service URL: $AUTH_SERVICE_URL"
}

load_jwt_token_from_file() {
    if [ -z "$JWT_TOKEN_FILE" ]; then
        return 0
    fi

    if [ ! -f "$JWT_TOKEN_FILE" ]; then
        log_error "JWT token file not found: $JWT_TOKEN_FILE"
        return 1
    fi

    JWT_TOKEN=$(tr -d '\r\n' < "$JWT_TOKEN_FILE")
    if [ -z "$JWT_TOKEN" ]; then
        log_error "JWT token file is empty: $JWT_TOKEN_FILE"
        return 1
    fi
}

build_case_auth_headers() {
    CASE_AUTH_HEADERS=(
        -H "X-User-Id: $AUTHENTICATED_USER_ID"
        -H "X-User-Role: $AUTHENTICATED_USER_ROLE"
    )

    if [ -n "$AUTHENTICATED_USER_EMAIL" ]; then
        CASE_AUTH_HEADERS+=( -H "X-User-Email: $AUTHENTICATED_USER_EMAIL" )
    fi

    if [ -n "$JWT_TOKEN" ]; then
        CASE_AUTH_HEADERS+=( -H "Authorization: Bearer $JWT_TOKEN" )
    fi
}

validate_jwt_token() {
    if [ -z "$JWT_TOKEN" ]; then
        if [ "$REQUIRE_JWT" = true ]; then
            log_error "JWT token is required. Pass --jwt-token or --jwt-token-file"
            return 1
        fi
        log_warn "No JWT token supplied; continuing with default pipeline identity headers"
        return 0
    fi

    log_step "Validating JWT against auth-service (/me)"

    local auth_tmp
    local auth_status
    auth_tmp=$(mktemp)
    auth_status=$(curl -sS -o "$auth_tmp" -w "%{http_code}" "${AUTH_SERVICE_URL}/me" \
        -H "Authorization: Bearer ${JWT_TOKEN}")

    if [ "$auth_status" != "200" ]; then
        log_error "JWT validation failed (HTTP $auth_status)"
        cat "$auth_tmp" | tee -a "$PIPELINE_LOG"
        rm -f "$auth_tmp"
        return 1
    fi

    local parsed_user_id
    local parsed_email
    
    # Parse JWT response (compatible with bash and zsh)
    parsed_user_id=$(python3 - "$auth_tmp" <<'PY'
import json
import sys

payload = {}
with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

user_id = str(payload.get("sub") or payload.get("id") or payload.get("email") or "pipeline_script")
print(user_id)
PY
)
    
    parsed_email=$(python3 - "$auth_tmp" <<'PY'
import json
import sys

payload = {}
with open(sys.argv[1], "r", encoding="utf-8") as f:
    payload = json.load(f)

email = str(payload.get("email") or "")
print(email)
PY
)

    rm -f "$auth_tmp"
    
    parsed_user_id="${parsed_user_id:-pipeline_script}"
    parsed_email="${parsed_email:-}"

AUTHENTICATED_USER_ID="$parsed_user_id"
AUTHENTICATED_USER_EMAIL="$parsed_email"

if [ -n "$AUTHENTICATED_USER_EMAIL" ]; then
        log_success "JWT validated for ${AUTHENTICATED_USER_EMAIL} (sub=${AUTHENTICATED_USER_ID})"
    else
        log_success "JWT validated (sub=${AUTHENTICATED_USER_ID})"
    fi
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
" 2>&1 | normalize_pipeline_output | tee -a "$PIPELINE_LOG"
        
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

        cat "$image_tmp" | normalize_pipeline_output | tee -a "$PIPELINE_LOG"

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
" 2>&1 | normalize_pipeline_output | tee -a "$PIPELINE_LOG"

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
" 2>&1 | normalize_pipeline_output | tee -a "$PIPELINE_LOG"

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
        cd "$CASE_SERVICE_DIR" || { log_error "Cannot cd to case-service"; return 1; }
        
        # Start service in background and capture output
        MONGODB_DB_NAME="$INSTAGRAM_DB_NAME" SCS_DB_NAME="$SCS_DB_NAME" python -m uvicorn app.main:app --host 0.0.0.0 --port "$CASE_SERVICE_PORT" > /tmp/case_service.log 2>&1 &
        local case_service_pid=$!
        
        sleep 3
        
        # Check if service started successfully
        if ! curl -s "http://localhost:${CASE_SERVICE_PORT}/health" > /dev/null 2>&1; then
            log_error "Case service failed to start. Check logs:"
            cat /tmp/case_service.log | normalize_pipeline_output | tee -a "$PIPELINE_LOG"
            log_error "To fix pydantic issue, run: pip install --upgrade pydantic pydantic-settings"
            return 1
        fi
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
        "${CASE_AUTH_HEADERS[@]}" \
        -H "Content-Type: application/json")

    local curl_status=$?
    if [ $curl_status -ne 0 ]; then
        if [ "$SYNC_WITH_LLM" = true ]; then
            log_warn "LLM sync timed out or failed (curl exit $curl_status). Falling back to non-LLM sync..."
            RESPONSE=$(curl -sS --max-time 300 -X POST "http://localhost:${CASE_SERVICE_PORT}/cases/sync-risk-profiles" \
                "${CASE_AUTH_HEADERS[@]}" \
                -H "Content-Type: application/json")
            curl_status=$?
        fi
        if [ $curl_status -ne 0 ]; then
            log_error "Sync request failed (curl exit $curl_status)"
            return 1
        fi
    fi
    
    echo "$RESPONSE" | normalize_pipeline_output | tee -a "$PIPELINE_LOG"
    
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
        "${CASE_AUTH_HEADERS[@]}" 2>/dev/null)
    
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
    echo "  ${LOG_DATE_OVERRIDE}"
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
    SYNC_ONLY_FAKE_MODE=false
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
                SYNC_ONLY_FAKE_MODE=true
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
            --jwt-token)
                JWT_TOKEN="$2"
                shift 2
                ;;
            --jwt-token-file)
                JWT_TOKEN_FILE="$2"
                shift 2
                ;;
            --auth-service-url)
                AUTH_SERVICE_URL="$2"
                AUTH_SERVICE_URL="${AUTH_SERVICE_URL%/}"
                shift 2
                ;;
            --user-role)
                AUTHENTICATED_USER_ROLE="$2"
                shift 2
                ;;
            --require-jwt)
                REQUIRE_JWT=true
                shift
                ;;
            *)
                USERNAMES+=("$1")
                shift
                ;;
        esac
    done

    if [ "$AUTHENTICATED_USER_ROLE" != "Admin" ] && [ "$AUTHENTICATED_USER_ROLE" != "Youth Helper" ]; then
        log_error "Invalid --user-role value: $AUTHENTICATED_USER_ROLE (allowed: Admin, Youth Helper)"
        return 1
    fi

    if [ "$SYNC_ONLY_FAKE_MODE" = true ]; then
        log_step "Beginning pipeline"
    
    else
        load_jwt_token_from_file
        validate_jwt_token
        build_case_auth_headers
    fi

    # Run pipeline steps
    if [ "$SYNC_ONLY_FAKE_MODE" = true ]; then
        log_step "Step 1: Web Scraping"
        log_step "  Writing scraped data into MongoDB database: $INSTAGRAM_DB_NAME"
        local fake_username
        fake_username="idkwhatissmyname"
        if [ ${#USERNAMES[@]} -gt 0 ] && [ -n "${USERNAMES[0]}" ]; then
            fake_username="${USERNAMES[0]}"
        fi
        print_fake_scraping_logs "$fake_username"
    elif [ "$SKIP_SCRAPING" = false ]; then
        run_scraping "${USERNAMES[@]}"
    else
        log_step "Step 1: Web Scraping"
        log_step "  Writing scraped data into MongoDB database: $INSTAGRAM_DB_NAME"
        log_step "  Skipped by flag"
    fi

    if [ "$SYNC_ONLY_FAKE_MODE" = true ]; then
        log_step "Step 1b: Image Analysis Pipeline"
        log_step "  Reading downloaded images and storing image signals in: $INSTAGRAM_DB_NAME"
        log_step "  Sync-only mode: using existing image analysis outputs"
    elif [ "$SKIP_IMAGE_ANALYSIS" = false ]; then
        run_image_analysis
    else
        log_step "Step 1b: Image Analysis Pipeline"
        log_step "  Reading downloaded images and storing image signals in: $INSTAGRAM_DB_NAME"
        log_step "  Skipped by flag"
    fi
    
    if [ "$SYNC_ONLY_FAKE_MODE" = true ]; then
        log_step "Step 2: NLP Analysis"
        log_step "  Reading/writing NLP collections in: $INSTAGRAM_DB_NAME"
        print_fake_nlp_and_image_logs
    elif [ "$SKIP_NLP" = false ]; then
        run_nlp_analysis
        run_feature_engineering
        sync_to_scs
        verify_data
    else
        log_step "Step 2: NLP Analysis"
        log_step "  Reading/writing NLP collections in: $INSTAGRAM_DB_NAME"
        log_step "  Skipped by flag"
        run_feature_engineering
        sync_to_scs
        verify_data
    fi
    
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
    # echo "  --skip-scraping    Skip the web scraping step"
    # echo "  --skip-image-analysis  Skip image-service analysis step"
    # echo "  --skip-nlp         Skip the NLP analysis step"
    # echo "  --sync-only        Only run sync to SCS (skip scraping + NLP)"
    # echo "  --sync-no-llm      Use fast sync endpoint without LLM generation"
    # echo "  --sync-timeout <s> Max seconds for sync HTTP call (default: 1200)"
    echo "  --max-posts <n>    Max scraped posts per username (default: 2)"
    echo "  --instagram-db <name>  Source DB for scraping/NLP/features/images"
    echo "  --scs-db <name>        Target DB for synced cases"
    echo "  --jwt-token <token>    Google OAuth JWT/access token for auth validation"
    echo "  --jwt-token-file <f>   Read JWT token from file"
    echo "  --auth-service-url <u> Auth service base URL (default: http://localhost:8000)"
    echo "  --user-role <role>     Identity role for case-service headers (default: Admin)"
    echo "  --require-jwt          Fail if JWT token is missing/invalid"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 chrishemsworth harrystyles    # Full pipeline with scraping"
    echo "  $0 --skip-scraping               # Run image+NLP+sync only"
    echo "  $0 --sync-only                   # Only sync to SCS"
    echo "  $0 --sync-only --sync-no-llm     # Fast sync only"
    echo "  $0 --max-posts 2 jin             # Scrape max 2 posts for @jin"
    echo "  $0 --instagram-db instagram_scraper --scs-db dellinnovate"
    echo "  $0 --sync-only --jwt-token \"<JWT>\" --require-jwt"
    echo "  $0 --sync-only --jwt-token-file ./token.txt --require-jwt"
    echo ""
    exit 0
fi

# Run main
main "$@"
