import sys
import types
import json
import os
from types import SimpleNamespace
from importlib import import_module


def _setup_workspace(tmpdir: str, channel_id: str):
    prompts_dir = os.path.join(tmpdir, "prompts")
    os.makedirs(os.path.join(prompts_dir, "tasks"), exist_ok=True)
    os.makedirs(os.path.join(prompts_dir, "variants"), exist_ok=True)

    # base task prompts
    with open(os.path.join(prompts_dir, "tasks", "script_generation.txt"), "w", encoding="utf-8") as f:
        f.write("base script prompt")
    with open(os.path.join(prompts_dir, "tasks", "upload_metadata.txt"), "w", encoding="utf-8") as f:
        f.write("base upload metadata prompt")

    # ensure prompts/schemas dir exists for other agents
    os.makedirs(os.path.join(prompts_dir, "schemas"), exist_ok=True)

    # system prompt and optimization task prompt + schema
    os.makedirs(os.path.join(prompts_dir, "system"), exist_ok=True)
    with open(os.path.join(prompts_dir, "system", "optimization_scaling_system.txt"), "w", encoding="utf-8") as f:
        f.write("system optimization")
    with open(os.path.join(prompts_dir, "tasks", "optimization_autopatch.txt"), "w", encoding="utf-8") as f:
        f.write("task autopatch")
    # minimal schema accepting object
    with open(os.path.join(prompts_dir, "schemas", "optimization_autopatch.schema.json"), "w", encoding="utf-8") as f:
        json.dump({"type": "object"}, f)

    # make rollup dir empty (agent should handle missing rollups)
    analytics_dir = os.path.join(tmpdir, "assets", "channels", channel_id, "pipeline", "analytics")
    os.makedirs(analytics_dir, exist_ok=True)


def _inject_stubs(tmpdir: str):
    # config.get_config
    def get_config():
        return SimpleNamespace(
            engine_root=tmpdir,
            openai_api_key="test-key",
            openai_model="gpt-4o",
            timezone="UTC",
            budget=SimpleNamespace(monthly_cap_usd=150.0, stop_at_pct=0.85, elevenlabs_cap_usd=50.0),
            hardware=SimpleNamespace(cpu_pause_pct=85.0, disk_free_pause_pct=10.0),
            youtube=None,
            elevenlabs=None,
        )

    cfg_mod = types.ModuleType("config")
    cfg_mod.get_config = get_config
    cfg_mod.EngineConfig = SimpleNamespace
    sys.modules["config"] = cfg_mod

    # stub OpenAI client
    oc = types.ModuleType("utils.openai_client")
    class OpenAIJsonClient:
        def __init__(self, api_key: str, model: str) -> None:
            pass
        def run_json(self, system_prompt: str, user_prompt: str, input_payload: dict) -> dict:
            # Return a plan with one patch touching script_generation.txt
            return {
                "patches": [
                    {"target_rel_path": "tasks/script_generation.txt", "operations": [{"op": "append", "text": "\n// variant"}]}
                ],
                "variant_name": "test_variant",
                "notes": "auto",
                "ab_test": {"enabled": True, "allocation": {"base": 0.5, "variant": 0.5}, "videos": 6, "success_metrics": []}
            }
    oc.OpenAIJsonClient = OpenAIJsonClient
    sys.modules["utils.openai_client"] = oc

    # ensure fresh import for utils.prompt_manager
    sys.modules.pop("utils.prompt_manager", None)


def test_run_weekly_optimization_creates_autopatch(tmp_path):
    tmpdir = str(tmp_path)
    channel_id = "channel_001_ai_tools"
    _setup_workspace(tmpdir, channel_id)
    _inject_stubs(tmpdir)

    # import the agent fresh
    mod = import_module("agents.optimization_scaling")
    EnginePaths = import_module("utils.paths").EnginePaths

    cfg = sys.modules["config"].get_config()
    paths = EnginePaths(cfg.engine_root)

    agent = mod.OptimizationScalingAgent(cfg, paths)

    out_path = agent.run_weekly_optimization(channel_id=channel_id)

    assert os.path.exists(out_path), "autopatch plan not written"

    with open(out_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    assert "variant_manifest_rel" in plan

    # state should have been updated
    state_path = os.path.join(cfg.engine_root, "data", "state", "orchestrator_state.json")
    assert os.path.exists(state_path)
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    assert channel_id in state.get("active_variants", {})
