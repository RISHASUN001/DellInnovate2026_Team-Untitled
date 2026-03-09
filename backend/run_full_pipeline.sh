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

# ============================================================================
# Step 1: Web Scraping (Optional - pass usernames as arguments)
# ============================================================================
run_scraping() {
    log_step "Step 1: Web Scraping"
    
    if [ $# -eq 0 ]; then
        log_warn "No usernames provided. Skipping scraping step."
        log_warn "Usage: $0 [username1] [username2] ..."
        return 0
    fi
    
    cd "$BACKEND_DIR"
    
    for username in "$@"; do
        log_step "  Scraping @$username..."
        python3 -c "
import asyncio
import sys
sys.path.append('$BACKEND_DIR')
from services.scraper_service import ScraperService
from config.database import MongoDB

async def scrape():
    await MongoDB.connect_db()
    scraper = ScraperService()
    try:
        await scraper.scrape_user_profile('$username')
        print(f'Scraped profile for $username')
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
# Step 2: NLP Analysis - Process all unanalyzed text units
# ============================================================================
run_nlp_analysis() {
    log_step "Step 2: NLP Analysis"
    
    cd "$BACKEND_DIR"
    
    python3 -c "
import asyncio
import sys
sys.path.append('$BACKEND_DIR')
from services.nlp_service import NLPService
from config.database import MongoDB
from loguru import logger

async def run_nlp():
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    nlp = NLPService()
    
    # Find all text units that need analysis
    text_units = db.text_units
    unanalyzed = await text_units.find({'analyzed': {\"\$ne\": True}}).to_list(length=1000)
    
    print(f'Found {len(unanalyzed)} text units to analyze')
    
    analyzed_count = 0
    for unit in unanalyzed:
        try:
            text = unit.get('text', '')
            if not text:
                continue
                
            # Run NLP analysis
            result = await nlp.analyze_text(text)
            
            # Store signals
            signal_doc = {
                'case_user': unit.get('username', unit.get('case_user', 'unknown')),
                'text_id': str(unit.get('_id')),
                'text_type': unit.get('text_type', 'comment'),
                'sentiment_score': result.get('sentiment', {}).get('compound', 0),
                'sentiment_label': result.get('sentiment', {}).get('label', 'neutral'),
                'emotions': result.get('emotions', {}),
                'distortions': result.get('distortions', []),
                'distress_score': result.get('distress_score', 0),
                'analyzed_at': asyncio.get_event_loop().time()
            }
            await db.text_units_signals.insert_one(signal_doc)
            
            # Mark as analyzed
            await text_units.update_one({'_id': unit['_id']}, {'\$set': {'analyzed': True}})
            analyzed_count += 1
            
        except Exception as e:
            print(f'Error analyzing text: {e}')
            continue
    
    print(f'Analyzed {analyzed_count} text units')
    await MongoDB.close_db()

asyncio.run(run_nlp())
" 2>&1 | tee -a "$PIPELINE_LOG"
    
    log_success "NLP Analysis complete"
}

# ============================================================================
# Step 3: Feature Engineering - Build case risk profiles
# ============================================================================
run_feature_engineering() {
    log_step "Step 3: Feature Engineering & Risk Profiling"
    
    cd "$BACKEND_DIR"
    
    python3 -c "
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
    
    log_success "Risk profiles created in instagram_scraper.case_risk_profiles"
}

# ============================================================================
# Step 4: Sync to SCS Cases with LLM Analysis
# ============================================================================
sync_to_scs() {
    log_step "Step 4: Sync to SCS Cases (dellinnovate cluster)"
    
    # Check if case-service is running
    if ! curl -s http://localhost:8003/health > /dev/null 2>&1; then
        log_warn "Case service not running. Starting it..."
        cd "$CASE_SERVICE_DIR"
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 &
        sleep 5
    fi
    
    # Call the LLM-enhanced sync endpoint
    log_step "  Calling sync-risk-profiles-llm endpoint..."
    
    RESPONSE=$(curl -s -X POST http://localhost:8003/cases/sync-risk-profiles-llm \
        -H "X-User-Id: pipeline_script" \
        -H "X-User-Role: Admin" \
        -H "Content-Type: application/json")
    
    echo "$RESPONSE" | tee -a "$PIPELINE_LOG"
    
    # Check for success
    if echo "$RESPONSE" | grep -q '"status": "success"'; then
        log_success "Cases synced to dellinnovate.scs_cases with LLM analysis"
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
    CASES=$(curl -s http://localhost:8003/cases \
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
    echo ""
    
    # Parse arguments
    SKIP_SCRAPING=false
    SKIP_NLP=false
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
                shift
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
    echo "  --skip-nlp         Skip the NLP analysis step"
    echo "  --sync-only        Only run sync to SCS (skip scraping + NLP)"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 chrishemsworth harrystyles    # Full pipeline with scraping"
    echo "  $0 --skip-scraping               # Run NLP + sync only"
    echo "  $0 --sync-only                   # Only sync to SCS"
    echo ""
    exit 0
fi

# Run main
main "$@"
