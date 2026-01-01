cd (git rev-parse --show-toplevel)

Write-Output "=== 1) STATUS (pre) ==="
git status --porcelain=v1 -b

Write-Output "`n=== 2) STAGE inventory artifacts ==="
git add -- repo_file_list.txt repo_manifest.json

Write-Output "`n=== 3) STAGED DIFF (sanity) ==="
git --no-pager diff --cached -- repo_file_list.txt repo_manifest.json

Write-Output "`n=== 4) COMMIT + PUSH ==="
git commit -m "chore: refresh repo inventory outputs"
git push

Write-Output "`n=== 5) RE-RUN GENERATOR (must be deterministic) ==="
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\generate_repo_inventory.ps1
Write-Output ("GEN_EXIT_CODE=" + $LASTEXITCODE)

Write-Output "`n=== 6) DIFF AFTER GENERATOR (MUST BE EMPTY) ==="
git --no-pager diff -- repo_file_list.txt repo_manifest.json

Write-Output "`n=== 7) FINAL STATUS ==="
git status --porcelain=v1 -b
git log -2 --oneline
