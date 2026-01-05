#!/bin/bash
# Integration Test Suite Runner
# Comprehensive test execution script for all integration tests

set -e

echo "=========================================="
echo "KPI Operations - Integration Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run test file
run_test() {
    local test_file=$1
    local test_name=$2

    echo -e "${YELLOW}Running: ${test_name}${NC}"
    echo "File: ${test_file}"
    echo "----------------------------------------"

    if pytest "${test_file}" -v --tb=short; then
        echo -e "${GREEN}✓ ${test_name} PASSED${NC}"
        ((PASSED_TESTS++))
    else
        echo -e "${RED}✗ ${test_name} FAILED${NC}"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    echo ""
}

# Navigate to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Project Root: ${PROJECT_ROOT}"
echo ""

# Run all integration tests
echo "=========================================="
echo "PHASE 1: Backend Integration Tests"
echo "=========================================="
echo ""

run_test "tests/backend/test_attendance_integration.py" "Attendance API Integration Tests"
run_test "tests/backend/test_coverage_integration.py" "Coverage API Integration Tests"
run_test "tests/backend/test_quality_integration.py" "Quality API Integration Tests"
run_test "tests/backend/test_multi_tenant_security.py" "Multi-Tenant Security Tests"

echo "=========================================="
echo "PHASE 2: End-to-End Workflow Tests"
echo "=========================================="
echo ""

run_test "tests/e2e/test_production_workflow.py" "Production Workflow E2E Tests"

echo "=========================================="
echo "Test Execution Summary"
echo "=========================================="
echo ""
echo "Total Test Suites: ${TOTAL_TESTS}"
echo -e "Passed: ${GREEN}${PASSED_TESTS}${NC}"
echo -e "Failed: ${RED}${FAILED_TESTS}${NC}"
echo ""

if [ ${FAILED_TESTS} -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "ALL TESTS PASSED! ✓"
    echo -e "==========================================${NC}"
    exit 0
else
    echo -e "${RED}=========================================="
    echo "SOME TESTS FAILED! ✗"
    echo -e "==========================================${NC}"
    exit 1
fi
