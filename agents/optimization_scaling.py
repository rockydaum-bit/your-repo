from __future__ import annotations

import os
from typing import Any, Dict, Optional, cast
from dataclasses import dataclass

from config import EngineConfig
from utils.paths import EnginePaths
from utils.openai_client import OpenAIJsonClient
from utils.json_validate import load_json, save_json, validate_json_against_schema
from utils.prompt_manager import PromptManager, PromptPatch
from utils.state import load_state, save_state, OrchestratorState
from datetime import datetime, timedelta


@dataclass
class OptimizationScalingAgent:
    cfg: EngineConfig
    paths: EnginePaths

    def __post_init__(self) -> None:
        self.client: Optional[OpenAIJsonClient] = None
        if getattr(self.cfg, "openai_api_key", None) and getattr(
            self.cfg, "openai_model", None
        ):
            try:
                # Import at runtime so tests can stub utils.openai_client in sys.modules before instantiation
                import importlib

                openai_mod = importlib.import_module("utils.openai_client")
                OpenAIJsonClientCls = getattr(openai_mod, "OpenAIJsonClient")
                self.client = OpenAIJsonClientCls(
                    self.cfg.openai_api_key, self.cfg.openai_model
                )
            except Exception:
                self.client = None
        self.pm = PromptManager(self.cfg.engine_root)

    def _read_prompt(self, rel_path: str) -> str:
        with open(self.paths.prompt_path(rel_path), "r", encoding="utf-8") as f:
            return f.read()

    def run_weekly_optimization(self, channel_id: str) -> str:
        """
        1) Read rollups (7d, 28d)
        2) Ask model for bounded patch plan
        3) Create prompt variant files under prompts/variants/...
        4) Activate A/B test mapping in orchestrator_state.json
        Returns path to autopatch plan JSON artifact.
        """
        rollup_dir = os.path.join(
            self.cfg.engine_root,
            "assets",
            "channels",
            channel_id,
            "pipeline",
            "analytics",
        )
        r7_path = os.path.join(rollup_dir, "rollup_7d.json")
        r28_path = os.path.join(rollup_dir, "rollup_28d.json")

        rollup_7d = load_json(r7_path) if os.path.exists(r7_path) else None
        rollup_28d = load_json(r28_path) if os.path.exists(r28_path) else None

        # Provide base prompts to patch (task prompts only — safest surface)
        base_task_paths = [
            "tasks/script_generation.txt",
            "tasks/upload_metadata.txt",
        ]
        base_prompts = {p: self.pm.read_prompt(p) for p in base_task_paths}

        system = self._read_prompt("system/optimization_scaling_system.txt")
        task = self._read_prompt("tasks/optimization_autopatch.txt")
        schema = load_json(
            self.paths.prompt_path("schemas/optimization_autopatch.schema.json")
        )

        payload = {
            "channel_id": channel_id,
            "rollups": {"rollup_7d": rollup_7d, "rollup_28d": rollup_28d},
            "base_prompts": base_prompts,
            "governance": {
                "bounded_ops_only": True,
                "max_total_operations": 6,
                "ab_test_default_videos": 6,
                "ab_test_default_split": {"base": 0.5, "variant": 0.5},
            },
        }

        if self.client is None:
            raise RuntimeError("OpenAI client not configured for weekly optimization.")

        plan = self.client.run_json(system, task, payload)
        validate_json_against_schema(plan, schema)

        # Build PromptPatch objects
        patches: list[PromptPatch] = []
        for p in plan["patches"]:
            patches.append(
                PromptPatch(
                    target_rel_path=p["target_rel_path"],
                    operations=p["operations"],
                )
            )

        # Create variant in prompts/variants/...
        variant = self.pm.create_variant(
            channel_id=channel_id,
            variant_name=plan["variant_name"],
            patches=patches,
            notes=plan["notes"],
            created_by="OptimizationScalingAgent",
        )

        # Persist autopatch plan artifact
        out_dir = os.path.join(
            self.cfg.engine_root,
            "assets",
            "channels",
            channel_id,
            "pipeline",
            "optimization",
        )
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "autopatch_plan.json")
        plan_with_variant = dict(plan)
        plan_with_variant["variant_manifest_rel"] = variant.manifest_path
        save_json(out_path, plan_with_variant)

        # Activate A/B mapping in orchestrator state
        state_path = os.path.join(
            self.cfg.engine_root, "data", "state", "orchestrator_state.json"
        )
        state = load_state(state_path)

        # Map base task prompts -> variant rel paths
        manifest = load_json(self.paths.prompt_path(variant.manifest_path))
        mapping = manifest["mapping"]  # base_rel -> variant_rel

        active_variants = dict(state.active_variants)
        ch_map = dict(active_variants.get(channel_id, {}))

        # We only override tasks listed in manifest mapping
        for base_rel, variant_rel in mapping.items():
            ch_map[base_rel] = variant_rel

        active_variants[channel_id] = ch_map

        # A/B test metadata
        ab_tests = dict(state.ab_tests)
        ab_tests[channel_id] = {
            "enabled": plan["ab_test"]["enabled"],
            "allocation": plan["ab_test"]["allocation"],
            "videos": plan["ab_test"]["videos"],
            "success_metrics": plan["ab_test"]["success_metrics"],
            "variant_manifest_rel": variant.manifest_path,
        }

        new_state = OrchestratorState(
            version=state.version,
            active_variants=active_variants,
            ab_tests=ab_tests,
        )
        save_state(state_path, new_state)

        return out_path


