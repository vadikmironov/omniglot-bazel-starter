<#
.SYNOPSIS
    Downloads and installs Amazon Corretto JDK toolchains for Windows.

.DESCRIPTION
    This script downloads and installs Amazon Corretto JDK versions (8, 11, 17, 21, 25)
    for Windows, validates checksums, extracts archives, and creates symbolic links.

.PARAMETER ToolchainRootPath
    Directory where JDK toolchains will be downloaded and extracted.
    Alias: -r

.EXAMPLE
    .\local_corretto_toolchains_setup.ps1 --toolchain_root_path C:\jdk_toolchains
    .\local_corretto_toolchains_setup.ps1 -r C:\jdk_toolchains
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [Alias("r")]
    [Alias("toolchain_root_path")]
    [string]$ToolchainRootPath = ""
)

$ErrorActionPreference = "Stop"

$ScriptName = $MyInvocation.MyCommand.Name

function Show-Usage {
    Write-Host "Usage: $ScriptName -ToolchainRootPath PATH | -r PATH"
    Write-Host "  -ToolchainRootPath, -r PATH: Directory where JDK toolchains will be downloaded and extracted"
    exit 1
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

function Write-ErrorAndExit {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] ERROR: $Message" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrEmpty($ToolchainRootPath)) {
    Write-ErrorAndExit "toolchain_root_path argument is required, call with --help for usage"
}

Write-Log "Creating toolchain root directory: $ToolchainRootPath"
try {
    if (-not (Test-Path $ToolchainRootPath)) {
        New-Item -ItemType Directory -Path $ToolchainRootPath -Force | Out-Null
    }
} catch {
    Write-ErrorAndExit "Failed to create directory: $ToolchainRootPath - $_"
}

Set-Location $ToolchainRootPath

function Get-Platform {
    $arch = [System.Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")

    switch ($arch) {
        "AMD64" { return "windows-x64" }
        default { Write-ErrorAndExit "Unsupported Windows architecture: $arch (only x86_64/AMD64 is supported)" }
    }
}

$Platform = Get-Platform
Write-Log "Detected platform: $Platform"

# Define JDK URLs
$Java8Urls = @{
    "windows-x64-archive" = "https://corretto.aws/downloads/latest/amazon-corretto-8-x64-windows-jdk.zip"
    "windows-x64-checksum" = "https://corretto.aws/downloads/latest_checksum/amazon-corretto-8-x64-windows-jdk.zip"
}

$Java11Urls = @{
    "windows-x64-archive" = "https://corretto.aws/downloads/latest/amazon-corretto-11-x64-windows-jdk.zip"
    "windows-x64-checksum" = "https://corretto.aws/downloads/latest_checksum/amazon-corretto-11-x64-windows-jdk.zip"
}

$Java17Urls = @{
    "windows-x64-archive" = "https://corretto.aws/downloads/latest/amazon-corretto-17-x64-windows-jdk.zip"
    "windows-x64-checksum" = "https://corretto.aws/downloads/latest_checksum/amazon-corretto-17-x64-windows-jdk.zip"
}

$Java21Urls = @{
    "windows-x64-archive" = "https://corretto.aws/downloads/latest/amazon-corretto-21-x64-windows-jdk.zip"
    "windows-x64-checksum" = "https://corretto.aws/downloads/latest_checksum/amazon-corretto-21-x64-windows-jdk.zip"
}

$Java25Urls = @{
    "windows-x64-archive" = "https://corretto.aws/downloads/latest/amazon-corretto-25-x64-windows-jdk.zip"
    "windows-x64-checksum" = "https://corretto.aws/downloads/latest_checksum/amazon-corretto-25-x64-windows-jdk.zip"
}

function Get-Jdk {
    param(
        [string]$ArchiveUrl,
        [string]$ChecksumUrl
    )

    $filename = [System.IO.Path]::GetFileName($ArchiveUrl)
    $checksumFile = "$filename.md5"

    Write-Log "Downloading $filename from $ArchiveUrl"
    try {
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $filename -UseBasicParsing
    } catch {
        Write-ErrorAndExit "Failed to download $filename - $_"
    }

    Write-Log "Downloading checksum file $checksumFile from $ChecksumUrl"
    try {
        Invoke-WebRequest -Uri $ChecksumUrl -OutFile $checksumFile -UseBasicParsing
    } catch {
        Write-ErrorAndExit "Failed to download checksum file $checksumFile - $_"
    }
}

function Test-Checksum {
    param(
        [string]$Filename,
        [string]$ChecksumFile
    )

    Write-Log "Validating checksum for $Filename"
    $expectedChecksum = (Get-Content $ChecksumFile -Raw).Trim()
    $actualChecksum = (Get-FileHash -Path $Filename -Algorithm MD5).Hash.ToLower()

    if ($expectedChecksum -ne $actualChecksum) {
        Write-ErrorAndExit "Checksum validation failed for $Filename (expected: $expectedChecksum, got: $actualChecksum)"
    }
    Write-Log "Checksum validation passed for $Filename"
}

function Expand-Jdk {
    param(
        [string]$Filename,
        [string]$Version
    )

    Write-Log "Extracting $Filename"

    if ($Filename -match "\.zip$") {
        try {
            Expand-Archive -Path $Filename -DestinationPath "." -Force
        } catch {
            Write-ErrorAndExit "Failed to extract $Filename - $_"
        }
    } else {
        Write-ErrorAndExit "Unsupported archive format: $Filename"
    }

    # Find extracted directory - handle different naming conventions
    # Java 8 uses jdk1.8.0_*, Java 11+ uses jdk11.*, jdk17.*, etc.
    $searchPattern = switch ($Version) {
        "8" { "jdk1.8*" }
        default { "jdk$Version.*" }
    }

    $extractedDir = Get-ChildItem -Directory | Where-Object {
        $_.Name -like "*corretto*$Version*" -or
        $_.Name -like $searchPattern -or
        $_.Name -like "jdk-$Version*" -or
        $_.Name -like "amazon-corretto-$Version*"
    } | Sort-Object LastWriteTime -Descending | Select-Object -First 1

    if ($null -eq $extractedDir) {
        Write-ErrorAndExit "Could not find extracted directory for version $Version"
    }

    Write-Log "Found extracted directory: $($extractedDir.Name)"
    return $extractedDir.Name
}

function New-Symlink {
    param(
        [string]$Version,
        [string]$ExtractedDir
    )

    $symlinkName = "amazon_corretto_jdk_${Version}_latest"

    if (Test-Path $symlinkName) {
        Remove-Item -Path $symlinkName -Force -Recurse
    }

    try {
        # Try directory junction first (works for local Windows paths)
        $result = cmd /c mklink /J $symlinkName $ExtractedDir 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Created junction: $symlinkName -> $ExtractedDir"
        } else {
            # Fall back to PowerShell symbolic link (requires admin or developer mode)
            New-Item -ItemType SymbolicLink -Path $symlinkName -Target $ExtractedDir -Force | Out-Null
            Write-Log "Created symlink: $symlinkName -> $ExtractedDir"
        }
    } catch {
        # As a last resort, just copy the directory (slower but always works)
        try {
            Copy-Item -Path $ExtractedDir -Destination $symlinkName -Recurse -Force
            Write-Log "Created copy (symlink unavailable): $symlinkName from $ExtractedDir"
        } catch {
            Write-ErrorAndExit "Failed to create symlink or copy: $_"
        }
    }
}

