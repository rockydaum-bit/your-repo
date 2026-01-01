<!-- Reviewer Expectations
- If any box below is unchecked, explain why.
- Auto-promotion changes require at least one dry-run cycle before enabling.
-->

Title: Safe autonomous publish→measure→decide loop — DB binding, deterministic A/B scoring, gated apply

Summary
-------
Implements a safe, auditable closed-loop for publish→measure→decide→act:
- Durable publish DB binding with idempotent upsert and orchestrator event audit.
- Deterministic A/B scoring (arithmetic-only) that writes suggestions in dry-run and applies behind feature flags.
- CLI to run scoring (`scripts/score_and_apply.py`) and deterministic unit tests that avoid external services.
- Reviewer checklist template added for enterprise gates.

Primary changes
---------------
- Feature flags: `config.py`
- Publish binding + audit: `utils/db.py`, `agents/publishing_seo.py`
- Deterministic A/B scoring + guarded apply: `agents/optimization_scaling.py`
- CLI: `scripts/score_and_apply.py`
- Tests: `tests/test_publishing_upload_db_binding.py`, `tests/test_experiment_scoring_promote.py`, `tests/test_experiment_scoring_rollback.py`
- Reviewer checklist: `.github/PULL_REQUEST_TEMPLATE/reviewer_checklist.md`
- Docs: `CONTRIBUTING.md` and README addendum

How to test locally
-------------------
- Run unit tests:
  ```bash
  pytest -q
  ```
- Dry-run scoring for a channel (no state mutation):
  ```bash
  python scripts/score_and_apply.py --channel channel_001_ai_tools
  ```
  This writes `promotion_suggestions.json` under the Engine root and emits `orchestrator_events` rows.
- Apply (manual, guarded):
  - Backup DB first.
  - Set `ENABLE_AUTO_PROMOTE=1` in env (feature flag off by default).
  - Run:
  ```bash
  ENABLE_AUTO_PROMOTE=1 python scripts/score_and_apply.py --channel channel_001_ai_tools --apply
  ```

Reviewer Checklist (copy/paste)
------------------------------
### 1) Correctness & Data Integrity
- [ ] Publish path writes `videos.youtube_video_id`, `published_ts`, and `status='published'` deterministically.
- [ ] Publish failures write `videos.status='upload_failed'` and an `orchestrator_events` ERROR.
- [ ] `upsert_video_publish()` is idempotent (repeat calls don’t create duplicates or corrupt state).
- [ ] `insert_orchestrator_event()` used for all critical mutations.

### 2) Safety & Change Control
- [ ] `ENABLE_AUTO_PROMOTE` defaults to **false** and prevents any state mutation when disabled.
- [ ] `score_ab_test(..., dry_run=True)` produces `promotion_suggestions.json` without applying.
- [ ] Apply path writes audit artifacts (`promotion_history.json`) and `orchestrator_events` rows.
- [ ] Promotions are reversible using history artifacts (manual rollback feasible).

### 3) Determinism & Auditability
- [ ] Scoring logic is deterministic (no network/model calls; arithmetic-only).
- [ ] Decision output includes: metrics snapshot, sample counts, decision, and rule used.
- [ ] Paths written are stable and channel-scoped (no cross-channel bleed).

### 4) Test & CI Hygiene
- [ ] Unit tests do not call external services (OpenAI/YouTube).
- [ ] New tests cover:
  - [ ] upload→DB binding + audit
  - [ ] promote decision
  - [ ] rollback decision
- [ ] `pytest -q` passes locally and in CI.
- [ ] Coverage remains above `.coverage_threshold` (ratchet compatible).

### 5) Operability
- [ ] `scripts/score_and_apply.py --channel <id>` runs in dry-run mode by default.
- [ ] `--apply` requires explicit enable flag to mutate state.
- [ ] README and CONTRIBUTING explain local run commands and safety flags.

### 6) Rollout Readiness
- [ ] Dry-run can be scheduled safely (no side effects beyond suggestion JSON + events).
- [ ] First-channel enablement plan documented (1 channel, 1–2 cycles, then expand).

Rollout Plan + Addendum (copy/paste under “Rollout Plan”)
--------------------------------------------------------
Launch mode: dry-run only for 1–2 cycles

Enablement: set `ENABLE_AUTO_PROMOTE=1` for a single channel (start with one small channel)

Guardrails:
- Revert `ENABLE_AUTO_PROMOTE=0` immediately if:
  - Upload failure rate > 5% (or > X absolute failures in window)
  - CTR or Average View Duration (AVD) collapses beyond expected variance (e.g., >2σ drop)
- Monitor `orchestrator_events` for error spikes and `promotion_history.json` for unexpected entries.

Monitoring & Rollback:
- Metrics: watch YouTube upload success counts (DB `videos.status`), CTR, AVD, and impressions in analytics rollups.
- Audit trails: `orchestrator_events` rows + `promotion_history.json` (used to reverse promotions manually).
- Manual rollback: use `promotion_history.json` to identify promoted videos and run `upsert_video_publish()` or an undo script to revert `videos` changes; write an `orchestrator_events` row for the rollback.

Notes for reviewers
-------------------
- Feature flags are intentionally OFF by default. Please confirm `ENABLE_AUTO_PROMOTE` defaults to false in `config.py`.
- Tests are deterministic and stub external clients; CI must run `pytest -q` and check coverage.
- See reviewer checklist file: `.github/PULL_REQUEST_TEMPLATE/reviewer_checklist.md`

---

If you'd like, I can:
- Insert this PR body into the repository as `.github/PULL_REQUEST_TEMPLATE/pr_template.md`, or
- Open a local branch, stage these changes, and provide exact git commands and a ready-to-run shell snippet for creating the PR. Which do you prefer?
