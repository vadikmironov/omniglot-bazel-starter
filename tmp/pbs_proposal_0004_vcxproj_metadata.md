# Derive Windows PYTHON.json metadata from MSBuild, as #1237 did for Unix

Follow-up in the direction of #1237 ("Derive PYTHON.json from build artifacts"), which replaced hand-maintained Unix extension metadata with values parsed from the configured Setup files, `config.c` and the Makefile. Windows still hardcodes its equivalents.

## Current state

`cpython-windows/build.py` gets its metadata three ways, and acknowledges two of them as temporary:

```python
# We hack up pythoncore.vcxproj and the list in it when this function
# runs isn't totally accurate. We hardcode the list from the CPython
# distribution.
# TODO pull from unaltered file
res["core"]["links"] = [ ... ]
```

```python
RE_ADDITIONAL_DEPENDENCIES = re.compile(
    "<AdditionalDependencies>([^<]+)</AdditionalDependencies>"
)
```

The regex reads one element from one line, so it cannot expand properties or evaluate conditions. That is why `ignore_additional_depends` has to carry the raw MSBuild string rather than a filename:

```python
"_lzma": {
    "ignore_additional_depends": {"$(OutDir)liblzma$(PyDebugExt).lib"},
},
```

`CONVERT_TO_BUILTIN_EXTENSIONS` and `EXTENSION_TO_LIBRARY_DOWNLOADS_ENTRY` are curated by hand for the same reason.

## Why the Unix approach does not port directly

A Makefile is a *post-configure* artifact: variables are already expanded and conditionals already resolved, so parsing it yields concrete values. A `.vcxproj` is the opposite — a pre-evaluation template of `$(OutDir)`, `$(PyDebugExt)` and `Condition="'$(Configuration)'=='Debug'"`.

Parsing the project file as XML would therefore mean reimplementing MSBuild evaluation: the `msbuild/2003` namespace, property expansion (the counterpart of #1237's `_expand_makefile_variables`), imports, and condition evaluation. That is where the cost stops being worth it.

## Proposal

Ask MSBuild for the evaluated values instead of inferring them. `-getProperty:` and `-getItem:` emit JSON, and `-preprocess` inlines all imports:

```
msbuild pcbuild.proj /p:Configuration=Debug /p:Platform=x64 \
        -getItem:Link -getProperty:TargetName,OutDir
```

Run per configuration, this returns values with properties expanded and conditions resolved. It is the real analogue of reading a post-configure Makefile, and it reimplements nothing: MSBuild is already invoked by `run_msbuild`, so the dependency is present.

Doing so would let `res["core"]["links"]`, the `AdditionalDependencies` regex and the `$(PyDebugExt)` literal in `ignore_additional_depends` all be replaced by evaluated data, and would make the artifact naming configuration-aware rather than hardcoded per build type.

## Smaller precursor

The `TODO pull from unaltered file` is not blocked on any of the above. `hack_project_files` mutates `pythoncore.vcxproj` before `collect_python_build_artifacts` reads it, so the immediate defect is staleness rather than parsing. Snapshotting the pristine project file before the hacking step would resolve that TODO on its own, and is worth doing first.

## Status

Recorded for later. Not to be filed upstream until there is an implementation behind it — the value of the proposal is in the code, and the maintainers have just shipped the Unix half themselves.
