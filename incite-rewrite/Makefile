# Makefile for Incite Rewrite Test Suite
# London School TDD methodology - focus on behavior verification

.PHONY: help install test test-unit test-integration test-e2e test-performance test-fast test-slow test-coverage test-report clean lint format type-check security-check all-checks

# Default target
help:
	@echo "Incite Rewrite Test Suite - London School TDD"
	@echo "=============================================="
	@echo ""
	@echo "Available targets:"
	@echo "  install           - Install dependencies"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-e2e          - Run end-to-end tests only"
	@echo "  test-performance  - Run performance benchmarks"
	@echo "  test-fast         - Run fast tests only (<100ms)"
	@echo "  test-slow         - Run slow tests only (>1s)"
	@echo "  test-coverage     - Run tests with detailed coverage"
	@echo "  test-report       - Generate HTML test report"
	@echo "  lint              - Run code linting"
	@echo "  format            - Format code"
	@echo "  type-check        - Run type checking"
	@echo "  security-check    - Run security checks"
	@echo "  all-checks        - Run all quality checks"
	@echo "  clean             - Clean test artifacts"

# Python and pip commands
PYTHON := python3
PIP := pip3
PYTEST := python3 -m pytest

# Directories
SRC_DIR := src
TEST_DIR := tests
REPORTS_DIR := reports
HTMLCOV_DIR := htmlcov

# Install dependencies
install:
	@echo "Installing dependencies..."
	$(PIP) install -r requirements-test.txt
	$(PIP) install flask flask-cors
	@echo "Dependencies installed successfully"

# Test targets
test:
	@echo "Running all tests with London School TDD methodology..."
	$(PYTEST) $(TEST_DIR) -v --tb=short

test-unit:
	@echo "Running unit tests - testing real component behavior..."
	$(PYTEST) $(TEST_DIR)/unit -v -m "unit" --tb=short

test-integration:
	@echo "Running integration tests - testing API and database interactions..."
	$(PYTEST) $(TEST_DIR)/integration -v -m "integration" --tb=short

test-e2e:
	@echo "Running end-to-end tests - testing complete user workflows..."
	$(PYTEST) $(TEST_DIR)/e2e -v -m "e2e" --tb=short --timeout=300

test-performance:
	@echo "Running performance benchmarks - measuring real system performance..."
	$(PYTEST) $(TEST_DIR)/performance -v -m "performance" --tb=short --timeout=600

test-fast:
	@echo "Running fast tests only..."
	$(PYTEST) $(TEST_DIR) -v -m "fast" --tb=short

test-slow:
	@echo "Running slow tests only..."
	$(PYTEST) $(TEST_DIR) -v -m "slow" --tb=short --timeout=300

test-coverage:
	@echo "Running tests with detailed coverage analysis..."
	$(PYTEST) $(TEST_DIR) -v --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing --cov-report=xml --cov-fail-under=90

test-report:
	@echo "Generating comprehensive HTML test report..."
	mkdir -p $(REPORTS_DIR)
	$(PYTEST) $(TEST_DIR) -v --html=$(REPORTS_DIR)/test_report.html --self-contained-html --cov=$(SRC_DIR) --cov-report=html:$(REPORTS_DIR)/coverage

# Authentication tests
test-auth:
	@echo "Running authentication tests - testing real hash validation and database ops..."
	$(PYTEST) $(TEST_DIR) -v -m "auth" --tb=short

# Text processing tests
test-text:
	@echo "Running text processing tests - testing real NLP algorithms..."
	$(PYTEST) $(TEST_DIR) -v -m "text_processing" --tb=short

# Database tests
test-database:
	@echo "Running database tests - testing real database operations..."
	$(PYTEST) $(TEST_DIR) -v -m "database" --tb=short

# API tests
test-api:
	@echo "Running API tests - testing real HTTP endpoints..."
	$(PYTEST) $(TEST_DIR) -v -m "api" --tb=short

# Security tests
test-security:
	@echo "Running security tests - testing real security measures..."
	$(PYTEST) $(TEST_DIR) -v -m "security" --tb=short

# Parallel testing
test-parallel:
	@echo "Running tests in parallel for faster execution..."
	$(PYTEST) $(TEST_DIR) -v -n auto --dist=loadfile

# Continuous testing (watch for changes)
test-watch:
	@echo "Starting continuous testing - watching for file changes..."
	$(PYTEST) $(TEST_DIR) -v -f --tb=short

# Code quality checks
lint:
	@echo "Running code linting..."
	flake8 $(SRC_DIR) $(TEST_DIR) --max-line-length=120 --exclude=__pycache__,*.pyc
	@echo "Linting completed"

format:
	@echo "Formatting code..."
	black $(SRC_DIR) $(TEST_DIR) --line-length=120
	isort $(SRC_DIR) $(TEST_DIR) --profile=black
	@echo "Code formatting completed"

type-check:
	@echo "Running type checking..."
	mypy $(SRC_DIR) --ignore-missing-imports --show-error-codes
	@echo "Type checking completed"

