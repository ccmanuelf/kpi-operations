#!/bin/bash
# Test Runner Script for Manufacturing KPI Platform
# Runs backend and frontend tests with coverage

set -e  # Exit on error

echo "============================================"
echo "Manufacturing KPI Platform - Test Suite"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "${YELLOW}Installing/updating dependencies...${NC}"
pip install -q pytest pytest-cov pytest-asyncio fastapi httpx

# Run backend tests
echo ""
echo "${GREEN}========== BACKEND TESTS (Pytest) ==========${NC}"
echo ""

pytest tests/backend/ \
    --cov=app \
    --cov-report=html:tests/coverage/backend \
    --cov-report=term-missing \
    --cov-fail-under=90 \
    -v

BACKEND_EXIT_CODE=$?

# Run integration tests
echo ""
echo "${GREEN}========== INTEGRATION TESTS ==========${NC}"
echo ""

pytest tests/integration/ \
    -v

INTEGRATION_EXIT_CODE=$?

# Run frontend tests (if Node.js available)
if command -v npm &> /dev/null; then
    echo ""
    echo "${GREEN}========== FRONTEND TESTS (Vitest) ==========${NC}"
    echo ""

    npm run test:coverage

    FRONTEND_EXIT_CODE=$?
else
    echo "${YELLOW}Node.js not found. Skipping frontend tests.${NC}"
    FRONTEND_EXIT_CODE=0
fi

# Summary
echo ""
echo "============================================"
echo "              TEST SUMMARY"
echo "============================================"

if [ $BACKEND_EXIT_CODE -eq 0 ]; then
    echo "${GREEN}✓ Backend tests: PASSED${NC}"
else
    echo "${RED}✗ Backend tests: FAILED${NC}"
fi

if [ $INTEGRATION_EXIT_CODE -eq 0 ]; then
    echo "${GREEN}✓ Integration tests: PASSED${NC}"
else
    echo "${RED}✗ Integration tests: FAILED${NC}"
fi

if [ $FRONTEND_EXIT_CODE -eq 0 ]; then
    echo "${GREEN}✓ Frontend tests: PASSED${NC}"
else
    echo "${RED}✗ Frontend tests: FAILED${NC}"
fi

echo ""
echo "Coverage reports:"
echo "  Backend: tests/coverage/backend/index.html"
if [ -f "tests/coverage/frontend/index.html" ]; then
    echo "  Frontend: tests/coverage/frontend/index.html"
fi

# Exit with error if any tests failed
if [ $BACKEND_EXIT_CODE -ne 0 ] || [ $INTEGRATION_EXIT_CODE -ne 0 ] || [ $FRONTEND_EXIT_CODE -ne 0 ]; then
    exit 1
fi

echo ""
echo "${GREEN}All tests passed!${NC}"
exit 0
