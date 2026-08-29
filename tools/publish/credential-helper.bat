@echo off
rem Windows entry point for the credential helper.
rem
rem Bazel launches the helper with CreateProcessW, which cannot run a shebang
rem script or a .ps1 directly: it fails with "%1 is not a valid Win32
rem application" (error 193). So --credential_helper points here, and this
rem hands off to the PowerShell implementation.
rem
rem PowerShell rather than Git Bash: the helper runs during fetch, before Bazel
rem has resolved a shell toolchain, so it must not depend on bash being on PATH.
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0credential-helper.ps1" %*
