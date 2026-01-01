import sys
import types
import json
import os
from types import SimpleNamespace
from importlib import import_module


def _setup_workspace(tmpdir: str):
    prompts_dir = os.path.join(tmpdir, "prompts")
    os.makedirs(os.path.join(prompts_dir, "system"), exist_ok=True)
    os.makedirs(os.path.join(prompts_dir, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(prompts_dir, "schemas"), exist_ok=True)

    with open(
        os.path.join(prompts_dir, "system", "voice_synthesis_system.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("system voice")
    with open(
        os.path.join(prompts_dir, "tasks", "tts_directive.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("task tts")

    # minimal script schema
    script_schema = {"type": "object"}
    with open(
        os.path.join(prompts_dir, "schemas", "script.schema.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(script_schema, f)


def _inject_stubs(tmpdir: str):
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

    # stub OpenAI client to return narration_chunks
    oc = types.ModuleType("utils.openai_client")

    class OpenAIJsonClient:
        def __init__(self, api_key: str, model: str) -> None:
            pass

        def run_json(
            self, system_prompt: str, user_prompt: str, input_payload: dict
        ) -> dict:
            return {"narration_chunks": [{"text": "hello world"}], "disclaimers": []}

    oc.OpenAIJsonClient = OpenAIJsonClient
    sys.modules["utils.openai_client"] = oc

    # ensure fresh imports for agent modules so they pick up the stubbed openai client
    for m in ["agents.voice_synthesis", "utils.openai_client"]:
        sys.modules.pop(m, None)

    # silence schema validation
    import importlib

    jv = importlib.import_module("utils.json_validate")
    jv.validate_json_against_schema = lambda *_a, **_k: None


def test_prepare_tts_writes_merged_json(tmp_path):
    tmpdir = str(tmp_path)
    _setup_workspace(tmpdir)
    _inject_stubs(tmpdir)

    mod = import_module("agents.voice_synthesis")
    EnginePaths = import_module("utils.paths").EnginePaths

    cfg = sys.modules["config"].get_config()
    paths = EnginePaths(cfg.engine_root)

    agent = mod.VoiceSynthesisAgent(cfg, paths)
    # ensure the agent uses our stubbed OpenAIJsonClient (in case module was previously imported)
    # override client directly to ensure no network calls
    agent.client = types.SimpleNamespace(
        run_json=lambda *a, **k: {
            "narration_chunks": [{"text": "hello world"}],
            "disclaimers": [],
        }
    )

    channel_id = "channel_001_ai_tools"
    run_id = "test_run"
    base = os.path.join(cfg.engine_root, "assets", "channels", channel_id, "pipeline")
    script_path = os.path.join(base, "scripts", "video01_script.json")

    # write a base script file
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump({"video_id": "v1"}, f)

    out_path = script_path
    agent.prepare_tts(
        channel_id=channel_id,
        run_id=run_id,
        script_path=script_path,
        output_path=out_path,
    )

    assert os.path.exists(out_path)
    with open(out_path, "r", encoding="utf-8") as f:
        merged = json.load(f)
    assert "narration_chunks" in merged
