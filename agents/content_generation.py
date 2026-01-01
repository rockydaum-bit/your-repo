from __future__ import annotations

import os
from dataclasses import dataclass

from config import EngineConfig
from utils.paths import EnginePaths
from utils.openai_client import OpenAIJsonClient
from utils.json_validate import load_json, save_json, validate_json_against_schema
from utils.state import load_state

@dataclass
class ContentGenerationAgent:
    cfg: EngineConfig
    paths: EnginePaths

    def __post_init__(self) -> None:
        self.client = OpenAIJsonClient(self.cfg.openai_api_key, self.cfg.openai_model)

    def _read_prompt(self, rel_path: str, channel_id: str | None = None) -> str:
        """
        If rel_path is a task prompt (e.g. tasks/script_generation.txt) and a variant is active,
        load variant prompt instead.
        """
        chosen = rel_path
        if channel_id and rel_path.startswith("tasks/"):
            state_path = os.path.join(self.cfg.engine_root, "data", "state", "orchestrator_state.json")
            state = load_state(state_path)
            mapping = state.active_variants.get(channel_id, {})
            # mapping key is base_rel_path (e.g., tasks/script_generation.txt)
            if rel_path in mapping:
                chosen = mapping[rel_path]

        with open(self.paths.prompt_path(chosen), "r", encoding="utf-8") as f:
            return f.read()


    def generate_plan(self, channel_id: str, run_id: str, brief_path: str, output_path: str) -> None:
        system = self._read_prompt("system/content_generation_system.txt")
        task = self._read_prompt("tasks/script_generation.txt", channel_id=channel_id)
        schema = load_json(self.paths.prompt_path("schemas/content_plan.schema.json"))
        brief = load_json(brief_path)

        payload = {
            "run_id": run_id,
            "channel_id": channel_id,
            "timezone": self.cfg.timezone,
            "brief": brief,
            "_task": "week_plan",
            "constraints": {
                "weekly_videos": 3,
                "weeks": 4,
                "policy_mode": "standard"
            }
        }

        out = self.client.run_json(system, task, payload)
        validate_json_against_schema(out, schema)

        # For demo pipeline, also write a single "plan item" file expected by script step.
        # If out contains week_plans, pick first video.
        plan_item = None
        try:
            plan_item = out["week_plans"][0]["videos"][0]
        except Exception:
            plan_item = {
                "video_id": f"{channel_id}_video01",
                "topic": brief.get("video_seed", {}).get("topic", "AI tools for SMB"),
                "angle": brief.get("video_seed", {}).get("angle", ""),
                "persona": brief.get("video_seed", {}).get("persona", "SMB owner"),
                "hook": "If your business still does these tasks manually, you’re burning money.",
                "affiliate_intent": "high",
                "expected_rpm_band": "high"
            }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        save_json(output_path, plan_item)

    def generate_script(self, channel_id: str, run_id: str, plan_item_path: str, output_path: str) -> None:
        system = self._read_prompt("system/content_generation_system.txt")
        task = self._read_prompt("tasks/script_generation.txt")
        schema = load_json(self.paths.prompt_path("schemas/script.schema.json"))
        plan_item = load_json(plan_item_path)

        payload = {
            "run_id": run_id,
            "channel_id": channel_id,
            "plan_item": plan_item,
            "_task": "script",
            "runtime_target_min": 14,
            "retention_rules": {
                "hook_seconds": 15,
                "pattern_interrupt_seconds": 120
            },
            "policy_mode": "standard"
        }

        out = self.client.run_json(system, task, payload)
        validate_json_against_schema(out, schema)
        save_json(output_path, out)
