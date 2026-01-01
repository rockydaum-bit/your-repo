from __future__ import annotations

import os
import json
from datetime import datetime

from config import get_config
from utils.paths import EnginePaths
from utils.logger import get_logger
from utils.db import init_db, log_event
from utils.budget_monitor import check_budget
from utils.hardware_monitor import check_hardware
from utils.json_validate import save_json, load_json, validate_json_against_schema, SchemaValidationError

from agents.content_generation import ContentGenerationAgent
from agents.voice_synthesis import VoiceSynthesisAgent
from agents.audio_video_production import AudioVideoProductionAgent
from agents.publishing_seo import PublishingSEOAgent
from agents.analytics_metrics import AnalyticsMetricsAgent
from agents.optimization_scaling import OptimizationScalingAgent

class Orchestrator:
    def __init__(self) -> None:
        self.cfg = get_config()
        self.paths = EnginePaths(self.cfg.engine_root)
        self.paths.ensure_dirs()

        self.logger = get_logger("orchestrator", self.paths.logs_dir)
        init_db(self.paths.db_path)

        self.content = ContentGenerationAgent(self.cfg, self.paths)
        self.voice = VoiceSynthesisAgent(self.cfg, self.paths)
        self.av = AudioVideoProductionAgent(self.cfg, self.paths)
        self.pub = PublishingSEOAgent(self.cfg, self.paths)
        self.analytics = AnalyticsMetricsAgent(self.cfg, self.paths)
        self.optimize = OptimizationScalingAgent(self.cfg, self.paths)

    def _ts(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def run_weekly_growth_loop(self) -> None:
        """
        High-level enterprise loop:
        - governance gates
        - plan -> script -> tts plan -> storyboard -> publish metadata -> (render/upload stub)
        - analytics -> optimization
        """
        ts = self._ts()
        self.logger.info("Weekly growth loop started.")
        log_event(self.paths.db_path, ts, "INFO", "weekly_growth_loop_start")

        # Governance: budget
        b = check_budget(
            db_path=self.paths.db_path,
            monthly_cap_usd=self.cfg.budget.monthly_cap_usd,
            stop_at_pct=self.cfg.budget.stop_at_pct,
        )
        if b.should_stop:
            msg = f"Budget gate triggered: month_total={b.month_total:.2f} >= stop_at={b.stop_at:.2f}"
            self.logger.warning(msg)
            log_event(self.paths.db_path, self._ts(), "WARN", "budget_gate_stop", json.dumps(b.__dict__))
            return

        # Governance: hardware
        hw = check_hardware(
            engine_root=self.cfg.engine_root,
            cpu_pause_pct=self.cfg.hardware.cpu_pause_pct,
            disk_free_pause_pct=self.cfg.hardware.disk_free_pause_pct,
        )
        if hw.should_pause:
            msg = f"Hardware gate pause: reasons={hw.reasons}"
            self.logger.warning(msg)
            log_event(self.paths.db_path, self._ts(), "WARN", "hardware_gate_pause", json.dumps(hw.__dict__))
            return

        # Demo run: single channel + one video pipeline (extend later)
        channel_id = "channel_001_ai_tools"
        run_id = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{channel_id}_v0001"

        artifacts = self._one_video_pipeline(channel_id=channel_id, run_id=run_id)

        # Update latest pointer for UI consumption (atomic)
        try:
            # read the produced run summary to get finished_at and status
            summary_path = artifacts.get("run_summary")
            updated_at = self._ts()
            status = "unknown"
            try:
                if summary_path and os.path.exists(summary_path):
                    rs = load_json(summary_path)
                    updated_at = rs.get("finished_at") or rs.get("started_at") or updated_at
                    status = rs.get("status") or status
            except Exception:
                # best-effort; continue
                pass

            latest_path = os.path.join(self.paths.state_dir, "runs", "latest.json")
            latest_map = {}
            if os.path.exists(latest_path):
                try:
                    latest_map = load_json(latest_path)
                except Exception:
                    latest_map = {}

            latest_map[channel_id] = {
                "run_id": run_id,
                "summary_rel": (summary_path or "").replace('\\', '/'),
                "updated_at": updated_at,
                "status": status,
            }
            save_json(latest_path, latest_map)
        except Exception as e:
            self.logger.warning(f"Failed to update latest.json: {e}")

        self.logger.info(f"Weekly loop complete. Artifacts: {artifacts}")
        log_event(self.paths.db_path, self._ts(), "INFO", "weekly_growth_loop_complete", json.dumps(artifacts))

                # Weekly optimization autopatch (requires rollups)
        try:
            opt_path = self.optimize.run_weekly_optimization(channel_id="channel_001_ai_tools")
            self.logger.info(f"Optimization autopatch written: {opt_path}")
        except Exception as e:
            self.logger.warning(f"Optimization autopatch skipped/failed: {e}")

    def _one_video_pipeline(self, channel_id: str, run_id: str) -> dict[str, str]:
        """
        Deterministic pipeline for a single video.
        """
        base = os.path.join(self.cfg.engine_root, "assets", "channels", channel_id, "pipeline")
        brief_path = os.path.join(base, "briefs", "video01_brief.json")
        plan_path = os.path.join(base, "plans", "video01_plan.json")
        script_path = os.path.join(base, "scripts", "video01_script.json")
        meta_path = os.path.join(base, "publish", "video01_metadata.json")
        storyboard_path = os.path.join(base, "video", "video01_storyboard.json")

        # Prepare a run-level directory and summary so UI/consumers can rely on a single artifact
        run_dir = os.path.join(self.paths.state_dir, "runs", run_id)
        os.makedirs(run_dir, exist_ok=True)
        run_summary_path = os.path.join(run_dir, "summary.json")

        # Load or initialize summary. Validate against schema and archive invalid files.
        schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "schemas", "run_summary.schema.json"))
        summary = {}
        if os.path.exists(run_summary_path):
            try:
                summary = load_json(run_summary_path)
                try:
                    schema = load_json(schema_path) if os.path.exists(schema_path) else None
                    if schema is not None:
                        validate_json_against_schema(summary, schema)
                except SchemaValidationError as sve:
                    self.logger.warning(f"Existing run summary failed schema validation: {sve}; archiving and starting fresh.")
                    bad_archive = run_summary_path + f".invalid.{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
                    try:
                        os.replace(run_summary_path, bad_archive)
                    except Exception:
                        # best-effort archive; ignore
                        pass
                    summary = {}
                except Exception as e:
                    self.logger.warning(f"Error validating existing summary: {e}; starting fresh.")
                    summary = {}
            except Exception:
                summary = {}

        summary.setdefault("run_id", run_id)
        summary.setdefault("channel_id", channel_id)
        summary.setdefault("started_at", self._ts())
        summary.setdefault("finished_at", None)
        summary.setdefault("status", "in_progress")
        summary.setdefault("steps", {})
        summary.setdefault("artifacts", {})
        summary.setdefault("errors", [])
        save_json(run_summary_path, summary)

        # Ensure a minimal brief exists (first run bootstrap)
        os.makedirs(os.path.dirname(brief_path), exist_ok=True)
        if not os.path.exists(brief_path):
            seed = {
                "channel_id": channel_id,
                "video_seed": {
                    "topic": "Best AI tools for small businesses in 2026",
                    "angle": "Practical stack: automate ops, marketing, support under $100",
                    "persona": "SMB owner / operator",
                    "affiliate_intent": "high",
                    "expected_rpm_band": "high"
                }
            }
            with open(brief_path, "w", encoding="utf-8") as f:
                json.dump(seed, f, indent=2)

        def _should_skip(path: str) -> bool:
            return os.path.exists(path) and os.path.getsize(path) > 0

        # 1) Content plan (optional in this demo) -> produce a single plan item
        try:
            if _should_skip(plan_path):
                summary["steps"]["plan"] = "skipped"
            else:
                self.content.generate_plan(channel_id=channel_id, run_id=run_id, brief_path=brief_path, output_path=plan_path)
                summary["steps"]["plan"] = "success"
        except Exception as e:
            summary["steps"]["plan"] = "failed"
            summary["errors"].append({"step": "plan", "message": str(e), "ts": self._ts()})
        summary["artifacts"]["plan"] = plan_path
        save_json(run_summary_path, summary)

        # 2) Script (depends on plan)
        plan_ok = summary.get("steps", {}).get("plan") == "success"
        if not plan_ok:
            summary["steps"]["script"] = "skipped"
            summary["errors"].append({"step": "script", "message": "blocked_by_failed_dependency", "ts": self._ts()})
        else:
            try:
                if _should_skip(script_path):
                    summary["steps"]["script"] = "skipped"
                else:
                    self.content.generate_script(channel_id=channel_id, run_id=run_id, plan_item_path=plan_path, output_path=script_path)
                    summary["steps"]["script"] = "success"
            except Exception as e:
                summary["steps"]["script"] = "failed"
                summary["errors"].append({"step": "script", "message": str(e), "ts": self._ts()})
        summary["artifacts"]["script"] = script_path
        save_json(run_summary_path, summary)

        # 3) Voice directives (depends on script)
        script_ok = summary.get("steps", {}).get("script") == "success"
        if not script_ok:
            summary["steps"]["tts"] = "skipped"
            summary["errors"].append({"step": "tts", "message": "blocked_by_failed_dependency", "ts": self._ts()})
        else:
            try:
                if _should_skip(script_path):
                    summary["steps"]["tts"] = "skipped"
                else:
                    # voice may write files referenced from script; keep same output_path for now
                    self.voice.prepare_tts(channel_id=channel_id, run_id=run_id, script_path=script_path, output_path=script_path)
                    summary["steps"]["tts"] = "success"
            except Exception as e:
                summary["steps"]["tts"] = "failed"
                summary["errors"].append({"step": "tts", "message": str(e), "ts": self._ts()})
        summary["artifacts"]["tts"] = script_path
        save_json(run_summary_path, summary)

        # 4) Storyboard (depends on script only)
        if not script_ok:
            summary["steps"]["storyboard"] = "skipped"
            summary["errors"].append({"step": "storyboard", "message": "blocked_by_failed_dependency", "ts": self._ts()})
        else:
            try:
                if _should_skip(storyboard_path):
                    summary["steps"]["storyboard"] = "skipped"
                else:
                    self.av.generate_storyboard(channel_id=channel_id, run_id=run_id, script_path=script_path, output_path=storyboard_path)
                    summary["steps"]["storyboard"] = "success"
            except Exception as e:
                summary["steps"]["storyboard"] = "failed"
                summary["errors"].append({"step": "storyboard", "message": str(e), "ts": self._ts()})
        summary["artifacts"]["storyboard"] = storyboard_path
        save_json(run_summary_path, summary)

        # 5) Publishing metadata (depends on script)
        if not script_ok:
            summary["steps"]["metadata"] = "skipped"
            summary["errors"].append({"step": "metadata", "message": "blocked_by_failed_dependency", "ts": self._ts()})
        else:
            try:
                if _should_skip(meta_path):
                    summary["steps"]["metadata"] = "skipped"
                else:
                    self.pub.generate_upload_metadata(channel_id=channel_id, run_id=run_id, script_path=script_path, output_path=meta_path)
                    summary["steps"]["metadata"] = "success"
            except Exception as e:
                summary["steps"]["metadata"] = "failed"
                summary["errors"].append({"step": "metadata", "message": str(e), "ts": self._ts()})
        summary["artifacts"]["metadata"] = meta_path
        save_json(run_summary_path, summary)

        # 6) Analytics (stub: would run daily)
        # 7) Optimization (stub: weekly based on analytics)

        # finalize summary
        summary["finished_at"] = self._ts()
        summary["status"] = "failed" if summary.get("errors") else "success"
        save_json(run_summary_path, summary)

        return {
            "brief": brief_path,
            "plan": plan_path,
            "script": script_path,
            "storyboard": storyboard_path,
            "metadata": meta_path,
            "run_summary": run_summary_path
        }
