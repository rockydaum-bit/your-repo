## Contributing

This file gives concise, actionable rules for developers working on the Text Autonomous Media Engine.

**Local dev quickstart**
- Activate venv (Windows PowerShell):
  - `python -m venv .venv` then `\.venv\Scripts\Activate.ps1`
- POSIX (macOS/Linux):
  - `python -m venv .venv` then `source .venv/bin/activate`
- Install deps:
  - `pip install -r requirements.txt`
  - Dev tools: `pip install ruff mypy pytest pytest-cov coverage`
- Run checks (separate commands):
  - `python -m ruff check .`
  - `python -m mypy --ignore-missing-imports agents utils main.py config.py`
  - `python -m pytest -q`
  - `python -m pytest --cov=agents --cov=utils --cov-report=term-missing`

**Testing standards**
- Unit tests MUST NOT hit external APIs.
- All external clients (OpenAI, YouTube, ElevenLabs, etc.) must be injected or stubbed in tests.
- New agent features must include tests for:
  - happy path
  - failure path (retries / error handling)
  - idempotency and audit writes

**Autonomy governance**
- `ENABLE_AUTO_PROMOTE` defaults to `False` (CI-safe).
- Dry-run review process:
  1. Run: `python scripts/score_and_apply.py --channel <id>` (dry-run)
  2. Inspect `assets/channels/<id>/pipeline/optimization/promotion_suggestions.json` and audit events
  3. After review, run with `--apply` in a controlled environment

  - PRs touching autonomy, promotion, or publish flows should include the
    **Reviewer Checklist** from `.github/PULL_REQUEST_TEMPLATE/reviewer_checklist.md`.
    Reviewers should use the built-in PR template which enforces these checks.

**Promotion audit requirements**
- Every applied promotion must write:
  - an `orchestrator_events` row
  - an entry appended to `data/state/promotion_history.json`

**Rollback procedure (operational)**
- Inspect `promotion_history.json` for the last apply timestamp and payload.
- Use the recorded details to revert changed prompts or configurations and re-run validation tests.

**Coverage ratchet policy**
- The required coverage floor is defined in `.coverage_threshold`.
- PRs must not reduce coverage; the default workflow enforces the floor.
- Exemptions must be documented in the PR description and approved by reviewers.

**CLI & feature flags (quick reference)**
- `scripts/score_and_apply.py --channel <id> [--apply]` — score and optional apply
- Feature flags (env): `ENABLE_AUTO_PROMOTE`, `AUTO_PROMOTE_MIN_VIDEOS`, `AUTO_PROMOTE_MIN_DAYS`

Thanks — follow these guardrails to keep the system safe and auditable.
