param(
    [switch]$NoInstallPyInstaller
)

$ErrorActionPreference = 'Stop'
Push-Location "$PSScriptRoot\.."

Write-Host '[build_exe] Running build_all.ps1 to produce ui_dist...'
& .\scripts\build_all.ps1

if (-not (Test-Path 'ui_dist')) {
    Write-Error 'ui_dist not found after build_all.ps1. Aborting.'
    Pop-Location
    exit 1
}

Write-Host '[build_exe] Ensuring PyInstaller is available...'
try { & pyinstaller --version > $null 2>&1; $has = $true } catch { $has = $false }
if (-not $has) {
    if ($NoInstallPyInstaller) { Write-Error 'PyInstaller not found (and --NoInstallPyInstaller set).'; Pop-Location; exit 2 }
    Write-Host '[build_exe] Installing PyInstaller into current Python environment...'
    & python -m pip install --upgrade pip pyinstaller
}

Write-Host '[build_exe] Running PyInstaller using textautonomous_node.spec (this may take a while)'
& pyinstaller textautonomous_node.spec
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed with exit code $LASTEXITCODE"; Pop-Location; exit $LASTEXITCODE }

Write-Host '[build_exe] Build complete. Check the dist\ directory for the EXE.'
Pop-Location
