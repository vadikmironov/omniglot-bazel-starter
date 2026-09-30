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
rem
rem Fast path: with no netrc file there is nothing to look up, so answer here.
rem Bazel asks for every host, the remote cache included, and starting
rem PowerShell on a loaded runner can outlast --credential_helper_timeout,
rem which fails the build. The path rules match credential-helper.ps1: NETRC,
rem else .netrc under HOME, else under USERPROFILE.
rem
rem Single-line ifs only. No goto: cmd.exe can miss a label in a file checked
rem out with LF endings. No blocks: a ")" in a path would close one early.
setlocal
set "NETRC_FILE=%NETRC%"
if not defined NETRC_FILE if defined HOME set "NETRC_FILE=%HOME%\.netrc"
if not defined NETRC_FILE if defined USERPROFILE set "NETRC_FILE=%USERPROFILE%\.netrc"
set "HAVE_NETRC="
if defined NETRC_FILE if exist "%NETRC_FILE%" set "HAVE_NETRC=1"
if defined HAVE_NETRC powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0credential-helper.ps1" %* & exit /b

rem Read the request to the end first, so Bazel's write never hits a closed pipe.
more >nul
echo {"headers":{}}
exit /b 0
