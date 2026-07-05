load("@rules_python//python:pip.bzl", "compile_pip_requirements")
load("@rules_uv//uv:venv.bzl", "create_venv")

# This target generates requirements_lock.txt file based on requirements.in.
compile_pip_requirements(
    name = "generate_requirements_lock",
    extra_args = [
        "--allow-unsafe",
        "--no-emit-index-url",
        "--upgrade",
    ],
    requirements_in = "requirements.in",
    requirements_txt = "requirements_lock.txt",
    tags = ["manual"],
)

# rules_uv virtual environment support to enable seamless development experience
# and easy virtual environment management via Bazel.

create_venv(
    name = "generate_virtual_env",
    destination_folder = ".venv",
    requirements_txt = "requirements_lock.txt",
)
