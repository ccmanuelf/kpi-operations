#!/bin/bash

###############################################################################
# Production Validation Test Runner
# Runs all validation suites and generates comprehensive report
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATION_DIR="${PROJECT_ROOT}/tests/validation"
REPORT_DIR="${PROJECT_ROOT}/validation-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="${REPORT_DIR}/validation_report_${TIMESTAMP}.txt"

# Create report directory
mkdir -p "$REPORT_DIR"

# Initialize report
cat > "$REPORT_FILE" << EOF
================================================================================
KPI OPERATIONS PLATFORM - PRODUCTION VALIDATION REPORT
================================================================================
Date: $(date)
Version: 1.0.0
Validated By: Production Validation Suite
================================================================================

EOF

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  KPI Operations Platform - Production Validation Suite    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to run test and capture result
run_test() {
    local test_name=$1
    local test_script=$2
    local test_description=$3

    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Running: ${test_name}${NC}"
    echo -e "${BLUE}Description: ${test_description}${NC}"
    echo ""

    echo "" >> "$REPORT_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
    echo "TEST: ${test_name}" >> "$REPORT_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Run test and capture output
    if python3 "$test_script" >> "$REPORT_FILE" 2>&1; then
        echo -e "${GREEN}✅ PASS${NC} - ${test_name}"
        echo "RESULT: ✅ PASS" >> "$REPORT_FILE"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} - ${test_name}"
        echo "RESULT: ❌ FAIL" >> "$REPORT_FILE"
        return 1
    fi
}

# Track results
total_tests=0
passed_tests=0
failed_tests=0

# Test 1: Database Schema Validation
echo ""
if run_test \
    "Database Schema Validation" \
    "${VALIDATION_DIR}/comprehensive_schema_validation.py" \
    "Validates all 213+ database fields, foreign keys, and indexes"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi
((total_tests++))

# Test 2: API Endpoint Validation
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Checking if backend is running...${NC}"
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running${NC}"

    if run_test \
        "API Endpoint Validation" \
        "${VALIDATION_DIR}/api_endpoint_validation.py" \
        "Tests all 78+ API endpoints with multi-tenant isolation"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
    ((total_tests++))
else
    echo -e "${RED}❌ Backend is NOT running${NC}"
    echo -e "${YELLOW}⚠️  Skipping API tests. Start backend with: uvicorn main:app${NC}"
    echo "" >> "$REPORT_FILE"
    echo "API ENDPOINT TEST: SKIPPED (Backend not running)" >> "$REPORT_FILE"
fi

# Test 3: Security Audit
echo ""
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    if run_test \
        "Security Audit" \
        "${VALIDATION_DIR}/security_audit.py" \
        "Tests for SQL injection, XSS, CSRF, and multi-tenant data leakage"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
    ((total_tests++))
else
    echo -e "${YELLOW}⚠️  Skipping security audit (Backend not running)${NC}"
    echo "SECURITY AUDIT: SKIPPED (Backend not running)" >> "$REPORT_FILE"
fi

# Test 4: Performance Benchmarks
echo ""
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    if run_test \
        "Performance Benchmarks" \
        "${VALIDATION_DIR}/performance_benchmarks.py" \
        "Benchmarks response times and load capacity"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
    ((total_tests++))
else
    echo -e "${YELLOW}⚠️  Skipping performance benchmarks (Backend not running)${NC}"
    echo "PERFORMANCE TEST: SKIPPED (Backend not running)" >> "$REPORT_FILE"
fi

# Generate summary
echo "" >> "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
echo "VALIDATION SUMMARY" >> "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "Total Tests:  $total_tests" >> "$REPORT_FILE"
echo "Passed:       $passed_tests" >> "$REPORT_FILE"
echo "Failed:       $failed_tests" >> "$REPORT_FILE"
echo "Skipped:      $((4 - total_tests))" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ $failed_tests -eq 0 ] && [ $total_tests -eq 4 ]; then
    echo "OVERALL RESULT: ✅ PRODUCTION READY" >> "$REPORT_FILE"
    production_ready=true
else
    echo "OVERALL RESULT: ❌ NOT PRODUCTION READY" >> "$REPORT_FILE"
    production_ready=false
fi

echo "" >> "$REPORT_FILE"
echo "Report saved to: ${REPORT_FILE}" >> "$REPORT_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT_FILE"

# Print summary
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              VALIDATION SUMMARY                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Total Tests:  ${BLUE}$total_tests${NC}"
echo -e "Passed:       ${GREEN}$passed_tests${NC}"
echo -e "Failed:       ${RED}$failed_tests${NC}"

if [ $total_tests -lt 4 ]; then
    echo -e "Skipped:      ${YELLOW}$((4 - total_tests))${NC}"
fi

echo ""

if [ "$production_ready" = true ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║             ✅ PRODUCTION READY ✅                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║           ❌ NOT PRODUCTION READY ❌                      ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo -e "${BLUE}Report saved to:${NC} ${REPORT_FILE}"
echo ""

# Exit with appropriate code
if [ "$production_ready" = true ]; then
    exit 0
else
    exit 1
fi
