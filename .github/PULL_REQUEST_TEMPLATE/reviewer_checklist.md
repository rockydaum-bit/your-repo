## Reviewer Checklist (Enterprise Gates)

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

Optional but Strong Add-On (1 minute improvement)

Add this to your PR description right under “Rollout Plan”:

Launch mode: dry-run only for 1–2 cycles

Enablement: set ENABLE_AUTO_PROMOTE=1 for one channel

Guardrails: revert to 0 immediately if upload failures spike or CTR/AVD collapses
