#!/bin/bash
# ============================================================================
# Get JWT Token from Google OAuth for Pipeline CLI
# ============================================================================
# 
# Usage:
#   bash get_jwt_token.sh [--auth-service-url http://localhost:8001]
#
# This script:
#   1. Opens browser to OAuth login with mode=json
#   2. Waits for you to complete OAuth and get redirect to /callback
#   3. You paste the code from the callback response
#   4. Exchanges code for JWT token
#   5. Returns JWT token ready for pipeline script
#
# ============================================================================

set -e

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
AUTH_SERVICE_URL="${1:-http://localhost:8001}"
AUTH_SERVICE_URL="${AUTH_SERVICE_URL%/}"  # Remove trailing slash

# API Gateway is supposed to be on 8000 or 8010
# But for this CLI flow, we talk directly to auth service
API_GATEWAY_URL="http://localhost:8010"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  JWT Token Generator for Pipeline${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Open login URL
echo -e "${YELLOW}Step 1: Opening Google OAuth login...${NC}"
echo ""
echo "Opening browser. Mode=json will return the auth code as JSON instead of redirecting."
echo ""

LOGIN_URL="${AUTH_SERVICE_URL}/login?mode=json"
echo "OAuth Login URL:"
echo -e "${GREEN}${LOGIN_URL}${NC}"
echo ""

# Try to open in browser
if command -v open &> /dev/null; then
    open "$LOGIN_URL"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$LOGIN_URL"
else
    echo -e "${YELLOW}Could not open browser automatically. Copy and paste this URL:${NC}"
    echo "$LOGIN_URL"
fi

echo ""
echo -e "${YELLOW}After you sign in with Google and see the JSON response with 'code', follow Step 2.${NC}"
echo ""

# Step 2: Get code from user
echo -e "${YELLOW}Step 2: Paste the authorization code from the callback response${NC}"
read -p "Enter the 'code' value from the JSON response: " AUTH_CODE

if [ -z "$AUTH_CODE" ]; then
    echo -e "${RED}Error: No code provided${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 3: Exchanging code for JWT token...${NC}"
echo ""

# Step 3: Exchange code for tokens at auth service /token endpoint
TOKEN_RESPONSE=$(curl -sS -X POST "${AUTH_SERVICE_URL}/token" \
    -H "Content-Type: application/json" \
    -d "{\"code\": \"${AUTH_CODE}\"}")

# Check if response is valid JSON
if ! echo "$TOKEN_RESPONSE" | jq . &>/dev/null 2>&1; then
    echo -e "${RED}Error: Invalid response from auth service${NC}"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi

# Extract JWT (try both id_token and access_token)
JWT_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.tokens.id_token // .tokens.access_token // empty' 2>/dev/null || echo "")

if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}Error: Could not extract token from response${NC}"
    echo "Full response:"
    echo "$TOKEN_RESPONSE" | jq '.'
    exit 1
fi

echo -e "${GREEN}✓ JWT token obtained successfully!${NC}"
echo ""

# Step 4: Display token and usage info
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}JWT Token:${NC}"
echo -e "${YELLOW}${JWT_TOKEN}${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Step 5: Show how to use with pipeline
echo -e "${GREEN}Usage with pipeline script:${NC}"
echo ""
echo -e "${YELLOW}Option 1: Direct command${NC}"
echo "bash run_full_pipeline.sh --sync-only --jwt-token \"$JWT_TOKEN\" --require-jwt --auth-service-url ${AUTH_SERVICE_URL}"
echo ""

echo -e "${YELLOW}Option 2: Save to file and reference${NC}"
echo "echo '$JWT_TOKEN' > jwt_token.txt"
echo "bash run_full_pipeline.sh --sync-only --jwt-token-file jwt_token.txt --require-jwt --auth-service-url ${AUTH_SERVICE_URL}"
echo ""

echo -e "${GREEN}✓ Copy the token above and paste it into your pipeline command${NC}"
echo ""
