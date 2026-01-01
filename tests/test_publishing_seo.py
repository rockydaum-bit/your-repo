import json
from pathlib import Path

from config import EngineConfig
from utils.paths import EnginePaths
from utils.json_validate import load_json

from agents.publishing_seo import PublishingSEOAgent


def _write_minimal_metadata_schema(path: Path) -> None:
    schema = {
        "type": "object",
        "required": ["channel_id", "video_id", "titles", "selected_title", "description", "tags", "chapters", "hashtags", "affiliate_plan", "pinned_comment", "thumbnail_briefs", "missing_data"],
        "properties": {
            "channel_id": {"type": "string"},
            "video_id": {"type": "string"},
            "titles": {"type": "array", "items": {"type": "string"}},
            "selected_title": {"type": ["string", "null"]},
            "description": {"type": ["string", "null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "chapters": {"type": "array", "items": {"type": "object"}},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "affiliate_plan": {"type": "object"},
            "pinned_comment": {"type": ["string", "null"]},
            "thumbnail_briefs": {"type": "array", "items": {"type": "object"}},
            "missing_data": {"type": "array", "items": {"type": "string"}}
        }
    }
    path.write_text(json.dumps(schema))


def test_generate_upload_metadata_writes_valid_metadata(tmp_path, monkeypatch):
    engine_root = str(tmp_path)
    cfg = EngineConfig(engine_root=engine_root, openai_api_key="test", openai_model="gpt-4o")
    paths = EnginePaths(cfg.engine_root)
    paths.ensure_dirs()

    # Create prompt files and schema
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "system").mkdir(parents=True)
    (prompts_dir / "tasks").mkdir(parents=True)
    (prompts_dir / "schemas").mkdir(parents=True)

    (prompts_dir / "system" / "publishing_seo_system.txt").write_text("You are the Publishing & SEO Agent. Output JSON only.")
    (prompts_dir / "tasks" / "upload_metadata.txt").write_text("TASK")
    _write_minimal_metadata_schema(prompts_dir / "schemas" / "metadata.schema.json")

    # Create minimal script JSON expected by agent
    channel_dir = tmp_path / "assets" / "channels" / "channel_001_ai_tools" / "pipeline" / "scripts"
    channel_dir.mkdir(parents=True, exist_ok=True)
    script_path = channel_dir / "video01_script.json"
    script = {
        "channel_id": "channel_001_ai_tools",
        "video_id": "channel_001_ai_tools_video01",
        "title_working": "Working title",
        "runtime_target_min": 12,
        "sections": [],
        "full_script": "Hello",
        "narration_chunks": [],
        "disclaimers": [],
        "missing_data": []
    }
    script_path.write_text(json.dumps(script))

    # Instantiate agent and stub OpenAIJsonClient to return deterministic metadata
    agent = PublishingSEOAgent(cfg, paths)

    class StubClient:
        def run_json(self, system_prompt: str, user_prompt: str, input_payload: dict) -> dict:
            return {
                "channel_id": input_payload.get("channel_id") or "channel_001_ai_tools",
                "video_id": input_payload.get("script", {}).get("video_id"),
                "titles": ["Best AI Tools 2026"],
                "selected_title": "Best AI Tools 2026",
                "description": "A neutral description.",
                "tags": ["ai","tools"],
                "chapters": [],
                "hashtags": [],
                "affiliate_plan": {"disclosure": "affiliate" , "placements": [], "tools_section": ""},
                "pinned_comment": None,
                "thumbnail_briefs": [{"concept":"1","overlay_text":"AI","composition_notes":"","dont_do":[]}],
                "missing_data": []
            }

    agent.client = StubClient()

    out_dir = tmp_path / "assets" / "channels" / "channel_001_ai_tools" / "pipeline" / "publish"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "video01_metadata.json"

    agent.generate_upload_metadata(channel_id="channel_001_ai_tools", run_id="r1", script_path=str(script_path), output_path=str(out_path))

    assert out_path.exists()
    out = load_json(str(out_path))
    # Validate presence of minimal top-level keys
    minimal_required = {"video_id", "titles", "selected_title"}
    assert minimal_required.issubset(set(out.keys()))
