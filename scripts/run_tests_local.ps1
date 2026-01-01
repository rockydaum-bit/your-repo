try {
    $repoRoot = (& git rev-parse --show-toplevel) 2>$null
} catch {
    $repoRoot = $null
}

if (-not $repoRoot) {
    Write-Error "Failed to determine repository root via 'git rev-parse --show-toplevel'."
    exit 1
}

$repoRoot = $repoRoot.Trim()
Set-Location -Path $repoRoot

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $repoRoot "run_tests_$ts.log"

# Resolve absolute target script path and sanity-check it
$target = Join-Path $repoRoot 'scripts\run_tests.ps1'
if (-not (Test-Path -LiteralPath $target)) {
    Write-Error "Target script not found: $target"
    exit 1
}
if ([IO.Path]::GetExtension($target).ToLower() -ne '.ps1') {
    Write-Error "Target script does not have a .ps1 extension: $target"
    exit 1
}

# Run and capture all output to log and console using explicit powershell.exe
$psexec = 'powershell.exe'
& $psexec -NoProfile -ExecutionPolicy Bypass -File $target *>&1 | Tee-Object -FilePath $log

$ec = $LASTEXITCODE
Write-Output "EXIT_CODE=$ec"
Write-Output "LOG_FILE=$log"

# Print last 120 lines of the log (if present)
if (Test-Path $log) {
    Get-Content -Path $log -Tail 120
} else {
    Write-Warning "Log file not found: $log"
}

exit $ec