def score_ab_test(
    db_path: str,
    channel_id: str,
    variant_manifest_rel: str,
    lookback_days: int = 14,
    min_videos: int = 5,
    promote_threshold: float = 0.05,
    rollback_threshold: float = -0.05,
) -> Dict[str, Any]:
    """
    Deterministic A/B scorer.

    - Aggregates per-variant metrics from `analytics_daily` table.
    - Requires at least `min_videos` per variant to consider promotion.
    - Returns suggestion: 'promote', 'rollback', or 'none' with reason and deltas.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    since = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()

    # Pull videos tied to this manifest variants via prompt_assignments
    cur.execute(
        """
        SELECT pa.video_id, pa.arm, a.views, a.revenue_usd, a.avg_view_duration_sec
        FROM prompt_assignments pa
        LEFT JOIN analytics_daily a ON a.video_id = pa.video_id
        WHERE pa.channel_id = ? AND pa.variant_manifest_rel = ?
        """,
        (channel_id, variant_manifest_rel),
    )

    rows = cur.fetchall()
    conn.close()

    # Aggregate per-variant
    per_variant: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        # rows may be sqlite3.Row or tuple
        if isinstance(row, dict) or hasattr(row, "keys"):
            vid = row.get("video_id")
            arm = row.get("arm")
            views_raw = row.get("views")
            revenue_raw = row.get("revenue_usd")
            avd_raw = row.get("avg_view_duration_sec")
        else:
            vid, arm, views_raw, revenue_raw, avd_raw = row

        video_id = cast(str, vid)
        variant = cast(str, arm)
        views = int(views_raw or 0)
        revenue = float(revenue_raw or 0.0)
        avd = float(avd_raw or 0.0)

        if variant not in per_variant:
            per_variant[variant] = {
                "views": 0,
                "revenue": 0.0,
                "avd": 0.0,
                "videos": set(),
            }
        per_variant[variant]["views"] += views
        per_variant[variant]["revenue"] += revenue
        per_variant[variant]["avd"] += avd
        per_variant[variant]["videos"].add(video_id)

    # Need at least two variants to compare
    variants = list(per_variant.keys())
    if len(variants) < 2:
        return {"suggestion": "none", "reason": "not_enough_variants"}

    # Compute simple score (revenue per view)
    scores: Dict[str, Optional[float]] = {}
    for v, data in per_variant.items():
        vids = len(data["videos"])
        if vids < min_videos:
            scores[v] = None
            continue
        views = int(data["views"] or 0)
        revenue = float(data.get("revenue", 0.0) or 0.0)
        if views <= 0:
            scores[v] = 0.0
        else:
            scores[v] = revenue / views

    # Exclude variants with insufficient data
    valid = {v: s for v, s in scores.items() if s is not None}
    if len(valid) < 2:
        return {"suggestion": "none", "reason": "insufficient_videos_per_variant"}

    # Compare specifically variant vs base (A/B). If keys differ, fallback to best/runner logic.
    suggestion = "none"
    reason = ""

    base_score = valid.get("base")
    variant_score = valid.get("variant")
    if base_score is not None and variant_score is not None:
        delta = (variant_score - base_score) / (base_score or 1.0)
        reason = "delta=%.4f" % (delta,)
        if delta >= promote_threshold:
            suggestion = "promote"
        elif delta <= rollback_threshold:
            suggestion = "rollback"
        return {
            "suggestion": suggestion,
            "base_score": base_score,
            "variant_score": variant_score,
            "delta": delta,
            "reason": reason,
        }

    # Fallback: best vs runner-up
    sorted_vars = sorted(valid.items(), key=lambda kv: kv[1], reverse=True)
    best_var, best_score = sorted_vars[0]
    runner_var, runner_score = sorted_vars[1]
    delta = (best_score - runner_score) / (runner_score or 1.0)
    reason = "delta=%.4f" % (delta,)
    if delta >= promote_threshold:
        suggestion = "promote"
    elif delta <= rollback_threshold:
        suggestion = "rollback"

    return {
        "suggestion": suggestion,
        "best_variant": best_var,
        "best_score": best_score,
        "runner_up": runner_var,
        "runner_score": runner_score,
        "delta": delta,
        "reason": reason,
    }


def _agent_score_ab_test_wrapper(
    self, channel_id: str, dry_run: bool = True
) -> Dict[str, Any]:
    # Resolve ab test manifest from state
    state_path = os.path.join(
        self.cfg.engine_root, "data", "state", "orchestrator_state.json"
    )
    try:
        state = load_state(state_path)
    except Exception:
        return {"decision": "none", "reason": "no_state"}

    ab = state.ab_tests.get(channel_id)
    if not ab or not ab.get("variant_manifest_rel"):
        return {"decision": "none", "reason": "no_ab_test_config"}

    variant_manifest_rel = ab["variant_manifest_rel"]
    min_videos = getattr(self.cfg, "auto_promote_min_videos", 6)
    lookback_days = getattr(self.cfg, "auto_promote_min_days", 14)

    result = score_ab_test(
        db_path=self.paths.db_path,
        channel_id=channel_id,
        variant_manifest_rel=variant_manifest_rel,
        lookback_days=lookback_days,
        min_videos=min_videos,
    )

    # map suggestion to decision key for tests
    decision = result.get("suggestion", "none")

    # Always write promotion_suggestions.json
    out_dir = os.path.join(
        self.cfg.engine_root,
        "assets",
        "channels",
        channel_id,
        "pipeline",
        "optimization",
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "promotion_suggestions.json")
    save_json(out_path, {"decision": decision, "details": result})

    # Guarded apply: only mutate when not dry_run and enabled in config
    applied = False
    if (
        (not dry_run)
        and getattr(self.cfg, "enable_auto_promote", False)
        and decision == "promote"
    ):
        apply_promotion_suggestion(
            self.paths.db_path,
            channel_id,
            variant_manifest_rel,
            result,
            enable_apply=True,
            history_path=os.path.join(
                self.cfg.engine_root, "data", "state", "promotion_history.json"
            ),
        )
        applied = True

    return {"decision": decision, "applied": applied, "details": result}


# Attach wrapper to class
setattr(OptimizationScalingAgent, "score_ab_test", _agent_score_ab_test_wrapper)


def apply_promotion_suggestion(
    db_path: str,
    channel_id: str,
    variant_manifest_rel: str,
    suggestion: Dict[str, Any],
    enable_apply: bool = False,
    history_path: Optional[str] = None,
):
    import sqlite3
    from utils.db import insert_orchestrator_event

    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "channel_id": channel_id,
        "manifest": variant_manifest_rel,
        "suggestion": suggestion,
    }

    # Idempotency check: don't duplicate the same promotion suggestion
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    like_pattern = f'%"manifest":"{variant_manifest_rel}"%'
    existing = cur.execute(
        "SELECT COUNT(1) as c FROM orchestrator_events WHERE event = 'promotion_suggestion' AND payload_json LIKE ?",
        (like_pattern,),
    ).fetchone()
    exists = existing["c"] if existing else 0

    if not exists:
        insert_orchestrator_event(
            db_path,
            datetime.utcnow().isoformat() + "Z",
            "INFO",
            "promotion_suggestion",
            event,
        )
        # Append to history file if provided
        if history_path:
            try:
                from utils.state import append_promotion_history

                append_promotion_history(history_path, event)
            except Exception:
                pass

    conn.close()

    applied = False
    if enable_apply and suggestion.get("suggestion") == "promote":
        # In real system, here we would flip configuration or call publish endpoints.
        applied = True

    return {"applied": applied, "event": event}
