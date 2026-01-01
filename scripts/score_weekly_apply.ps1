param([string]$Channel="channel_001_ai_tools")

Set-Location "D:\textautonomous_media_engine"
.\.venv\Scripts\Activate.ps1

$env:ENABLE_AUTO_PROMOTE="1"
python main.py score --channel $Channel --window 7 --apply
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
