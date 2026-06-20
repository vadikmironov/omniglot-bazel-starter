"""
This module contains mypy_aspect definition, please refer to the rules_mypy documentation here:
https://github.com/theoremlp/rules_mypy/blob/main/readme.md
"""

load("@mypy_pip_types//:types.bzl", "types")
load("@rules_mypy//mypy:mypy.bzl", "mypy")

mypy_aspect = mypy(
    # the use of local mypy package requires same python runtime
    # as used by rules_mypy (3.12 currently)
    #mypy_cli = "//tools/python/mypy:mypy_cli",
    mypy_ini = Label("//:mypy_config"),
    types = types,
)
