# Integration Test Suite - Quick Start Guide

## Overview

This directory contains comprehensive integration tests covering all API endpoints, multi-tenant security, and end-to-end workflows.

**Total Test Files**: 5
**Total Test Cases**: 150+
**Coverage Target**: 80%+

---

## Quick Start

### 1. Install Dependencies
```bash
pip install pytest pytest-asyncio pytest-cov
```

### 2. Run All Tests
```bash
# Simple approach - run all
pytest tests/ -v

# With coverage report
pytest tests/ --cov=backend --cov-report=html --cov-report=term

# Using test runner script
./tests/run_integration_tests.sh
```

### 3. Run Individual Test Suites
```bash
# Attendance tests
pytest tests/backend/test_attendance_integration.py -v

# Coverage tests
pytest tests/backend/test_coverage_integration.py -v

# Quality tests
pytest tests/backend/test_quality_integration.py -v

# Multi-tenant security tests
pytest tests/backend/test_multi_tenant_security.py -v

# E2E workflow tests
pytest tests/e2e/test_production_workflow.py -v
```

---

## Test Files

| File | Purpose | Test Cases |
|------|---------|------------|
| test_attendance_integration.py | Attendance API endpoints + Bradford Factor | 25+ |
| test_coverage_integration.py | Coverage API + floating pool | 20+ |
| test_quality_integration.py | Quality API + FPY/PPM/DPMO | 30+ |
| test_multi_tenant_security.py | Multi-tenant data isolation | 15+ |
| test_production_workflow.py | E2E production workflows | 10+ |

---

## Documentation

For detailed test documentation, see:
- /docs/TEST_SUITE_SUMMARY.md - Comprehensive test suite summary

**Last Updated**: 2026-01-02
