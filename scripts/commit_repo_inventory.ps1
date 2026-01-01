[CmdletBinding()]
param()

function ErrExit([string]$msg, [int]$code = 1) {
    Write-Error $msg
    exit $code
}

# Resolve repo root
$root = & git rev-parse --show-toplevel 2>$null
if (-not $root) { ErrExit "Not inside a git repository (git rev-parse --show-toplevel failed)." }
$root = (Resolve-Path -LiteralPath $root).ProviderPath.TrimEnd('\','/')
Set-Location -LiteralPath $root

# Ensure generator exists
$genScript = Join-Path $root 'scripts/generate_repo_inventory.ps1'
if (-not (Test-Path -LiteralPath $genScript)) { ErrExit "Required script not found: scripts/generate_repo_inventory.ps1" }

# Run generator
Write-Output "Running $genScript..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $genScript
if ($LASTEXITCODE -ne 0) { ErrExit "scripts/generate_repo_inventory.ps1 failed (exit code $LASTEXITCODE)." }

# Ensure generated files exist
$filesToAdd = @('repo_file_list.txt','repo_manifest.json')
foreach ($f in $filesToAdd) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $f))) { ErrExit "Expected generated file not found: $f" }
}

# Stage files
Write-Output 'Staging generated files...'
& git add -- repo_file_list.txt repo_manifest.json
if ($LASTEXITCODE -ne 0) { ErrExit "git add failed (exit code $LASTEXITCODE)." }

# Detect in-progress operations and refuse to proceed
$gitDir = Join-Path $root '.git'
if (Test-Path (Join-Path $gitDir 'MERGE_HEAD')) { ErrExit 'Refusing to commit: .git/MERGE_HEAD present (merge in progress).' }
if (Test-Path (Join-Path $gitDir 'CHERRY_PICK_HEAD')) { ErrExit 'Refusing to commit: .git/CHERRY_PICK_HEAD present (cherry-pick in progress).' }
if (Test-Path (Join-Path $gitDir 'rebase-apply')) { ErrExit 'Refusing to commit: .git/rebase-apply present (rebase in progress).' }
if (Test-Path (Join-Path $gitDir 'rebase-merge')) { ErrExit 'Refusing to commit: .git/rebase-merge present (rebase in progress).' }

# Commit with retry for missing identity only
$commitMessage = 'chore: add filtered repo manifest and file list'
$attempt = 0
$maxAttempts = 2
$didSetLocalIdentity = $false

while ($attempt -lt $maxAttempts) {
    $attempt++
    Write-Output "git commit attempt #$attempt..."
    $output = & git commit -m $commitMessage 2>&1
    $exit = $LASTEXITCODE
    if ($exit -eq 0) { Write-Output 'Commit succeeded.'; exit 0 }

    $outStr = ($output -join "`n")
    # detect missing identity message or unset config
    $hasUserName = (& git config --get user.name 2>$null) -ne $null -and (& git config --get user.name 2>$null) -ne ''
    $hasUserEmail = (& git config --get user.email 2>$null) -ne $null -and (& git config --get user.email 2>$null) -ne ''
    if (-not $didSetLocalIdentity -and (-not ($hasUserName -and $hasUserEmail) -or ($outStr -match 'Please tell me who you are' -or $outStr -match 'unable to auto-detect email address'))) {
        Write-Output 'Commit failed due to missing git identity; setting local identity and retrying once...'
        & git config user.name 'Local Automation'
        & git config user.email 'automation@local'
        if ($LASTEXITCODE -ne 0) { ErrExit 'Failed to set local git identity.' }
        $didSetLocalIdentity = $true
        continue
    }

    # Other failures: print diagnostics and exit non-zero
    Write-Output "Commit failed. Diagnostics:";
    Write-Output '--- git status --porcelain=v1 -b ---'
    & git status --porcelain=v1 -b
    Write-Output '--- git diff --name-only --cached ---'
    & git diff --name-only --cached
    Write-Output '--- git commit output ---'
    Write-Output $output
    ErrExit "Commit failed (exit code $exit). See diagnostics above."
}

ErrExit 'Commit did not succeed after retries.'
