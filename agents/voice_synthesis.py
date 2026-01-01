from __future__ import annotations

import os
from dataclasses import dataclass

from config import EngineConfig
from utils.paths import EnginePaths
from utils.openai_client import OpenAIJsonClient
from utils.json_validate import load_json, save_json, validate_json_against_schema
from utils.elevenlabs_client import ElevenLabsClient

@dataclass
class VoiceSynthesisAgent:
    cfg: EngineConfig
    paths: EnginePaths

    def __post_init__(self) -> None:
        self.client = OpenAIJsonClient(self.cfg.openai_api_key, self.cfg.openai_model)

    def _read_prompt(self, rel_path: str) -> str:
        with open(self.paths.prompt_path(rel_path), "r", encoding="utf-8") as f:
            return f.read()

    def prepare_tts(self, channel_id: str, run_id: str, script_path: str, output_path: str) -> None:
        system = self._read_prompt("system/voice_synthesis_system.txt")
        task = self._read_prompt("tasks/tts_directive.txt")
        schema = load_json(self.paths.prompt_path("schemas/script.schema.json"))
        script = load_json(script_path)

        payload = {
            "run_id": run_id,
            "channel_id": channel_id,
            "video_id": script.get("video_id"),
            "_task": "tts",
            "budget_policy": {
                "elevenlabs_cap_usd": self.cfg.budget.elevenlabs_cap_usd,
                "stop_at_pct": self.cfg.budget.stop_at_pct
            },
            "script": script
        }

        out = self.client.run_json(system, task, payload)

        # Merge narration fields into script
        merged = dict(script)
        for k in ["narration_chunks", "disclaimers", "missing_data"]:
            if k in out:
                merged[k] = out[k]

        validate_json_against_schema(merged, schema)

        # ---- ACTUAL SYNTH ----
        if not self.cfg.elevenlabs:
            # If not configured, just write merged JSON.
            save_json(output_path, merged)
            return

        el = self.cfg.elevenlabs
        tts = ElevenLabsClient(api_key=el.api_key)

        out_dir = os.path.join(
            self.cfg.engine_root, "assets", "channels", channel_id,
            "pipeline", "audio", "narration_chunks"
        )

        voice_settings = {
            "stability": el.stability,
            "similarity_boost": el.similarity_boost,
            "style": el.style,
            "speaker_boost": el.speaker_boost,
        }

        result = tts.synthesize_chunks(
            chunks=merged.get("narration_chunks", []),
            voice_id=el.default_voice_id,
            out_dir=out_dir,
            model_id=el.model_id,
            output_format=el.output_format,
            voice_settings=voice_settings,
        )

        merged["tts_outputs"] = {
            "voice_id": result.voice_id,
            "model_id": result.model_id,
            "files": result.outputs,
            "dir": out_dir
        }

        save_json(output_path, merged)
