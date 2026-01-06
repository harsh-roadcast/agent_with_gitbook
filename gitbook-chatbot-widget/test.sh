#!/bin/bash

# Test Script for GitBook Chatbot Widget
# This script tests the widget and API integration

echo "🧪 GitBook Chatbot Widget Test Suite"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if API is running
echo "Test 1: Checking API connectivity..."
API_URL="http://localhost:8001/v1/search"

if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_URL" | grep -q "405\|200"; then
    echo -e "${GREEN}✓ API is accessible${NC}"
else
    echo -e "${RED}✗ API is not accessible at $API_URL${NC}"
    echo -e "${YELLOW}  Make sure your FastAPI server is running on port 8001${NC}"
    exit 1
fi

# Test 2: Test CORS headers
echo ""
echo "Test 2: Checking CORS configuration..."
CORS_RESPONSE=$(curl -s -I -X OPTIONS "$API_URL" \
  -H "Origin: https://roadcast.gitbook.io" \
  -H "Access-Control-Request-Method: POST" 2>&1)

if echo "$CORS_RESPONSE" | grep -qi "access-control-allow-origin"; then
    echo -e "${GREEN}✓ CORS headers are present${NC}"
else
    echo -e "${RED}✗ CORS headers not found${NC}"
    echo -e "${YELLOW}  Check CORS_SETUP.md for configuration instructions${NC}"
fi

# Test 3: Test search endpoint with sample query
echo ""
echo "Test 3: Testing search endpoint with sample query..."
SEARCH_RESPONSE=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "message_id": "test_123",
    "session_id": "test_session",
    "limit": 3
  }')

if echo "$SEARCH_RESPONSE" | grep -q "results"; then
    echo -e "${GREEN}✓ Search endpoint is working${NC}"
    RESULT_COUNT=$(echo "$SEARCH_RESPONSE" | grep -o '"total":[0-9]*' | grep -o '[0-9]*')
    echo -e "  Found $RESULT_COUNT results"
else
    echo -e "${RED}✗ Search endpoint returned unexpected response${NC}"
    echo "  Response: $SEARCH_RESPONSE"
fi

# Test 4: Check widget files exist
echo ""
echo "Test 4: Checking widget files..."
FILES=("chatbot-widget.js" "chatbot-widget.css" "config.js" "demo.html")
ALL_FILES_EXIST=true

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $file exists${NC}"
    else
        echo -e "${RED}✗ $file is missing${NC}"
        ALL_FILES_EXIST=false
    fi
done

# Test 5: Check file sizes (ensure they're not empty)
echo ""
echo "Test 5: Checking file integrity..."
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        SIZE=$(wc -c < "$file")
        if [ "$SIZE" -gt 100 ]; then
            echo -e "${GREEN}✓ $file (${SIZE} bytes)${NC}"
        else
            echo -e "${YELLOW}⚠ $file seems too small (${SIZE} bytes)${NC}"
        fi
    fi
done

# Summary
echo ""
echo "===================================="
echo "Test Summary"
echo "===================================="

if [ "$ALL_FILES_EXIST" = true ]; then
    echo -e "${GREEN}✓ All widget files present${NC}"
    echo -e "${GREEN}✓ API is working${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Open demo.html in your browser to test the widget"
    echo "2. Check GITBOOK_INTEGRATION.md for GitBook setup"
    echo "3. Configure CORS for production (see CORS_SETUP.md)"
else
    echo -e "${RED}✗ Some files are missing${NC}"
fi

echo ""
echo "To test the widget in browser:"
echo "  python -m http.server 8080"
echo "  Then open: http://localhost:8080/demo.html"
