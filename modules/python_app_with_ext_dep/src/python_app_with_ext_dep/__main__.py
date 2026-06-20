"""Main entry point"""

import sys

if sys.argv[0].endswith("__main__.py"):
    sys.argv[0] = "python -m python_app_with_ext_dep"

from python_app_with_ext_dep.app_main import main

main()
