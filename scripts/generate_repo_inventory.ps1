[CmdletBinding()]
param()

function Fail([string]$msg) {
    Write-Error $msg
    exit 2
}

# Resolve repository root
$root = & git rev-parse --show-toplevel 2>$null
if (-not $root) { Fail "Not inside a git repository (git rev-parse --show-toplevel failed)." }
$root = (Resolve-Path -LiteralPath $root).ProviderPath.TrimEnd('\','/')

Set-Location -LiteralPath $root

$repoFileList = 'repo_file_list.txt'
$repoManifest = 'repo_manifest.json'

# Exclusions (case-insensitive, path-segment aware)
$excludedDirSegments = @('build','ui_dist','dist','__pycache__','.pytest_cache','.mypy_cache','node_modules','.venv','.git','.ruff_cache')
$excludedPathFragments = @('data/logs','data/state')
$excludedExts = @('.pyc','.pyo','.exe','.pkg','.pyz','.zip','.tar','.gz')
$excludedExact = @($repoFileList.ToLower(), $repoManifest.ToLower(), '.coverage', '.coverage_threshold', 'config/yt_token.json', 'config/yt_client_secrets.json')

Write-Verbose "Repo root: $root"

# Collect files
Write-Verbose "Scanning files..."
$all = Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue

function Normalize-RelPath([string]$fullpath) {
    $rel = $fullpath.Substring($root.Length).TrimStart('\','/')
    $rel = $rel -replace '\\','/'
    return $rel
}

function Is-Excluded([string]$rel) {
    if (-not $rel) { return $true }
    $lc = $rel.ToLower()
    # exact matches
    foreach ($ex in $excludedExact) { if ($lc -eq $ex.ToLower()) { return $true } }
    # .secrets anywhere
    if ($lc -match '\.secrets') { return $true }
    # repo-root run_tests_*.log files
    if ($lc -match '^run_tests_.*\.log$') { return $true }
    # extensions
    foreach ($ext in $excludedExts) { if ($lc.EndsWith($ext)) { return $true } }
    # excluded repo-root dirs: startswith and segment match
    foreach ($seg in $excludedDirSegments) {
        if ($rel -eq $seg -or $rel.StartsWith($seg + '/')) { return $true }
        if ($lc -match '(?i)(^|/)' + [regex]::Escape($seg) + '(/|$)') { return $true }
    }
    # excluded path fragments (segment aware)
    foreach ($frag in $excludedPathFragments) {
        $fragNorm = $frag.TrimEnd('/')
        if ($rel -eq $fragNorm -or $rel.StartsWith($fragNorm + '/')) { return $true }
        if ($lc -match '(?i)(^|/)' + [regex]::Escape($fragNorm) + '(/|$)') { return $true }
    }
    return $false
}

# Build normalized path list and metadata, detect duplicates
$paths = @()
$meta = @{}
foreach ($f in $all) {
    $rel = Normalize-RelPath $f.FullName
    if (Is-Excluded $rel) { Write-Verbose "Excluded: $rel"; continue }
    if ($paths -contains $rel) { Fail "Duplicate normalized path detected: $rel" }
    $paths += $rel
    $meta[$rel] = $f.FullName
}

# Sort deterministically (do not use Sort-Object -Unique)
$sorted = $paths.Clone()
[Array]::Sort($sorted, [System.StringComparer]::Ordinal)

# Write repo_file_list.txt: all paths, sorted, forward slashes, exactly one LF newline, UTF8 no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$fileListContent = ($sorted -join "`n") + "`n"
[System.IO.File]::WriteAllText((Join-Path $root $repoFileList), $fileListContent, $utf8NoBom)

# Build manifest entries with ordered keys and sort by path
$manifestObjs = @()
foreach ($rel in $sorted) {
    $full = $meta[$rel]
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash
    $entry = [ordered]@{
        path = $rel
        size = [int64]((Get-Item -LiteralPath $full).Length)
        sha256 = $hash
    }
    $manifestObjs += [PSCustomObject]$entry
}

# Convert to JSON and ensure LF newlines and exactly one trailing LF
$json = $manifestObjs | ConvertTo-Json -Depth 5
$json = $json -replace "(`r`n|`r|`n)","`n"
if (-not $json.EndsWith("`n")) { $json += "`n" }
[System.IO.File]::WriteAllText((Join-Path $root $repoManifest), $json, $utf8NoBom)

# Final counts and SHA256
$count = $sorted.Count
$hashFileList = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $repoFileList)).Hash
$hashManifest = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root $repoManifest)).Hash

Write-Output "WROTE: $repoFileList ($count entries)"
Write-Output "WROTE: $repoManifest ($count entries)"
Write-Output "repo_file_list.txt SHA256: $hashFileList"
Write-Output "repo_manifest.json  SHA256: $hashManifest"

# Determinism check (repo-state independent):
# Rebuild content in-memory and ensure it matches what we just wrote.
# This avoids failing just because the repo had outdated committed artifacts.
function Build-InventoryContent {
    param(
        [string[]]$sortedPaths,
        [hashtable]$fullPathMap
    )

    $fileList = ($sortedPaths -join "`n") + "`n"

    $manifest = @()
    foreach ($rel in $sortedPaths) {
        $full = $fullPathMap[$rel]
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash
        $entry = [ordered]@{
            path   = $rel
            size   = [int64]((Get-Item -LiteralPath $full).Length)
            sha256 = $hash
        }
        $manifest += [PSCustomObject]$entry
    }

    $json2 = $manifest | ConvertTo-Json -Depth 5
    $json2 = $json2 -replace "(`r`n|`r|`n)","`n"
    if (-not $json2.EndsWith("`n")) { $json2 += "`n" }

    return [PSCustomObject]@{
        FileList = $fileList
        Json     = $json2
    }
}

$first = Build-InventoryContent -sortedPaths $sorted -fullPathMap $meta

# Read back what we wrote (source of truth)
$writtenFileList = [System.IO.File]::ReadAllText((Join-Path $root $repoFileList), $utf8NoBom)
$writtenJson     = [System.IO.File]::ReadAllText((Join-Path $root $repoManifest), $utf8NoBom)

# Rebuild again (second pass) and compare all three
$second = Build-InventoryContent -sortedPaths $sorted -fullPathMap $meta

if ($first.FileList -ne $writtenFileList -or $first.FileList -ne $second.FileList) {
    Fail "Non-deterministic repo_file_list.txt generation detected."
}
if ($first.Json -ne $writtenJson -or $first.Json -ne $second.Json) {
    Fail "Non-deterministic repo_manifest.json generation detected."
}

Write-Output "determinism: OK (two-pass match)"
exit 0
