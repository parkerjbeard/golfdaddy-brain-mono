#!/usr/bin/env python3
"""
Test runner for semantic search feature tests.

Usage:
    python tests/run_semantic_tests.py              # Run all semantic tests
    python tests/run_semantic_tests.py unit         # Run only unit tests
    python tests/run_semantic_tests.py integration  # Run only integration tests
    python tests/run_semantic_tests.py coverage     # Run with coverage report
"""
import sys
import subprocess
import os


def run_tests(test_type="all"):
    """Run semantic search tests."""
    test_paths = {
        "unit": [
            "tests/unit/services/semantic/test_embedding_service.py",
            "tests/unit/services/semantic/test_context_analyzer.py",
            "tests/unit/services/semantic/test_semantic_search_service.py",
            "tests/unit/doc_agent/test_auto_doc_client_semantic.py"
        ],
        "integration": [
            "tests/integration/test_semantic_search_integration.py"
        ]
    }
    
    if test_type == "all":
        paths = test_paths["unit"] + test_paths["integration"]
    elif test_type in test_paths:
        paths = test_paths[test_type]
    else:
        print(f"Unknown test type: {test_type}")
        return 1
    
    # Run pytest with verbose output
    cmd = ["pytest", "-v", "--tb=short"] + paths
    
    print(f"Running {test_type} tests for semantic search features...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")
    return result.returncode


def run_with_coverage():
    """Run tests with coverage report."""
    cmd = [
        "pytest",
        "--cov=app.services.embedding_service",
        "--cov=app.services.context_analyzer",
        "--cov=app.services.semantic_search_service",
        "--cov=doc_agent.client",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v"
    ] + [
        "tests/unit/services/semantic/",
        "tests/unit/doc_agent/test_auto_doc_client_semantic.py",
        "tests/integration/test_semantic_search_integration.py"
    ]
    
    print("Running semantic search tests with coverage...")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")
    
    if result.returncode == 0:
        print("\nCoverage report generated in htmlcov/index.html")
    
    return result.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "coverage":
            return run_with_coverage()
        else:
            return run_tests(arg)
    else:
        return run_tests()


if __name__ == "__main__":
    sys.exit(main())