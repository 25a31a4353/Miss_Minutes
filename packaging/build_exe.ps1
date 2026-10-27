# packaging/build_exe.ps1 - Builds MissMinutes.exe using PyInstaller
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$buildDir = Join-Path $env:USERPROFILE ".miss_minutes\build_dist"
$workDir = Join-Path $env:USERPROFILE ".miss_minutes\build_work"

if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
if (Test-Path $workDir) { Remove-Item -Recurse -Force $workDir }

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

Write-Host "Running PyInstaller outside OneDrive..."
& pyinstaller --clean --noconfirm --distpath $buildDir --workpath $workDir packaging\MissMinutes.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Mirroring build to dist\MissMinutes..."
$destDir = Join-Path $repoRoot "dist\MissMinutes"
& robocopy (Join-Path $buildDir "MissMinutes") $destDir /MIR /R:2 /W:1
$rc = $LASTEXITCODE
if ($rc -ge 8) {
    Write-Error "Robocopy failed with code $rc"
    exit $rc
}

Write-Host "Packaged build complete: dist\MissMinutes\MissMinutes.exe"
exit 0
