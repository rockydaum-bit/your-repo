# Release v0.3.0 — Closed-loop Autonomy Baseline

Release date: 2025-12-22

Summary
-------
This release establishes a governed closed-loop publish→measure→decide system for the Text Autonomous Media Engine. It introduces deterministic A/B scoring, safe guarded application (feature-flagged), durable publish DB binding with audit trails, CI guardrails, and reviewer templates to enforce governance.

Key changes
-----------
- Deterministic A/B scoring and guarded apply: `agents/optimization_scaling.py`
- Durable publish binding and audit events: `utils/db.py`, `agents/publishing_seo.py`
- PR governance: default PR template and reviewer checklist in `.github/PULL_REQUEST_TEMPLATE/`
- CI safety: `.github/workflows/ci.yml` now sets `ENABLE_AUTO_PROMOTE=0` by default and runs unit tests (`-m "not integration"`).
- Guardrail test: `tests/test_feature_flag_guardrail.py` ensures auto-promotion is opt-in only.
- Helper scripts: `scripts/create_and_push_branch.ps1` added to standardize branch creation and pushing.
- Ops runbook: `docs/weekly_ops_cadence.md` added.

Why this matters
---------------
- Converts automation into governed behavior (opt-in autopromotion only).
- Provides deterministic, auditable decisions and an explicit rollout path.
- Reduces risk by enforcing CI-level invariants and reviewer expectations.

Rollout plan
------------
1. Merge PR to `main` using the provided PR template and reviewer checklist.
2. Start dry-run only for one channel for 1–2 cycles. Do not enable `ENABLE_AUTO_PROMOTE` broadly.
3. Verify metrics (upload success, CTR, AVD). If stable, expand channel enablement.
4. Tag the merge commit as `v0.3.0-closed-loop-autonomy`.

Monitoring & rollback
---------------------
- Monitor `orchestrator_events`, `videos.status`, and analytics rollups.
- Use `data/state/promotion_history.json` to revert applied promotions manually.

Contact
-------
For questions or approvals, tag Architecture/System and Data owners in the PR.
