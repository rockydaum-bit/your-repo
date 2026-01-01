param(
  [string]$Channel = "channel_001_ai_tools"
)

Set-Location "D:\textautonomous_media_engine"
.\.venv\Scripts\Activate.ps1

# Run pipeline (1 video)
python main.py run --channel $Channel --max-videos 1

# Measure (7d rollup)
python main.py measure --channel $Channel --window 7

# Score (dry-run)
python main.py score --channel $Channel --window 7
