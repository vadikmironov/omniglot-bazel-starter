"""Main entry point"""

import platform
import sys

if sys.argv[0].endswith("__main__.py"):
    sys.argv[0] = "python -m python_app"

from python_app.app_main import main

print(f">> using python {platform.python_version()}")
print(f">> located at {sys.executable}")

main()
