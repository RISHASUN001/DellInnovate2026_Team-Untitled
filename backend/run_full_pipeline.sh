#!/bin/bash
# ============================================================================
# Full Instagram Analysis Pipeline
# ============================================================================
# This script orchestrates the complete data flow for a SPECIFIC user:
#   1. Web Scraping     → Instagram user profile + posts (3 posts max)
#   2. Image Download   → Download post images to local folder
#   3. NLP Analysis     → Sentiment, emotion, distortion detection
#   4. Risk Profiling   → Aggregate signals into case_risk_profiles
#   5. Case Sync        → Sync to dellinnovate.scs_cases with LLM analysis
#
# Pipeline Flow:
#   Instagram → Scraper → instagram_posts (instagram_scraper)
#                            ↓
#                    Download Images (local folder)
#                            ↓
#                    NLP Analysis → text_units_signals
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

# Default max posts per user
MAX_POSTS=3

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
# Step 1: Web Scraping + Image Download
# Scrapes user profile and posts (limited to MAX_POSTS)
# Images are automatically downloaded via scraper_service.py
# ============================================================================
run_scraping() {
    local username=$1
    log_step "Step 1: Web Scraping for @$username"
    
    if [ -z "$username" ]; then
        log_error "No username provided for scraping"
        return 1
    fi
    
    cd "$BACKEND_DIR"
    
    log_step "  Scraping profile and $MAX_POSTS posts for @$username..."
    python3 << EOF
import asyncio
import sys
sys.path.insert(0, '$BACKEND_DIR')
from services.scraper_service import ScraperService
from config.database import MongoDB

async def scrape():
    await MongoDB.connect_db()
    scraper = ScraperService()
    try:
        # Scrape user profile
        print(f'Scraping profile for $username...')
        await scraper.scrape_user_profile('$username')
        print(f'Profile scraped for $username')
        
        # Scrape posts with limit - this also auto-downloads images
        print(f'Scraping $MAX_POSTS posts for $username (images will be auto-downloaded)...')
        posts = await scraper.scrape_user_posts('$username', max_posts=$MAX_POSTS)
        print(f'Scraped {len(posts)} posts for $username')
        
        # Return success
        print(f'SUCCESS: Scraped profile and {len(posts)} posts for $username')
        
    except Exception as e:
        print(f'Error scraping $username: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await MongoDB.close_db()

asyncio.run(scrape())
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Scraped @$username with $MAX_POSTS posts and images downloaded"
    else
        log_error "Failed to scrape @$username"
        return 1
    fi
}

# ============================================================================
# Step 2: NLP Analysis - Process posts and comments for the specified user
# Reads from instagram_posts, stores signals in text_units_signals
# ============================================================================
run_nlp_analysis() {
    local username=$1
    log_step "Step 2: NLP Analysis for @$username"
    
    if [ -z "$username" ]; then
        log_error "No username provided for NLP analysis"
        return 1
    fi
    
    cd "$BACKEND_DIR"
    
    python3 << EOF
import asyncio
import sys
from datetime import datetime
sys.path.insert(0, '$BACKEND_DIR')
from services.nlp_service import NLPService
from config.database import MongoDB, get_posts_collection

async def run_nlp():
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    nlp = NLPService()
    
    # Get posts for the specified user
    posts_collection = await get_posts_collection()
    
    # Find posts by the specified user
    cursor = posts_collection.find({'username': '$username'})
    posts = await cursor.to_list(length=100)
    
    print(f'Found {len(posts)} posts for @$username')
    
    if not posts:
        print(f'No posts found for @$username - checking if posts have different username field...')
        # Try alternative query
        cursor = posts_collection.find({})
        all_posts = await cursor.to_list(length=100)
        print(f'Total posts in collection: {len(all_posts)}')
        if all_posts:
            print(f'Sample post fields: {list(all_posts[0].keys())}')
    
    analyzed_count = 0
    signals_collection = db.text_units_signals
    
    for post in posts:
        try:
            # Analyze caption if present
            caption = post.get('caption', '')
            if not caption:
                captions = post.get('captions', [])
                if captions and len(captions) > 0:
                    caption = captions[0] if isinstance(captions[0], str) else str(captions[0])
            
            if caption:
                result = nlp.analyze_text(caption)
                
                signal_doc = {
                    'case_user': '$username',
                    'text_id': str(post.get('_id')),
                    'shortcode': post.get('shortcode'),
                    'text_type': 'caption',
                    'text': caption[:500] if caption else '',
                    'sentiment_score': result.get('sentiment_score', 0.0),
                    'sentiment_label': result.get('sentiment', 'neutral'),
                    'emotion_label': result.get('primary_emotion', 'neutral'),
                    'emotions': result.get('emotions', {}),
                    'distortion_indicator': 1 if result.get('distortion_indicator', False) else 0,
                    'distress_score': result.get('distortion_score', 0.0),
                    'is_distress': result.get('distortion_indicator', False),
                    'processed_at': datetime.utcnow()
                }
                await signals_collection.insert_one(signal_doc)
                analyzed_count += 1
            
            # Analyze comments if present
            comments = post.get('comments', [])
            for comment in comments[:10]:  # Limit to 10 comments per post
                comment_text = comment.get('text', '')
                if not comment_text:
                    continue
                
                result = nlp.analyze_text(comment_text)
                
                signal_doc = {
                    'case_user': '$username',
                    'text_id': comment.get('id', str(post.get('_id'))),
                    'shortcode': post.get('shortcode'),
                    'text_type': 'comment',
                    'text': comment_text[:500],
                    'commenter': comment.get('owner', 'unknown'),
                    'sentiment_score': result.get('sentiment_score', 0.0),
                    'sentiment_label': result.get('sentiment', 'neutral'),
                    'emotion_label': result.get('primary_emotion', 'neutral'),
                    'emotions': result.get('emotions', {}),
                    'distortion_indicator': 1 if result.get('distortion_indicator', False) else 0,
                    'distress_score': result.get('distortion_score', 0.0),
                    'is_distress': result.get('distortion_indicator', False),
                    'processed_at': datetime.utcnow()
                }
                await signals_collection.insert_one(signal_doc)
                analyzed_count += 1
                
        except Exception as e:
            print(f'Error analyzing post {post.get("shortcode")}: {e}')
            continue
    
    print(f'Analyzed {analyzed_count} text units for @$username')
    print(f'Signals stored in text_units_signals collection')
    await MongoDB.close_db()

asyncio.run(run_nlp())
EOF
    
    if [ $? -eq 0 ]; then
        log_success "NLP Analysis complete for @$username"
    else
        log_error "NLP Analysis failed for @$username"
        return 1
    fi
}

# ============================================================================
# Step 3: Feature Engineering - Build risk profile for the specified user
# ============================================================================
run_feature_engineering() {
    local username=$1
    log_step "Step 3: Feature Engineering & Risk Profiling for @$username"
    
    if [ -z "$username" ]; then
        log_error "No username provided for feature engineering"
        return 1
    fi
    
    cd "$BACKEND_DIR"
    
    python3 << EOF
import asyncio
import sys
sys.path.insert(0, '$BACKEND_DIR')
from analytics.feature_engineering import BehavioralFeatureEngineer
from config.database import MongoDB

async def build_profile():
    await MongoDB.connect_db()
    
    engineer = BehavioralFeatureEngineer()
    
    # Process only the specified user
    print(f'Processing risk profile for @$username...')
    
    try:
        profile = await engineer.compute_risk_profile('$username', window_days=30)
        
        if profile:
            await engineer.store_risk_profile(profile)
            print(f'SUCCESS: Risk profile created for @$username')
            print(f'  Risk Score: {profile.get("risk_score", 0):.1f}')
            print(f'  Risk Level: {profile.get("risk_level", "Unknown")}')
            print(f'  Priority: {profile.get("priority", 0)}')
        else:
            print(f'WARNING: No risk profile could be computed for @$username')
            print(f'This may be because no signals were found in text_units_signals')
            
            # Create a minimal profile so the case can still be synced
            db = MongoDB.get_db()
            minimal_profile = {
                'case_user': '$username',
                'signal_count': 0,
                'distortion_count': 0,
                'distortion_rate': 0.0,
                'avg_sentiment_score': 0.0,
                'sentiment_std': 0.0,
                'negative_sentiment_rate': 0.0,
                'positive_sentiment_rate': 0.0,
                'distress_emotion_count': 0,
                'distress_emotion_rate': 0.0,
                'emotion_distribution': {},
                'avg_distress_score': 0.0,
                'abnormal_activity': False,
                'risk_score': 25.0,
                'risk_level': 'Low',
                'priority': 3,
                'top_distress_comments': [],
                'key_signals': ['New case - pending analysis'],
                'computed_at': __import__('datetime').datetime.utcnow(),
                'last_updated': __import__('datetime').datetime.utcnow()
            }
            await db.case_risk_profiles.update_one(
                {'case_user': '$username'},
                {'\$set': minimal_profile},
                upsert=True
            )
            print(f'Created minimal risk profile for @$username')
            
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    await MongoDB.close_db()

asyncio.run(build_profile())
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Risk profile created for @$username in case_risk_profiles"
    else
        log_error "Failed to create risk profile for @$username"
        return 1
    fi
}

# ============================================================================
# Step 4: Sync to SCS Cases with LLM Analysis (for specific user)
# ============================================================================
sync_to_scs() {
    local username=$1
    log_step "Step 4: Sync to SCS Cases with LLM for @$username"
    
    if [ -z "$username" ]; then
        log_error "No username provided for sync"
        return 1
    fi
    
    # Check if case-service is running
    if ! curl -s http://localhost:8003/health > /dev/null 2>&1; then
        log_warn "Case service not running. Starting it..."
        cd "$CASE_SERVICE_DIR"
        # Use system Python which has correct pydantic_settings version
        /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8003 &
        sleep 5
        
        # Verify it started
        if ! curl -s http://localhost:8003/health > /dev/null 2>&1; then
            log_error "Failed to start case-service. Please start it manually:"
            log_error "  cd $CASE_SERVICE_DIR && python -m uvicorn app.main:app --port 8003"
            return 1
        fi
    fi
    
    # Call the user-specific LLM sync endpoint
    log_step "  Calling sync-user-risk-profile-llm endpoint for @$username..."
    
    RESPONSE=$(curl -s -X POST "http://localhost:8003/cases/sync-user-risk-profile-llm/$username" \
        -H "X-User-Id: pipeline_script" \
        -H "X-User-Role: Admin" \
        -H "Content-Type: application/json")
    
    echo "$RESPONSE" | tee -a "$PIPELINE_LOG"
    
    # Check for success (handle both with and without spaces in JSON)
    if echo "$RESPONSE" | grep -qE '"status"\s*:\s*"success"'; then
        log_success "Case synced for @$username to dellinnovate.scs_cases with LLM analysis"
    else
        log_error "Failed to sync case for @$username"
        return 1
    fi
}

# ============================================================================
# Step 5: Verify Frontend Data
# ============================================================================
verify_data() {
    local username=$1
    log_step "Step 5: Verify Frontend Data for @$username"
    
    # Get case count from API
    USER_ID="@case_$username"
    
    CASE=$(curl -s "http://localhost:8003/cases" \
        -H "X-User-Id: pipeline_script" \
        -H "X-User-Role: Admin" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)
for c in data:
    if c.get('user_id') == '$USER_ID':
        print(json.dumps(c, indent=2))
        break
" 2>/dev/null || echo "{}")
    
    if [ -n "$CASE" ] && [ "$CASE" != "{}" ]; then
        log_success "Case found for @$username"
        echo "$CASE" | head -20
    else
        log_warn "Case for @$username not found in API response"
    fi
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
    USERNAME=""
    
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
            --max-posts)
                MAX_POSTS=$2
                shift 2
                ;;
            *)
                if [ -z "$USERNAME" ]; then
                    USERNAME="$1"
                fi
                shift
                ;;
        esac
    done
    
    # Validate username
    if [ -z "$USERNAME" ]; then
        log_error "No username provided!"
        echo ""
        echo "Usage: $0 [OPTIONS] USERNAME"
        echo ""
        echo "Options:"
        echo "  --skip-scraping    Skip the web scraping step"
        echo "  --skip-nlp         Skip the NLP analysis step"
        echo "  --sync-only        Only run sync to SCS (skip scraping + NLP)"
        echo "  --max-posts N      Maximum posts to scrape (default: 3)"
        echo "  -h, --help         Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 chrishemsworth          # Full pipeline for user"
        echo "  $0 --max-posts 5 harrystyles"
        echo "  $0 --skip-scraping gretathunberg"
        echo "  $0 --sync-only username"
        echo ""
        exit 1
    fi
    
    log_step "Processing user: @$USERNAME"
    log_step "Max posts to scrape: $MAX_POSTS"
    echo ""
    
    # Run pipeline steps
    if [ "$SKIP_SCRAPING" = false ]; then
        run_scraping "$USERNAME"
    else
        log_warn "Skipping scraping step"
    fi
    
    if [ "$SKIP_NLP" = false ]; then
        run_nlp_analysis "$USERNAME"
    else
        log_warn "Skipping NLP analysis step"
    fi
    
    run_feature_engineering "$USERNAME"
    sync_to_scs "$USERNAME"
    verify_data "$USERNAME"
    
    echo ""
    log_success "Pipeline completed successfully for @$USERNAME!"
    echo ""
    echo "=============================================="
    echo "  Pipeline Summary for @$USERNAME"
    echo "=============================================="
    echo "  1. Scraped Instagram profile + $MAX_POSTS posts"
    echo "  2. Downloaded images to image-service/data/post_images/"
    echo "  3. NLP signals stored in instagram_scraper.text_units_signals"
    echo "  4. Risk profile stored in instagram_scraper.case_risk_profiles"
    echo "  5. Case synced to dellinnovate.scs_cases with LLM analysis"
    echo ""
    echo "  Log file: $PIPELINE_LOG"
    echo "=============================================="
}

