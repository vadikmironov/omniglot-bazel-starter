# Windows implementation of the Bazel credential helper protocol.
#
# Mirrors tools/publish/credential-helper (bash) + netrc_lib.sh: reads a JSON
# request from stdin, extracts the URI's host, looks it up in ~/.netrc and
# writes HTTP headers as JSON on stdout.
#
# PowerShell rather than a bash shim: Bazel invokes the helper during fetch,
# before it has resolved any shell toolchain, so the bootstrap path must not
# depend on Git Bash being installed and on PATH. Windows PowerShell is always
# present.
#
# Keep this in step with the bash implementation: the two are expected to
# return the same output for the same input.
#
# Compatibility target: Windows PowerShell 5.1, which is what `powershell`
# resolves to (the .bat does not call pwsh). Constraints, extended as they
# surface:
#   1. ASCII only. 5.1 reads a BOM-less .ps1 as ANSI where 7 reads UTF-8.
#      UTF-8 with a BOM also works in 5.1, but BOMs break Unix tooling.
#      https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding

$ErrorActionPreference = 'Stop'

function Get-NetrcCredential {
    param([string]$TargetHost)

    $result = @{ Login = ''; Password = '' }

    $netrc = $env:NETRC
    if (-not $netrc) {
        $home_ = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
        if (-not $home_) { return $result }
        $netrc = Join-Path $home_ '.netrc'
    }
    if (-not (Test-Path -LiteralPath $netrc -PathType Leaf)) { return $result }

    $inMachine = $false
    foreach ($rawLine in [IO.File]::ReadAllLines($netrc)) {
        $line = $rawLine.Trim()
        if ($line -eq '') { continue }
        if ($line.StartsWith('#')) { continue }

        $tokens = $line -split '\s+'
        $i = 0
        while ($i -lt $tokens.Count) {
            # if/elseif with -ceq rather than switch: switch matches
            # case-insensitively, where the bash `case` does not, and quoting
            # the 'default' keyword inside a switch is needlessly subtle.
            $token = $tokens[$i]
            if ($token -ceq 'machine') {
                $next = if ($i + 1 -lt $tokens.Count) { $tokens[$i + 1] } else { '' }
                $inMachine = ($next -ceq $TargetHost)
                $i += 2
            }
            elseif ($token -ceq 'default') {
                # Only a fallback: a machine entry that already matched wins.
                $inMachine = ($result.Login -eq '')
                $i += 1
            }
            elseif ($token -ceq 'login') {
                if ($inMachine -and ($i + 1 -lt $tokens.Count)) { $result.Login = $tokens[$i + 1] }
                $i += 2
            }
            elseif ($token -ceq 'password') {
                if ($inMachine -and ($i + 1 -lt $tokens.Count)) { $result.Password = $tokens[$i + 1] }
                $i += 2
            }
            else {
                $i += 1
            }
        }
    }
    return $result
}

$empty = '{"headers":{}}'
$request = [Console]::In.ReadToEnd()

$match = [regex]::Match($request, '"uri"\s*:\s*"([^"]*)"')
if (-not $match.Success -or $match.Groups[1].Value -eq '') {
    [Console]::Out.Write($empty)
    exit 0
}

$uri = $match.Groups[1].Value
$targetHost = ($uri -replace '^https?://', '')
$targetHost = ($targetHost -split '/')[0]
$targetHost = ($targetHost -split ':')[0]

$cred = Get-NetrcCredential -TargetHost $targetHost
if ($cred.Login -eq '' -or $cred.Password -eq '') {
    [Console]::Out.Write($empty)
    exit 0
}

$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$($cred.Login):$($cred.Password)"))
[Console]::Out.Write("{`"headers`":{`"Authorization`":[`"Basic $encoded`"]}}")
