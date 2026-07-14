"""Shared py_test entrypoint: run pytest on this target's bench directory.

The target's runfiles contain only the srcs listed in the BUILD rule, so
collecting the directory picks up exactly this bench (plus conftest.py).
"""

import os
import sys

import pytest

if __name__ == "__main__":
    args = [
        os.path.dirname(__file__),
        # Collect bench_*.py files — pytest's default pattern is test_*.py.
        "-o",
        "python_files=bench_*.py",
        *sys.argv[1:],
    ]
    sys.exit(pytest.main(args))
