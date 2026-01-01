param(
	[Parameter(Mandatory=$true, Position=0)]
	[string]$RemoteUrl,
	[string]$BranchName = "",
	[switch]$SetLocalIdentity
)

if (-not $BranchName) {
	$timestamp = (Get-Date -Format yyyyMMdd-HHmm)
	$BranchName = "feat/bootstrap-$timestamp"
}

Write-Host "Using remote: $RemoteUrl"
Write-Host "Target branch: $BranchName"

# Initialize repo if needed
if (-not (Test-Path -Path .git)) {
	Write-Host "Initializing git repository..."
	git init
}

# Optionally set repo-local identity before commit
if ($SetLocalIdentity) {
	Write-Host "Ensuring repo-local git identity is set..."
	# Determine existing local config (empty if not set)
	$existingName = git config user.name 2>$null
	$existingEmail = git config user.email 2>$null

	if (-not $existingName -or -not $existingEmail) {
		# Prefer env vars if provided
		$name = $env:GIT_USER_NAME
		$email = $env:GIT_USER_EMAIL

		if (-not $name) {
			$name = Read-Host "Enter git user.name for this repo (or set GIT_USER_NAME)"
		}
		if (-not $email) {
			$email = Read-Host "Enter git user.email for this repo (or set GIT_USER_EMAIL)"
		}

		if ($name) { git config user.name "$name" }
		if ($email) { git config user.email "$email" }
		Write-Host "Repo-local identity set to: $name <$email>"
	} else {
		Write-Host "Repo-local identity already present: $existingName <$existingEmail>"
	}
}

# Add origin remote if it does not exist
$existingRemotes = git remote
if (-not ($existingRemotes -match 'origin')) {
	Write-Host "Adding origin remote..."
	git remote add origin $RemoteUrl
} else {
	Write-Host "Remote 'origin' already present. Skipping add."
}

# Try fetching origin (non-fatal)
try {
	git fetch origin
} catch {
	Write-Host "Warning: git fetch origin failed or no origin yet. Continuing..."
}

Write-Host "Validating branch does not already exist locally or remotely..."
# Check local branches
$localExists = git branch --list $BranchName
if ($localExists) {
	Write-Host "Error: local branch '$BranchName' already exists. Aborting."; exit 1
}

# Check remote branches (non-fatal if fetch fails)
try {
	git fetch origin --prune
	$remoteExists = git ls-remote --heads origin $BranchName
	if ($remoteExists) { Write-Host "Error: remote branch '$BranchName' already exists. Aborting."; exit 1 }
} catch {
	Write-Host "Warning: could not check remote branches. Proceeding with local checks only."
}

Write-Host "Creating and switching to branch $BranchName"
git checkout -b $BranchName

Write-Host "Staging changes..."
git add .

# Commit only if there are staged changes
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
	Write-Host "Nothing to commit."
} else {
	git commit -m "Add CI guardrails and PR template for safe A/B autopromote"
}

Write-Host "Pushing branch to origin..."
try {
	git push -u origin $BranchName
} catch {
	Write-Host "git push failed. Please inspect output and push manually."
}
