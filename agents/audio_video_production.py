from __future__ import annotations

from dataclasses import dataclass

from config import EngineConfig
from utils.paths import EnginePaths
from utils.openai_client import OpenAIJsonClient
from utils.json_validate import load_json, save_json, validate_json_against_schema


@dataclass
class AudioVideoProductionAgent:
    cfg: EngineConfig
    paths: EnginePaths

    def __post_init__(self) -> None:
        self.client = OpenAIJsonClient(self.cfg.openai_api_key, self.cfg.openai_model)

    def _read_prompt(self, rel_path: str) -> str:
        with open(self.paths.prompt_path(rel_path), "r", encoding="utf-8") as f:
            return f.read()

    def generate_storyboard(
        self, channel_id: str, run_id: str, script_path: str, output_path: str
    ) -> None:
        system = self._read_prompt("system/av_production_system.txt")
        task = self._read_prompt("tasks/storyboard_shotlist.txt")
        schema = load_json(self.paths.prompt_path("schemas/storyboard.schema.json"))

        script = load_json(script_path)

        payload = {
            "run_id": run_id,
            "channel_id": channel_id,
            "video_id": script.get("video_id"),
            "script": script,
            "_task": "storyboard",
            "asset_sources": {
                "allowed": ["pexels", "pixabay", "wikimedia_commons"],
                "local_assets_dir": f"assets/channels/{channel_id}/pipeline/video/assets",
            },
            "quality_mode": False,
            "export_defaults": {
                "resolution": "1920x1080",
                "fps": 30,
                "codec": "h264",
                "bitrate_mbps": 16,
            },
        }

        out = self.client.run_json(system, task, payload)
        validate_json_against_schema(out, schema)
        save_json(output_path, out)
