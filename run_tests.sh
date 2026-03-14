#!/bin/bash

echo "================================================"
echo "  MCP & CHATBOT INTEGRATION TEST RUNNER"
echo "================================================"
echo ""

# Check if services are running
echo "🔍 Checking if services are running..."
echo ""

check_service() {
    local name=$1
    local url=$2
    local status=$(curl -s -o /dev/null -w "%{http_code}" $url 2>/dev/null)
    
    if [ "$status" = "200" ]; then
        echo "✅ $name is running"
        return 0
    else
        echo "❌ $name is NOT running (expected at $url)"
        return 1
    fi
}

all_running=true

check_service "MCP Service" "http://localhost:8003/health" || all_running=false
check_service "Chatbot Service" "http://localhost:8000/health" || all_running=false
check_service "Case Service" "http://localhost:8001/health" || all_running=false

echo ""

if [ "$all_running" = false ]; then
    echo "⚠️  Some services are not running!"
    echo ""
    echo "Please start all services first:"
    echo "  Terminal 1: cd chatbot-service && uvicorn app.main:app --port 8000"
    echo "  Terminal 2: cd mcp-service && uvicorn app.main:app --port 8003"
    echo "  Terminal 3: cd case-service && uvicorn app.main:app --port 8001"
    echo ""
    exit 1
fi

echo "✅ All services are running!"
echo ""
echo "================================================"
echo "  Running Backend Integration Tests"
echo "================================================"
echo ""

# Run Python tests
if command -v python3 &> /dev/null; then
    python3 tests/test_mcp_integration.py
else
    python tests/test_mcp_integration.py
fi

test_result=$?

echo ""
echo "================================================"
echo "  Frontend Tests"
echo "================================================"
echo ""
echo "📱 To run frontend tests, open in browser:"
echo "   file://$(pwd)/tests/test_frontend_integration.html"
echo ""
echo "   OR if frontend is running:"
echo "   http://localhost:5173 (then navigate to tests page)"
echo ""

if [ $test_result -eq 0 ]; then
    echo "================================================"
    echo "  ✅ ALL BACKEND TESTS PASSED"
    echo "================================================"
    exit 0
else
    echo "================================================"
    echo "  ❌ SOME TESTS FAILED"
    echo "================================================"
    exit 1
fi
