"""Main entry point"""

import platform
import sys

if sys.argv[0].endswith("__main__.py"):
    sys.argv[0] = "python -m cpp_py_ext_module"

from cpp_py_ext_module.app_main import main

print(f">> using python {platform.python_version()}")
print(f">> located at {sys.executable}")

main()