# Show usage if --help
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Usage: $0 [OPTIONS] USERNAME"
    echo ""
    echo "Run the full Instagram analysis pipeline for a specific user."
    echo ""
    echo "Options:"
    echo "  --skip-scraping    Skip the web scraping step"
    echo "  --skip-nlp         Skip the NLP analysis step"
    echo "  --sync-only        Only run sync to SCS (skip scraping + NLP + feature eng.)"
    echo "  --max-posts N      Maximum posts to scrape (default: 3)"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 chrishemsworth           # Full pipeline with 3 posts"
    echo "  $0 --max-posts 5 harrystyles  # Full pipeline with 5 posts"
    echo "  $0 --skip-scraping gretathunberg  # Run NLP + feature eng. + sync"
    echo "  $0 --sync-only username     # Only sync existing risk profile to SCS"
    echo ""
    echo "Data Flow:"
    echo "  Instagram → Scraper → instagram_posts"
    echo "                           ↓"
    echo "  Image Download → image-service/data/post_images/"
    echo "                           ↓"
    echo "  NLP Analysis → text_units_signals"
    echo "                           ↓"
    echo "  Feature Engineering → case_risk_profiles"
    echo "                           ↓"
    echo "  LLM Sync → scs_cases → Frontend"
    echo ""
    exit 0
fi

# Run main
main "$@"
