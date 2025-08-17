#!/usr/bin/env python
"""
Script to run doc agent integration tests with proper setup.
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def run_tests():
    """Run the integration tests."""
    print("=" * 80)
    print("DOC AGENT INTEGRATION TEST SUITE")
    print("=" * 80)
    
    # Set test environment variables
    test_env = os.environ.copy()
    test_env.update({
        "TESTING_MODE": "true",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "OPENAI_API_KEY": "test-key",
        "GITHUB_TOKEN": "test-token",
        "SLACK_BOT_TOKEN": "test-token",
        "SUPABASE_URL": os.getenv("SUPABASE_URL", "https://test.supabase.co"),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY", "test-key"),
    })
    
    # Test categories
    test_suites = {
        "Unit Tests": [
            "tests/unit/doc_agent/test_auto_doc_client.py",
            "tests/unit/doc_agent/test_auto_doc_client_comprehensive.py",
        ],
        "Integration Tests": [
            "tests/integration/test_doc_agent_workflow.py",
            "tests/integration/test_doc_agent_comprehensive.py",
        ],
    }
    
    results = {}
    
    for suite_name, test_files in test_suites.items():
        print(f"\n{suite_name}")
        print("-" * 40)
        
        for test_file in test_files:
            if not Path(test_file).exists():
                print(f"  ⚠️  {test_file} - NOT FOUND")
                continue
            
            # Run pytest for this file
            cmd = [
                sys.executable, "-m", "pytest",
                test_file,
                "-v",
                "--tb=short",
                "--no-header",
                "-q"
            ]
            
            result = subprocess.run(
                cmd,
                env=test_env,
                capture_output=True,
                text=True
            )
            
            # Parse results
            if result.returncode == 0:
                # Count passed tests
                passed = result.stdout.count(" PASSED")
                print(f"  ✅ {test_file} - {passed} tests passed")
                results[test_file] = {"status": "passed", "count": passed}
            elif "no tests collected" in result.stdout or "no tests collected" in result.stderr:
                print(f"  ⚠️  {test_file} - No tests collected")
                results[test_file] = {"status": "no_tests", "count": 0}
            else:
                # Count failures
                failed = result.stdout.count(" FAILED") + result.stdout.count(" ERROR")
                print(f"  ❌ {test_file} - {failed} tests failed")
                results[test_file] = {"status": "failed", "count": failed}
                
                # Show error details
                if "--tb=short" in cmd:
                    error_lines = result.stdout.split("\n")
                    for line in error_lines:
                        if "ERROR" in line or "FAILED" in line or "ImportError" in line:
                            print(f"      {line}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_passed = sum(r["count"] for r in results.values() if r["status"] == "passed")
    total_failed = sum(r["count"] for r in results.values() if r["status"] == "failed")
    total_no_tests = sum(1 for r in results.values() if r["status"] == "no_tests")
    
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")
    print(f"Files with no tests: {total_no_tests}")
    
    if total_failed > 0:
        print("\n⚠️  Some tests failed. Run with pytest directly for detailed output:")
        print("    pytest tests/integration/test_doc_agent_comprehensive.py -xvs")
        return 1
    elif total_no_tests > 0:
        print("\n⚠️  Some test files have no tests collected. Check test class structure.")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(run_tests())