#!/usr/bin/env bash
# Runs under `bazel run` from the runfiles tree; BUILD_WORKSPACE_DIRECTORY is the source root.
set -euo pipefail

uv="$(realpath "{{uv}}")"
python="$(realpath "{{python}}")"
project="${BUILD_WORKSPACE_DIRECTORY}/{{project_dir}}"
venv="${BUILD_WORKSPACE_DIRECTORY}/{{destination_folder}}"

UV_PROJECT_ENVIRONMENT="${venv}" "${uv}" sync \
    --project "${project}" \
    --python "${python}" \
    --no-python-downloads \
    --all-groups \
    --locked \
    --no-progress

echo "Created ${venv}; activate with: source {{destination_folder}}/bin/activate"
