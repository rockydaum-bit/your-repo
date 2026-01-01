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

    # write minimal prompt files
    with open(
        os.path.join(prompts_dir, "system", "content_generation_system.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("system content")
    with open(
        os.path.join(prompts_dir, "tasks", "script_generation.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write("task content")

    # minimal schemas that accept simple dicts
    content_plan_schema = {"type": "object"}
    script_schema = {"type": "object"}
    with open(
        os.path.join(prompts_dir, "schemas", "content_plan.schema.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(content_plan_schema, f)
    with open(
        os.path.join(prompts_dir, "schemas", "script.schema.json"),
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(script_schema, f)


def _inject_stubs(tmpdir: str):
    # config.get_config
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
    # provide EngineConfig symbol for imports in agents
    cfg_mod.EngineConfig = SimpleNamespace
    sys.modules["config"] = cfg_mod

    # ensure any previously imported agent modules are reloaded when tests run
    for m in [
        "agents.content_generation",
        "utils.openai_client",
    ]:
        sys.modules.pop(m, None)

    # stub OpenAIJsonClient
    oc = types.ModuleType("utils.openai_client")

    class OpenAIJsonClient:
        def __init__(self, api_key: str, model: str) -> None:
            pass

        def run_json(
            self, system_prompt: str, user_prompt: str, input_payload: dict
        ) -> dict:
            # return a plausible script structure
            return {"week_plans": [{"videos": [{"video_id": "v1"}]}], "video_id": "v1"}

    oc.OpenAIJsonClient = OpenAIJsonClient
    sys.modules["utils.openai_client"] = oc

    # silence schema validation
    import importlib

    jv = importlib.import_module("utils.json_validate")
    jv.validate_json_against_schema = lambda *_a, **_k: None


def test_generate_plan_and_script(tmp_path):
    tmpdir = str(tmp_path)
    _setup_workspace(tmpdir)
    _inject_stubs(tmpdir)

    # import module after stubs
    mod = import_module("agents.content_generation")
    EnginePaths = import_module("utils.paths").EnginePaths

    cfg = sys.modules["config"].get_config()
    paths = EnginePaths(cfg.engine_root)

    agent = mod.ContentGenerationAgent(cfg, paths)

    channel_id = "channel_001_ai_tools"
    run_id = "test_run"
    base = os.path.join(cfg.engine_root, "assets", "channels", channel_id, "pipeline")
    brief_path = os.path.join(base, "briefs", "video01_brief.json")
    plan_path = os.path.join(base, "plans", "video01_plan.json")
    script_path = os.path.join(base, "scripts", "video01_script.json")

    # create brief
    os.makedirs(os.path.dirname(brief_path), exist_ok=True)
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump({"channel_id": channel_id, "video_seed": {"topic": "t"}}, f)

    agent.generate_plan(
        channel_id=channel_id,
        run_id=run_id,
        brief_path=brief_path,
        output_path=plan_path,
    )
    assert os.path.exists(plan_path)

    agent.generate_script(
        channel_id=channel_id,
        run_id=run_id,
        plan_item_path=plan_path,
        output_path=script_path,
    )
    assert os.path.exists(script_path)

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)
    assert "video_id" in script
