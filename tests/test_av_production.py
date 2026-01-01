import sys
import types
import json
import os
from types import SimpleNamespace
from importlib import import_module


def _setup_workspace(tmpdir: str, channel_id: str):
    prompts_dir = os.path.join(tmpdir, "prompts")
    os.makedirs(os.path.join(prompts_dir, "system"), exist_ok=True)
    os.makedirs(os.path.join(prompts_dir, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(prompts_dir, "schemas"), exist_ok=True)

    with open(
        os.path.join(prompts_dir, "system", "av_production_system.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("system av")
    with open(
        os.path.join(prompts_dir, "tasks", "storyboard_shotlist.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("task storyboard")

    # minimal storyboard schema
    storyboard_schema = {"type": "object"}
    with open(
        os.path.join(prompts_dir, "schemas", "storyboard.schema.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(storyboard_schema, f)


def _inject_stubs(tmpdir: str):
    # config
    def get_config():
        return SimpleNamespace(
            engine_root=tmpdir,
            openai_api_key="test-key",
            openai_model="gpt-4o",
            timezone="UTC",
            budget=SimpleNamespace(
                monthly_cap_usd=150.0, stop_at_pct=0.85, elevenlabs_cap_usd=50.0
            ),
            hardware=SimpleNamespace(cpu_pause_pct=85.0, disk_free_pause_pct=10.0),
            youtube=None,
            elevenlabs=None,
        )

    cfg_mod = types.ModuleType("config")
    cfg_mod.get_config = get_config
    cfg_mod.EngineConfig = SimpleNamespace
    sys.modules["config"] = cfg_mod

    # stub OpenAI client to return a simple storyboard
    oc = types.ModuleType("utils.openai_client")

    class OpenAIJsonClient:
        def __init__(self, api_key: str, model: str) -> None:
            pass

        def run_json(
            self, system_prompt: str, user_prompt: str, input_payload: dict
        ) -> dict:
            return {"shots": [{"clip": 1}], "metadata": {}}

    oc.OpenAIJsonClient = OpenAIJsonClient
    sys.modules["utils.openai_client"] = oc

    # silence schema validation
    import importlib

    jv = importlib.import_module("utils.json_validate")
    jv.validate_json_against_schema = lambda *_a, **_k: None


def test_generate_storyboard_writes_json(tmp_path):
    tmpdir = str(tmp_path)
    channel_id = "channel_001_ai_tools"
    _setup_workspace(tmpdir, channel_id)
    _inject_stubs(tmpdir)

    mod = import_module("agents.audio_video_production")
    EnginePaths = import_module("utils.paths").EnginePaths

    cfg = sys.modules["config"].get_config()
    paths = EnginePaths(cfg.engine_root)

    agent = mod.AudioVideoProductionAgent(cfg, paths)

    run_id = "test_run"
    base = os.path.join(cfg.engine_root, "assets", "channels", channel_id, "pipeline")
    script_path = os.path.join(base, "scripts", "video01_script.json")
    storyboard_path = os.path.join(base, "video", "video01_storyboard.json")

    # write a simple script file
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump({"video_id": "v1"}, f)

    agent.generate_storyboard(
        channel_id=channel_id,
        run_id=run_id,
        script_path=script_path,
        output_path=storyboard_path,
    )

    assert os.path.exists(storyboard_path)
    with open(storyboard_path, "r", encoding="utf-8") as f:
        sb = json.load(f)
    assert "shots" in sb