function Remove-TempFiles {
    param(
        [string]$Filename,
        [string]$ChecksumFile
    )

    Write-Log "Cleaning up downloaded files"
    try {
        if (Test-Path $Filename) { Remove-Item $Filename -Force }
        if (Test-Path $ChecksumFile) { Remove-Item $ChecksumFile -Force }
    } catch {
        Write-Log "Warning: Failed to clean up some files"
    }
}

function Install-Jdk {
    param(
        [string]$Version,
        [hashtable]$Urls
    )

    $archiveKey = "$Platform-archive"
    $checksumKey = "$Platform-checksum"

    if (-not $Urls.ContainsKey($archiveKey)) {
        Write-Log "Skipping Java $Version - no archive URL for platform $Platform"
        return
    }

    $archiveUrl = $Urls[$archiveKey]
    $checksumUrl = $Urls[$checksumKey]
    $filename = [System.IO.Path]::GetFileName($archiveUrl)
    $checksumFile = "$filename.md5"

    Write-Log "Processing Java $Version for $Platform"

    Get-Jdk -ArchiveUrl $archiveUrl -ChecksumUrl $checksumUrl
    Test-Checksum -Filename $filename -ChecksumFile $checksumFile
    $extractedDir = Expand-Jdk -Filename $filename -Version $Version
    New-Symlink -Version $Version -ExtractedDir $extractedDir
    Remove-TempFiles -Filename $filename -ChecksumFile $checksumFile

    Write-Log "Successfully installed Java $Version"
}

$Versions = @{
    "8" = $Java8Urls
    "11" = $Java11Urls
    "17" = $Java17Urls
    "21" = $Java21Urls
    "25" = $Java25Urls
}

Write-Log "Starting JDK installation process"

foreach ($version in @("8", "11", "17", "21", "25")) {
    Install-Jdk -Version $version -Urls $Versions[$version]
}

Write-Log "All JDK versions processed successfully"
Write-Log "Installation directory: $ToolchainRootPath"
Write-Log "Available JDK installations:"

Get-ChildItem -Directory -Filter "amazon*" | Sort-Object Name | ForEach-Object { Write-Host $_.FullName }
