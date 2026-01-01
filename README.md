Text Autonomous Media Engine — Dev Quickstart

Short, actionable local commands that mirror CI (.github/workflows/ci.yml). Use PowerShell on Windows or POSIX shells on Linux/macOS.

Prerequisites
- Python 3.11
- Git

Create and activate a virtual environment

PowerShell:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

POSIX (bash):
```bash
python -m venv .venv
source .venv/bin/activate
```

Install runtime + dev dependencies

PowerShell / POSIX:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
# dev tools used by CI
pip install --upgrade pytest ruff mypy types-requests pytest-cov coverage
```

Run linters and type checks

PowerShell / POSIX:
```bash
# Lint
python -m ruff check .

# Static types (mypy)
python -m mypy --ignore-missing-imports agents utils tests main.py config.py
```

Run tests with coverage (matches CI)

PowerShell / POSIX:
```bash
python -m pytest --maxfail=1 -q --cov=. --cov-report=xml --cov-report=term-missing

# enforce coverage floor (reads .coverage_threshold)
THRESH=$(cat .coverage_threshold | tr -d " \n\r")
python -m coverage report --fail-under=$THRESH
```

If you prefer PowerShell native command to enforce threshold:
```powershell
$THRESH = (Get-Content .coverage_threshold).Trim()
python -m coverage report --fail-under=$THRESH
```

Adjusting the coverage floor
- Edit `.coverage_threshold` (single integer percentage). The repository includes an automated ratchet that will open PRs to increment this value on a schedule.

That's it — these commands mirror what CI runs so local checks follow the same rules as automated checks.

CLI & Feature flags (quick reference)

- `scripts/score_and_apply.py --channel <id> [--apply]` — score A/B tests and (optionally) apply promotions.
- Environment feature flags (defaults):
	- `ENABLE_AUTO_PROMOTE` (default: `False`)
	- `AUTO_PROMOTE_MIN_VIDEOS` (default: `6`)
	- `AUTO_PROMOTE_MIN_DAYS` (default: `7`)

See `CONTRIBUTING.md` for governance, testing standards, and the dry-run review process.

### Running the packaged node

After building with `scripts/build_exe.ps1` (or using the provided `dist/textautonomous_node.exe`), run the packaged node with an explicit config file:

```powershell
cd dist

# Brain
.\textautonomous_node.exe --config "C:\textauto\engine-brain.yaml"

# Worker
.\textautonomous_node.exe --config "C:\textauto\engine-worker.yaml"
```

Alternatively you can set `ENGINE_CONFIG_PATH` in the environment and omit `--config`. If both are set, `--config` takes precedence. See `docs/DEPLOY.md` and `docs/CONFIG.md` for full installation and configuration guidance.


## Acceptance tests

Acceptance tests validate the full orchestration loop end-to-end (artifact writing, run summaries, and dependency gating) using deterministic LLM fixtures.

### Run locally (Windows PowerShell)

Activate venv and run:

```powershell
& .venv\Scripts\Activate.ps1
python -m pytest -q -s -vv -m acceptance --maxfail=1 --durations=20
```

### Run individual tests

```powershell
python -m pytest -q -s -vv tests/test_acceptance_run_contracts.py::test_two_run_acceptance
python -m pytest -q -s -vv tests/test_acceptance_run_contracts.py::test_dependency_gating_on_plan_failure
```

### Notes

* Tests use deterministic fixtures via a router and `_task` discriminators in payloads.
* `OPENAI_API_KEY` can be set to any value for acceptance runs.
