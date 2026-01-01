# Weekly Ops Cadence — Closed-loop Autonomy

Purpose
-------
Operational checklist for safely operating the closed-loop publish→measure→decide system.

Cadence (weekly)
-----------------
- Owners: 1 Architecture/System lead, 1 Data/Analytics reviewer, 1 Ops/Runbook reviewer.
- Frequency: weekly sync (15-30 minutes) and an extended monthly review (60 minutes).

Weekly checklist
----------------
1. Dry-run review (fast)
   - Run `python scripts/score_and_apply.py --channel <id>` in dry-run mode for active channels.
   - Confirm `assets/channels/<id>/pipeline/optimization/promotion_suggestions.json` contains expected decisions.
   - Verify no unexpected `orchestrator_events` ERROR spikes.

2. Safety gates
   - Confirm `ENABLE_AUTO_PROMOTE` remains OFF in staging/CI environments.
   - Confirm feature-flag toggles and environment configs are recorded in deployment notes.

3. Metrics spot-check
   - Check upload success rates (`videos.status`) and `orchestrator_events` for errors.
   - Inspect CTR and Average View Duration (AVD) deltas for promoted videos.

4. Post-apply monitoring (if any applies occurred)
   - For any applied promotions, confirm `promotion_history.json` entries exist and auditors recorded reason.
   - Monitor key metrics for at least 1–2 full cycles (e.g., 7 days) after promotion before expanding enablement.

Escalation triggers
-------------------
- Upload failure rate > 5% in a rolling 7-day window.
- CTR or AVD drop more than 2 standard deviations vs baseline within 7 days.

Rollback procedure
------------------
- Use `data/state/promotion_history.json` to identify the exact promotion payload and timestamp.
- Revert changes using the recorded details and write an `orchestrator_events` row documenting the rollback.
- Notify owners and schedule a post-mortem if rollback was due to a data/model issue.

Notes
-----
- Start enablement with a single small channel for 1–2 cycles before broadening.
- Keep the `ENABLE_AUTO_PROMOTE` flag off by default and enable per-channel explicitly when ready.

***
Generated as part of the closed-loop autonomy baseline work.
