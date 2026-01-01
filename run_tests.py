import os
import subprocess
import json
import glob
import sys
import shutil
from pathlib import Path

def run_jest_suite(suite_name, test_paths):
    out_file = f'.jest-{suite_name.lower().replace("/", "-")}.json'
    JEST_CONFIG_PATH = 'typescript/jest.config.js'
    # Check if npx is available
    if shutil.which('npx') is None:
        print("ERROR: 'npx' command not found. Please ensure Node.js and npx are installed and in your PATH.")
        return 0, 0, 1
    cmd = [
        'npx', 'jest',
        '--config', JEST_CONFIG_PATH,
        '--json', f'--outputFile={out_file}',
        *test_paths
    ]
    print(f"\n=== Running {suite_name} Suite ===")
    try:
        # Ensure PYTHONPATH includes the python directory
        env = os.environ.copy()
        python_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'python'))
        env['PYTHONPATH'] = python_dir + (os.pathsep + env['PYTHONPATH'] if 'PYTHONPATH' in env else '')
        subprocess.run(cmd, check=True, shell=True, env=env)
        with open(out_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
        test_results = result.get('testResults', [])
        total = sum(len(tr['assertionResults']) for tr in test_results)
        passed = sum(
            sum(1 for r in tr['assertionResults'] if r['status'] == 'passed')
            for tr in test_results
        )
        failed = sum(
            sum(1 for r in tr['assertionResults'] if r['status'] == 'failed')
            for tr in test_results
        )
        print(f"{suite_name} Suite: {'PASS' if failed == 0 else 'FAIL'}")
        print(f"  Passed: {passed}/{total}")
        if failed:
            print(f"  Failed: {failed}")
        return total, passed, failed
    except subprocess.CalledProcessError:
        print(f"{suite_name} Suite: ERROR (could not run)")
        return 0, 0, 1

def run_pytest_suite(suite_name, test_paths):
    out_file = '.pytest.json'
    print(f"\n=== Running {suite_name} Suite (pytest) ===")
    # --json-report requires pytest-json-report plugin. --tb=short for concise output.
    # If test_paths is empty or None, default to ['python/tests']
    if not test_paths:
        test_paths = ['python/tests']
    cmd = [
        sys.executable, '-m', 'pytest', *test_paths,
        '--json-report', f'--json-report-file={out_file}', '--tb=short'
    ]
    try:
        # Ensure PYTHONPATH includes the python directory
        env = os.environ.copy()
        python_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'python'))
        env['PYTHONPATH'] = python_dir + (os.pathsep + env['PYTHONPATH'] if 'PYTHONPATH' in env else '')
        subprocess.run(cmd, check=True, shell=True, env=env)
        with open(out_file, 'r', encoding='utf-8') as f:
            rep = json.load(f)
        summary = rep.get('summary', {})
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        total = summary.get('total', 0)
        print(f"{suite_name} Suite: {'PASS' if failed == 0 else 'FAIL'}")
        print(f"  Passed: {passed}/{total}")
        if failed:
            print(f"  Failed: {failed}")
        return total, passed, failed
    except subprocess.CalledProcessError:
        print(f"{suite_name} Suite: ERROR (could not run)")
        return 0, 0, 1

if __name__ == '__main__':
    print("\n===== TEST SUITE SUMMARY =====\n")
    ts_test_dir = os.path.normpath(os.path.abspath(os.path.join('typescript', 'tests', 'imperial_generals')))
    ts_all_tests = [os.path.normpath(p) for p in glob.glob(os.path.join(ts_test_dir, '*.test.ts'))]

    py_test_dir = os.path.normpath(os.path.abspath(os.path.join('python', 'tests')))
    py_all_tests = [os.path.normpath(p) for p in glob.glob(os.path.join(py_test_dir, '*.py'))]

    total_overall = passed_overall = failed_overall = 0
    # Run TypeScript test suites
    total, passed, failed = run_jest_suite('Typescript', ts_all_tests)
    total_overall += total
    passed_overall += passed
    failed_overall += failed

    # Run Python test suite
    total, passed, failed = run_pytest_suite('Python', py_all_tests)
    total_overall += total
    passed_overall += passed
    failed_overall += failed

    print("\n=== OVERALL SUMMARY ===")
    print(f"  Passed: {passed_overall}/{total_overall}")
    if failed_overall != 0:
        print("Some tests FAILED.  (See above output)")

    print(f"\nTest run completed at: {__import__('datetime').datetime.now()}\n")
