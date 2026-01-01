# Build UI and copy to backend ui_dist
Set-StrictMode -Version Latest

Push-Location "$PSScriptRoot\..\ui"
Write-Host "Running npm install (if needed) and build..."
npm install
npm run build

$dist = Join-Path (Get-Location) 'dist'
if (-not (Test-Path $dist)) {
    Write-Error "ui/dist not found after build"
    Pop-Location
    exit 1
}

$target = Join-Path "$PSScriptRoot\.." 'ui_dist'
if (Test-Path $target) {
    Remove-Item -Recurse -Force $target
}

Write-Host "Copying built UI to $target"
Copy-Item -Recurse -Force $dist $target
Pop-Location
Write-Host "Build complete. ui_dist is ready in backend root."