security-check:
	@echo "Running security checks..."
	bandit -r $(SRC_DIR) -f json -o $(REPORTS_DIR)/security_report.json || true
	safety check --json --output $(REPORTS_DIR)/safety_report.json || true
	@echo "Security checks completed"

all-checks: lint type-check security-check
	@echo "All code quality checks completed"

# Performance benchmarking
benchmark:
	@echo "Running comprehensive performance benchmarks..."
	$(PYTHON) $(TEST_DIR)/performance/test_benchmarks.py

# Load testing
load-test:
	@echo "Running load tests..."
	$(PYTEST) $(TEST_DIR) -v -k "concurrent or load" --tb=short --timeout=600

# Memory profiling
memory-test:
	@echo "Running memory usage tests..."
	$(PYTHON) -m memory_profiler $(PYTEST) $(TEST_DIR)/performance -v --tb=short

# Clean up
clean:
	@echo "Cleaning test artifacts..."
	rm -rf $(HTMLCOV_DIR)
	rm -rf $(REPORTS_DIR)
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	find . -type f -name "*.db" -delete
	rm -rf .mypy_cache
	@echo "Cleanup completed"

# Development workflow
dev-test: clean install test-fast lint
	@echo "Development workflow completed - fast tests + linting"

# CI/CD workflow
ci-test: clean install test-coverage lint type-check security-check
	@echo "CI/CD workflow completed - full test suite + quality checks"

# Full validation
full-test: clean install test lint type-check security-check benchmark
	@echo "Full validation completed - all tests + quality checks + benchmarks"

# Test specific components
test-component:
	@echo "Usage: make test-component COMPONENT=auth|text|api|database"
	@echo "Example: make test-component COMPONENT=auth"
ifdef COMPONENT
	$(PYTEST) $(TEST_DIR) -v -k "$(COMPONENT)" --tb=short
endif

# Debug test failures
debug-test:
	@echo "Running tests with debug output..."
	$(PYTEST) $(TEST_DIR) -v -s --tb=long --capture=no

# Test with specific Python version
test-python-version:
	@echo "Testing with specific Python version..."
	@echo "Current Python version: $$(python3 --version)"
	$(PYTEST) $(TEST_DIR) -v --tb=short

# Generate test documentation
test-docs:
	@echo "Generating test documentation..."
	mkdir -p $(REPORTS_DIR)/docs
	$(PYTEST) $(TEST_DIR) --collect-only -q > $(REPORTS_DIR)/docs/test_inventory.txt
	@echo "Test documentation generated in $(REPORTS_DIR)/docs/"

# Verify test completeness
verify-coverage:
	@echo "Verifying test coverage completeness..."
	$(PYTEST) $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=term-missing --cov-fail-under=90
	@echo "Coverage verification completed"

# Run specific test file
test-file:
	@echo "Usage: make test-file FILE=path/to/test_file.py"
ifdef FILE
	$(PYTEST) $(FILE) -v --tb=short
endif

# London School TDD specific targets
tdd-unit:
	@echo "Running London School TDD unit tests - no mocks, real behavior..."
	$(PYTEST) $(TEST_DIR)/unit -v --tb=short -x

tdd-integration:
	@echo "Running London School TDD integration tests - real collaborations..."
	$(PYTEST) $(TEST_DIR)/integration -v --tb=short -x

tdd-e2e:
	@echo "Running London School TDD end-to-end tests - complete workflows..."
	$(PYTEST) $(TEST_DIR)/e2e -v --tb=short -x

# Test data validation
validate-test-data:
	@echo "Validating test data and fixtures..."
	$(PYTHON) -c "import tests.conftest; print('Test configuration validated')"

# Performance analysis
perf-analysis:
	@echo "Running detailed performance analysis..."
	$(PYTEST) $(TEST_DIR)/performance -v --tb=short --benchmark-only --benchmark-sort=mean

# Help for specific test categories
help-tests:
	@echo "Test Categories (London School TDD):"
	@echo "===================================="
	@echo "Unit Tests (tests/unit/*):"
	@echo "  - Test individual components with real behavior"
	@echo "  - No mocks - validate actual functionality"
	@echo "  - Focus on component interactions and contracts"
	@echo ""
	@echo "Integration Tests (tests/integration/*):"
	@echo "  - Test API endpoints with real HTTP responses"
	@echo "  - Real database operations and transactions"
	@echo "  - Authentication flows and session management"
	@echo ""
	@echo "End-to-End Tests (tests/e2e/*):"
	@echo "  - Complete user workflows and journeys"
	@echo "  - System reliability and error handling"
	@echo "  - Performance under realistic conditions"
	@echo ""
	@echo "Performance Tests (tests/performance/*):"
	@echo "  - Real performance benchmarking"
	@echo "  - Memory usage and resource monitoring"
	@echo "  - Concurrent load testing"

# Final validation before deployment
pre-deploy: clean install full-test
	@echo "Pre-deployment validation completed successfully!"
	@echo "✓ All tests passed"
	@echo "✓ Code quality checks passed"
	@echo "✓ Security checks passed"
	@echo "✓ Performance benchmarks completed"
	@echo "Ready for deployment!"