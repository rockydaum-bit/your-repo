param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("brain","worker")]
    [string]$Role,

    [string]$InstallRoot = "C:\TextAutonomous",
    [string]$NodeName = $env:COMPUTERNAME
)

Write-Host "Installing TextAutonomous node as role '$Role' to '$InstallRoot'..."

# 1) Create target directory
New-Item -ItemType Directory -Path $InstallRoot -ErrorAction SilentlyContinue | Out-Null

# 2) Copy EXE and config templates
$sourceRoot = "D:\textautonomous_media_engine"
$distExe    = Join-Path $sourceRoot "dist\textautonomous_node.exe"

if (-not (Test-Path $distExe)) {
    Write-Error "Executable not found at $distExe. Build it first with scripts\build_exe.ps1."
    exit 1
}

Copy-Item $distExe (Join-Path $InstallRoot "textautonomous_node.exe") -Force

# copy base config folder (if you want all configs)
if (Test-Path (Join-Path $sourceRoot "config")) {
    Copy-Item (Join-Path $sourceRoot "config") $InstallRoot -Recurse -Force
}

# 3) Choose config file for this role
$configPath = if ($Role -eq "brain") {
    Join-Path $InstallRoot "config\engine-brain.yaml"
} else {
    Join-Path $InstallRoot "config\engine-worker.yaml"
}

if (-not (Test-Path $configPath)) {
    Write-Warning "Expected config file not found: $configPath. Please create or adjust it."
}

# 4) Create a simple run script for this node
$runScript = @"
`$env:ENGINE_CONFIG_PATH = '$configPath'
`$env:ENGINE_ROLE = '$Role'
`$env:WORKER_ID = '$NodeName'
Start-Process -FilePath (Join-Path '$InstallRoot' 'textautonomous_node.exe') -WorkingDirectory '$InstallRoot'
"@

$runScriptPath = Join-Path $InstallRoot "run_node_$Role.ps1"
$runScript | Set-Content -Path $runScriptPath -Encoding UTF8

Write-Host "Created run script: $runScriptPath"

Write-Host "Installation complete. To start this node:"
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$runScriptPath`""
