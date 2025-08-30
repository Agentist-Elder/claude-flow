#!/usr/bin/env python3
"""
Comprehensive test runner for London School TDD test suite.
Provides various test execution modes and reporting capabilities.
"""

import sys
import os
import pytest
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_unit_tests():
    """Run unit tests only."""
    return pytest.main([
        "-m", "unit",
        "--tb=short",
        "-v"
    ])


def run_integration_tests():
    """Run integration tests only."""
    return pytest.main([
        "-m", "integration", 
        "--tb=short",
        "-v"
    ])


def run_e2e_tests():
    """Run end-to-end tests only."""
    return pytest.main([
        "-m", "e2e",
        "--tb=short", 
        "-v"
    ])


def run_performance_tests():
    """Run performance tests only."""
    return pytest.main([
        "-m", "performance",
        "--tb=short",
        "-v"
    ])


def run_fast_tests():
    """Run only fast tests for development."""
    return pytest.main([
        "-m", "fast or (unit and not slow)",
        "--tb=short",
        "-v",
        "--durations=5"
    ])


def run_all_tests():
    """Run complete test suite."""
    return pytest.main([
        "--tb=short",
        "-v",
        "--durations=10",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=term-missing"
    ])


def run_tests_with_coverage():
    """Run tests with detailed coverage reporting."""
    return pytest.main([
        "--cov=src",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--tb=short",
        "-v"
    ])


def run_behavior_verification_tests():
    """Run tests focused on behavior verification and mocking."""
    return pytest.main([
        "-m", "mock or behavior",
        "--tb=short",
        "-v",
        "-k", "test_.*behavior.*or test_.*collaboration.*or test_.*interaction.*"
    ])


def run_london_school_showcase():
    """Run showcase tests demonstrating London School TDD principles."""
    showcase_tests = [
        "test_app.py::TestAuthenticationMiddleware::test_require_auth_validates_bearer_token",
        "test_processor.py::TestTextProcessorBehavior::test_analyzes_text_and_extracts_metrics", 
        "test_citations.py::TestCitationExtractionBehavior::test_extracts_basic_federal_case_citation",
        "test_courtlistener.py::TestHTTPRequestBehavior::test_makes_get_request_with_proper_parameters",
        "test_storage.py::TestQueryExecutionBehavior::test_executes_select_query_and_returns_results",
        "test_integration.py::TestCompleteUserWorkflow::test_complete_document_analysis_workflow"
    ]
    
    return pytest.main(showcase_tests + [
        "--tb=short",
        "-v",
        "--no-header"
    ])


def main():
    """Main test runner with command line options."""
    parser = argparse.ArgumentParser(description="London School TDD Test Runner")
    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=[
            "all", "unit", "integration", "e2e", "performance", 
            "fast", "coverage", "behavior", "showcase"
        ],
        help="Type of tests to run"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel")
    parser.add_argument("--markers", "-m", help="Run tests with specific markers")
    parser.add_argument("--keyword", "-k", help="Run tests matching keyword")
    parser.add_argument("--file", "-f", help="Run specific test file")
    
    args = parser.parse_args()
    
    # Set up environment
    os.environ["PYTEST_CURRENT_TEST"] = "true"
    
    if args.debug:
        os.environ["DEBUG"] = "true"
        
    # Build pytest command
    pytest_args = []
    
    if args.verbose:
        pytest_args.extend(["-v", "--tb=long"])
    else:
        pytest_args.extend(["--tb=short"])
        
    if args.parallel:
        pytest_args.extend(["-n", str(args.parallel)])
        
    if args.markers:
        pytest_args.extend(["-m", args.markers])
        
    if args.keyword:
        pytest_args.extend(["-k", args.keyword])
        
    if args.file:
        pytest_args.append(args.file)
    
    # Run appropriate test suite
    print(f"Running {args.test_type} tests with London School TDD methodology...")
    print("=" * 70)
    
    try:
        if args.test_type == "unit":
            exit_code = run_unit_tests()
        elif args.test_type == "integration":
            exit_code = run_integration_tests()
        elif args.test_type == "e2e":
            exit_code = run_e2e_tests()
        elif args.test_type == "performance":
            exit_code = run_performance_tests()
        elif args.test_type == "fast":
            exit_code = run_fast_tests()
        elif args.test_type == "coverage":
            exit_code = run_tests_with_coverage()
        elif args.test_type == "behavior":
            exit_code = run_behavior_verification_tests()
        elif args.test_type == "showcase":
            exit_code = run_london_school_showcase()
        elif args.test_type == "all":
            exit_code = run_all_tests()
        else:
            # Custom pytest execution
            exit_code = pytest.main(pytest_args)
            
        print("=" * 70)
        if exit_code == 0:
            print("✅ All tests passed successfully!")
        else:
            print("❌ Some tests failed. Check output above for details.")
            
        return exit_code
        
    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)