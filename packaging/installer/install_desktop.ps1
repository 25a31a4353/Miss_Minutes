<#
.SYNOPSIS
    packaging/installer/install_desktop.ps1 - Windows Desktop & Start Menu Shortcut Creator.
.DESCRIPTION
    Creates Windows shortcuts for the packaged Miss Minutes application.
    Points to MissMinutes.exe with proper working directory and MissMinutes.ico icon.
#>

[CmdletBinding()]
param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $InstallDir) {
    # Default to dist\MissMinutes if run from project root
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $candidate = Resolve-Path (Join-Path $scriptDir "..\..\dist\MissMinutes") -ErrorAction SilentlyContinue
    if ($candidate -and (Test-Path (Join-Path $candidate "MissMinutes.exe"))) {
        $InstallDir = $candidate.Path
    } else {
        $InstallDir = "$env:LOCALAPPDATA\Programs\MissMinutes"
    }
}

$exePath = Join-Path $InstallDir "MissMinutes.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "MissMinutes.exe not found at '$exePath'. Please build or install the application first."
    exit 1
}

$iconPath = Join-Path $InstallDir "packaging\MissMinutes.ico"
if (-not (Test-Path $iconPath)) {
    $iconPath = $exePath
}

$WshShell = New-Object -ComObject WScript.Shell

# 1. Desktop Shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $desktopPath "Miss Minutes.lnk"
$shortcut = $WshShell.CreateShortcut($desktopLnk)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = "$iconPath, 0"
$shortcut.Description = "Miss Minutes & Jarvis AI Desktop Assistant"
$shortcut.Save()
Write-Host "[OK] Created Desktop shortcut: $desktopLnk"

# 2. Start Menu Shortcut
$startMenuPath = [Environment]::GetFolderPath("Programs")
$startMenuLnk = Join-Path $startMenuPath "Miss Minutes.lnk"
$shortcutSM = $WshShell.CreateShortcut($startMenuLnk)
$shortcutSM.TargetPath = $exePath
$shortcutSM.WorkingDirectory = $InstallDir
$shortcutSM.IconLocation = "$iconPath, 0"
$shortcutSM.Description = "Miss Minutes & Jarvis AI Desktop Assistant"
$shortcutSM.Save()
Write-Host "[OK] Created Start Menu shortcut: $startMenuLnk"

Write-Host "Miss Minutes desktop integration completed successfully."
