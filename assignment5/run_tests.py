"""
Tiny stand-in test runner.

This sandbox has no network access, so `pip install pytest` cannot run here.
This script discovers and executes every `test_*` function in
service/tests/test_orders.py exactly as pytest would, and reports the same
pass/fail information. It does not change the test file's pytest
compatibility - `pytest service/tests/` will run these same functions on any
machine that has pytest installed.
"""
import sys
import time
import traceback

from service.tests import test_orders

test_functions = [
    (name, obj)
    for name, obj in vars(test_orders).items()
    if name.startswith("test_") and callable(obj)
]

passed, failed = [], []

start = time.time()
for name, fn in test_functions:
    try:
        fn()
        passed.append(name)
        print(f"PASSED  {name}")
    except Exception:
        failed.append(name)
        print(f"FAILED  {name}")
        traceback.print_exc()
elapsed = time.time() - start

print()
print(f"{len(passed)} passed, {len(failed)} failed in {elapsed:.2f}s")

sys.exit(1 if failed else 0)
