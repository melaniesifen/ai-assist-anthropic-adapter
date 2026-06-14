from __future__ import annotations

import sys
import unittest
from pathlib import Path


def load_tests(loader: unittest.TestLoader, standard_tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    tests_dir = Path(__file__).resolve().parent / "tests"
    sys.path.insert(0, str(tests_dir))
    return loader.discover(str(tests_dir), pattern=pattern or "test*.py", top_level_dir=str(tests_dir))
