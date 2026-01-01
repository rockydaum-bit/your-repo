import sys
import types
import json
import os
from importlib import import_module
from types import SimpleNamespace


def _inject_stubs(tmpdir: str):
    # Stub config.get_config
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
    cfg_mod.get_config = get_config  # type: ignore[attr-defined]
    sys.modules["config"] = cfg_mod  # type: ignore[attr-defined]

    # Stub utils.hardware_monitor
    hw_mod = types.ModuleType("utils.hardware_monitor")
    class HWStatus:
        def __init__(self):
            self.cpu_pct = 0.0
            self.disk_free_pct = 100.0
            self.should_pause = False
            self.reasons = []
    def check_hardware(engine_root: str, cpu_pause_pct: float, disk_free_pause_pct: float):
        return HWStatus()
    hw_mod.check_hardware = check_hardware  # type: ignore[attr-defined]
    sys.modules["utils.hardware_monitor"] = hw_mod  # type: ignore[attr-defined]

    # Stub agent modules with minimal implementations
    def make_agent(module_name, methods: dict):
        m = types.ModuleType(module_name)
        for cls_name, cls_impl in methods.items():
            setattr(m, cls_name, cls_impl)
        sys.modules[module_name] = m

    class ContentStub:
        def __init__(self, cfg, paths):
            self.cfg = cfg
            self.paths = paths
        def generate_plan(self, channel_id, run_id, brief_path, output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            plan = {"video_id": f"{channel_id}_video01"}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(plan, f)
        def generate_script(self, channel_id, run_id, plan_item_path, output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            script = {"video_id": f"{channel_id}_video01", "narration_chunks": [{"text": "hello"}]}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(script, f)

    class VoiceStub:
        def __init__(self, cfg, paths):
            self.cfg = cfg
            self.paths = paths
        def prepare_tts(self, channel_id, run_id, script_path, output_path):
            # read script and write it back (merge step)
            with open(script_path, "r", encoding="utf-8") as f:
                script = json.load(f)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(script, f)

    class AVStub:
        def __init__(self, cfg, paths):
            self.cfg = cfg
            self.paths = paths
        def generate_storyboard(self, channel_id, run_id, script_path, output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            sb = {"shots": []}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(sb, f)

    class PubStub:
        def __init__(self, cfg, paths):
            self.cfg = cfg
            self.paths = paths
        def generate_upload_metadata(self, channel_id, run_id, script_path, output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            meta = {"titles": ["Test Title"], "selected_title": "Test Title", "description": ""}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(meta, f)

    make_agent("agents.content_generation", {"ContentGenerationAgent": ContentStub})
    make_agent("agents.voice_synthesis", {"VoiceSynthesisAgent": VoiceStub})
    make_agent("agents.audio_video_production", {"AudioVideoProductionAgent": AVStub})
    make_agent("agents.publishing_seo", {"PublishingSEOAgent": PubStub})
    # analytics and optimization modules are not required for _one_video_pipeline but stub them
    make_agent("agents.analytics_metrics", {"AnalyticsMetricsAgent": type("A", (), {"__init__": lambda self, cfg, paths: None})})
    make_agent("agents.optimization_scaling", {"OptimizationScalingAgent": type("O", (), {"__init__": lambda self, cfg, paths: None})})


def test_one_video_pipeline_creates_artifacts(tmp_path):
    tmpdir = str(tmp_path)
    _inject_stubs(tmpdir)

    # Import the orchestrator after stubs are in place
    orch_mod = import_module("agents.orchestrator")  # type: ignore[attr-defined]
    Orchestrator = orch_mod.Orchestrator

    orch = Orchestrator()

    channel_id = "channel_001_ai_tools"
    run_id = "smoke_test_run"

    artifacts = orch._one_video_pipeline(channel_id=channel_id, run_id=run_id)

    # All returned paths should exist
    for k, p in artifacts.items():
        assert os.path.exists(p), f"artifact {k} not created at {p}"

    # brief should contain the seed JSON
    with open(artifacts["brief"], "r", encoding="utf-8") as f:
        brief = json.load(f)
    assert brief.get("channel_id") == channel_id


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
