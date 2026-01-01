[CmdletBinding()]
param()

function Fail([string]$msg, [int]$code = 1) {
    Write-Error $msg
    exit $code
}

# Resolve repo root and cd there
$root = & git rev-parse --show-toplevel 2>$null
if (-not $root) { Fail "Not inside a git repository (git rev-parse --show-toplevel failed)." }
$root = (Resolve-Path -LiteralPath $root).ProviderPath.TrimEnd('\','/')
Set-Location -LiteralPath $root

Write-Host "Repo root: $root"

# Ensure .venv exists
$venvDir = Join-Path $root '.venv'
$pythonExe = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvDir)) {
    Write-Host "Creating venv at $venvDir"
    & py -3 -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create virtual environment (py -3 -m venv). Exit $LASTEXITCODE." }
} else {
    Write-Host "Virtualenv exists: $venvDir"
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Fail "Python executable not found in venv: $pythonExe"
}

# Upgrade pip
Write-Host "Upgrading pip..."
$workdir = [IO.Path]::GetTempPath()
Push-Location -LiteralPath $workdir
& $pythonExe -m pip install --upgrade pip
$pipUpgradeExit = $LASTEXITCODE
Pop-Location
if ($pipUpgradeExit -ne 0) { Fail "Failed to upgrade pip. Exit $pipUpgradeExit." }

# Install requirements.txt if present
$req = Join-Path $root 'requirements.txt'
if (Test-Path -LiteralPath $req) {
    Write-Host "Installing requirements from requirements.txt..."
    Push-Location -LiteralPath $workdir
    & $pythonExe -m pip install -r $req
    $reqExit = $LASTEXITCODE
    Pop-Location
    if ($reqExit -ne 0) { Fail "Failed to install requirements.txt. Exit $reqExit." }
} else {
    Write-Host "No requirements.txt found, skipping."
}

# Ensure pytest installed
Write-Host "Installing pytest..."
Push-Location -LiteralPath $workdir
& $pythonExe -m pip install pytest
$pytestInstallExit = $LASTEXITCODE
Pop-Location
if ($pytestInstallExit -ne 0) { Fail "Failed to install pytest. Exit $pytestInstallExit." }

# 1) Run generator (invoked directly, forwarding -Verbose if present)
$genScript = Join-Path $root 'scripts\generate_repo_inventory.ps1'
if (-not (Test-Path -LiteralPath $genScript)) { Fail "Generator script not found: $genScript" }

Write-Host "Running generator: $genScript"
# Forward -Verbose to generator if caller used -Verbose
if ($PSBoundParameters.ContainsKey('Verbose') -or $VerbosePreference -eq 'Continue') {
    & $genScript -Verbose
} else {
    & $genScript
}
if ($LASTEXITCODE -ne 0) { Fail "Generator script failed (exit $LASTEXITCODE)." }

# 2) Run pytest guardrail (fail-fast)
$testTarget = 'tests/test_repo_inventory_manifest.py'
Write-Host "Running pytest: $testTarget"
& $pythonExe -m pytest -q $testTarget
$pytestExit = $LASTEXITCODE
if ($pytestExit -ne 0) { Fail "pytest failed (exit $pytestExit)." }

Write-Host "All steps completed successfully."
exit 0
