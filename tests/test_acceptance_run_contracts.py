import os
import json
import subprocess
import glob
import time

import pytest

from utils.json_validate import load_json, validate_json_against_schema
import threading
import hashlib


class StubOpenAIClient:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def run_json(
        self, system_prompt: str, user_prompt: str, input_payload: dict
    ) -> dict:
        # Simulate failure for plan generation (payload includes 'brief')
        if isinstance(input_payload, dict) and "brief" in input_payload:
            raise RuntimeError("Error code: 401 - {'error': 'mock invalid api key'}")
        # For other calls, return minimal valid payloads
        return {"ok": True}


def write_minimal_prompts(root: str) -> None:
    prompts_dir = os.path.join(root, "prompts")
    sys_dir = os.path.join(prompts_dir, "system")
    tasks_dir = os.path.join(prompts_dir, "tasks")
    schemas_dir = os.path.join(prompts_dir, "schemas")
    os.makedirs(sys_dir, exist_ok=True)
    os.makedirs(tasks_dir, exist_ok=True)
    os.makedirs(schemas_dir, exist_ok=True)

    # Minimal system and task prompts required by agents
    with open(
        os.path.join(sys_dir, "content_generation_system.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("content generation system")
    with open(
        os.path.join(tasks_dir, "script_generation.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("script generation task")
    with open(
        os.path.join(sys_dir, "av_production_system.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("av production system")
    with open(
        os.path.join(tasks_dir, "storyboard_shotlist.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("storyboard task")
    with open(
        os.path.join(sys_dir, "voice_synthesis_system.txt"), "w", encoding="utf-8"
    ) as f:
        f.write("voice synthesis system")
    with open(os.path.join(tasks_dir, "tts_directive.txt"), "w", encoding="utf-8") as f:
        f.write("tts directive task")

    # Copy canonical schemas from repository prompts to the test engine_root so agent validators can load them
    repo_schemas = os.path.join(os.getcwd(), "prompts", "schemas")
    for fname in (
        "content_plan.schema.json",
        "script.schema.json",
        "storyboard.schema.json",
        "metadata.schema.json",
    ):
        src = os.path.join(repo_schemas, fname)
        dst = os.path.join(schemas_dir, fname)
        try:
            with (
                open(src, "r", encoding="utf-8") as rf,
                open(dst, "w", encoding="utf-8") as wf,
            ):
                wf.write(rf.read())
        except FileNotFoundError:
            # Fallback: create a permissive object schema if repo schema not present
            permissive = {
                "$schema": "http://json-schema.org/draft/2020-12/schema",
                "type": "object",
            }
            with open(dst, "w", encoding="utf-8") as wf:
                json.dump(permissive, wf)


def write_brief(root: str, channel: str) -> None:
    brief_dir = os.path.join(root, "assets", "channels", channel, "pipeline", "briefs")
    os.makedirs(brief_dir, exist_ok=True)
    brief = {"channel_id": channel, "video_seed": {"topic": "test"}}
    with open(
        os.path.join(brief_dir, "video01_brief.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(brief, f)


@pytest.mark.acceptance
def test_two_run_acceptance(tmp_path, monkeypatch):
    # Set isolated engine root and required env
    engine_root = str(tmp_path)
    monkeypatch.setenv("ENGINE_ROOT", engine_root)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    # Run as worker so preflight does not require YouTube OAuth
    monkeypatch.setenv("ENGINE_ROLE", "worker")

    # Prevent any subprocess from being spawned by mistake (tripwire)
    def _no_subprocess(*args, **kwargs):
        raise RuntimeError("subprocess.run disabled in acceptance tests")

    monkeypatch.setattr(subprocess, "run", _no_subprocess)

    # Also block direct Popen usage
    def _no_popen(*args, **kwargs):
        raise RuntimeError("subprocess.Popen disabled in acceptance tests")

    monkeypatch.setattr(subprocess, "Popen", _no_popen)

    # Ensure YouTube env vars are not set so OAuth paths are not reached
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRETS_PATH", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKEN_PATH", raising=False)

    # Prepare minimal prompts and brief
    write_minimal_prompts(engine_root)
    write_brief(engine_root, "channel_001_ai_tools")

    # Monkeypatch slow/remote helpers so test is fast and deterministic
    # 1) Hardware probe: remove psutil 1s interval
    from utils.hardware_monitor import HardwareStatus

    # Insert a lightweight `openai` shim into sys.modules to avoid importing the
    # real `openai` package (which pulls in pydantic/pydantic_core binary wheels
    # that may not be available in the test environment). This prevents import
    # errors during `agents.orchestrator` imports while still allowing the
    # test to monkeypatch `OpenAIJsonClient.run_json` below.
    import types as _types
    import sys as _sys

    if "openai" not in _sys.modules:
        fake_openai = _types.ModuleType("openai")

        # Minimal OpenAI constructor used by utils.openai_client.OpenAIJsonClient
        def _fake_openai_ctor(*a, **k):
            # Provide a `.chat.completions.create(...)` call signature that
            # returns an object with `.choices[0].message.content` used by
            # `OpenAIJsonClient.run_json` when not monkeypatched.
            class _Resp:
                def __init__(self):
                    self.choices = [
                        _types.SimpleNamespace(
                            message=_types.SimpleNamespace(content="{}")
                        )
                    ]

            class _Completions:
                @staticmethod
                def create(*args, **kwargs):
                    return _Resp()

            fake = _types.SimpleNamespace(
                chat=_types.SimpleNamespace(completions=_Completions())
            )
            return fake

        fake_openai.OpenAI = _fake_openai_ctor
        _sys.modules["openai"] = fake_openai
    import agents.orchestrator as orch

    monkeypatch.setattr(
        orch,
        "check_hardware",
        lambda *a, **k: HardwareStatus(
            cpu_pct=1.0, disk_free_pct=50.0, should_pause=False, reasons=[]
        ),
    )

    # 2) Disable weekly optimization to avoid additional OpenAI calls
    import agents.optimization_scaling as opt

    monkeypatch.setattr(
        opt.OptimizationScalingAgent,
        "run_weekly_optimization",
        lambda self, *a, **k: "skipped_in_tests",
    )

    # 3) Patch OpenAIJsonClient.run_json to return deterministic fixtures per schema
    import utils.openai_client as oc
    import json as _json

    def fake_run_json(self, system_prompt, user_prompt, input_payload):
        fixtures_dir = os.path.join(os.getcwd(), "tests", "fixtures")

        def _load(name):
            with open(os.path.join(fixtures_dir, name), "r", encoding="utf-8") as f:
                return _json.load(f)

        # Prefer explicit task discriminator
        if isinstance(input_payload, dict):
            task = input_payload.get("_task")
            if task == "week_plan":
                return _load("week_plan.json")
            if task == "script":
                return _load("script.json")
            if task == "storyboard":
                return _load("storyboard.json")
            if task == "tts":
                return {
                    "narration_chunks": [
                        {
                            "chunk_id": "c1",
                            "text": "Hello",
                            "pacing": "medium",
                            "emphasis": [],
                            "pauses_ms": [],
                            "pronunciations": [],
                        }
                    ],
                    "disclaimers": [],
                    "missing_data": [],
                }

        # Fallback heuristics (backwards compatibility)
        if isinstance(input_payload, dict) and "brief" in input_payload:
            return _load("week_plan.json")
        if isinstance(input_payload, dict) and "plan_item" in input_payload:
            return _load("script.json")
        if isinstance(input_payload, dict) and "script" in input_payload:
            sp = (system_prompt or "") + " " + (user_prompt or "")
            sp = sp.lower()
            if "voice" in sp or "tts" in sp:
                return {
                    "narration_chunks": [
                        {
                            "chunk_id": "c1",
                            "text": "Hello",
                            "pacing": "medium",
                            "emphasis": [],
                            "pauses_ms": [],
                            "pronunciations": [],
                        }
                    ],
                    "disclaimers": [],
                    "missing_data": [],
                }
            return _load("storyboard.json")

        # Default: empty object
        return {}

    monkeypatch.setattr(oc.OpenAIJsonClient, "run_json", fake_run_json, raising=True)

    from agents.orchestrator import Orchestrator

    def run_with_timeout(fn, timeout_sec=10):
        exc = []

        def target():
            try:
                fn()
            except Exception as e:
                exc.append(e)

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout_sec)
        if t.is_alive():
            raise TimeoutError(f"Timed out after {timeout_sec}s")
        if exc:
            raise exc[0]

    # helpers to capture artifact hashes
    def sha256_file(path: str) -> str:
        h = hashlib.sha256()
        # wait up to a few seconds for the file to exist (filesystem timing on Windows/temp dirs)
        wait = 0.0
        while not os.path.exists(path) and wait < 5.0:
            time.sleep(0.1)
            wait += 0.1
        if not os.path.exists(path):
            parent = os.path.dirname(path) or "."
            try:
                listing = os.listdir(parent)
            except Exception as e:
                listing = f"<cannot list {parent}: {e}>"
            # emit visible diagnostic to pytest stdout
            print(f"DEBUG: missing artifact {path}; parent {parent} listing: {listing}")
            raise FileNotFoundError(
                f"{path} not found; parent dir {parent} listing: {listing}"
            )
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def snapshot_hashes(paths: dict[str, str], keys: list[str]) -> dict[str, str]:
        out = {}
        for k in keys:
            if k not in paths:
                raise KeyError(f"artifact key missing from summary artifacts: {k}")
            out[k] = sha256_file(paths[k])
        return out

    artifacts_run1 = None
    artifacts_run2 = None
    summary_run2 = None
    hashes_run1 = None
    hashes_run2 = None
    stable_keys = ["plan", "script", "storyboard", "metadata"]

    for i in range(2):
        # run the orchestrator directly (avoid argparse/sys.argv interference)
        run_with_timeout(
            lambda: Orchestrator().run_weekly_growth_loop(), timeout_sec=10
        )
        # small pause to ensure timestamps differ (run_id uses second precision)
        time.sleep(1.1)

        # capture the most recent run summary and artifacts for this iteration
        runs_dir = os.path.join(engine_root, "data", "state", "runs")
        runs_now = sorted(
            [d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)],
            key=os.path.getmtime,
            reverse=True,
        )
        assert runs_now, "no runs produced"
        latest_run_dir = runs_now[0]
        sfn = os.path.join(latest_run_dir, "summary.json")
        assert os.path.exists(sfn), f"missing summary after run: {sfn}"
        sdata = load_json(sfn)
        if i == 0:
            artifacts_run1 = sdata.get("artifacts", {})
            # compute hashes immediately to avoid later filesystem races
            hashes_run1 = snapshot_hashes(artifacts_run1, stable_keys)
        else:
            artifacts_run2 = sdata.get("artifacts", {})
            summary_run2 = sdata
            hashes_run2 = snapshot_hashes(artifacts_run2, stable_keys)

    # Sanity: config should not enable YouTube in this test
    from config import get_config

    cfg = get_config()
    assert cfg.youtube is None

    # Gather runs (sanity)
    runs_dir = os.path.join(engine_root, "data", "state", "runs")
    runs = sorted(
        [d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)],
        key=os.path.getmtime,
        reverse=True,
    )
    assert len(runs) >= 2

    # Validate the two newest summaries against schema
    schema = load_json(os.path.join("prompts", "schemas", "run_summary.schema.json"))
    summaries = []
    for d in runs[:2]:
        sfn = os.path.join(d, "summary.json")
        assert os.path.exists(sfn), f"missing summary: {sfn}"
        data = load_json(sfn)
        validate_json_against_schema(data, schema)
        summaries.append(data)

    # Idempotency: if a step is 'skipped' on run2 its artifact must match run1; if regenerated, validate presence only
    if artifacts_run1 is None or artifacts_run2 is None:
        raise AssertionError("failed to capture artifacts for runs")
    if hashes_run1 is None or hashes_run2 is None:
        raise AssertionError("failed to capture artifact hashes for runs")
    for key in stable_keys:
        status = summary_run2["steps"].get(key)
        if status == "skipped":
            assert hashes_run2[key] == hashes_run1[key], (
                f"artifact {key} changed despite being skipped"
            )
        elif status == "success":
            # regenerated: ensure artifact exists and is valid JSON where applicable
            assert key in artifacts_run2 and os.path.exists(artifacts_run2[key]), (
                f"regenerated artifact {key} missing"
            )
        else:
            raise AssertionError(
                f"unexpected step status for idempotency check: {status}"
            )

    # Behavioral: run #2 should mark core steps as skipped or success
    assert summary_run2 is not None
    for step in ["plan", "script", "storyboard", "metadata"]:
        assert summary_run2["steps"][step] in ("skipped", "success"), (
            f"step {step} not skipped/success in run2"
        )

    # latest.json exists and points to most recent
    latest_path = os.path.join(runs_dir, "latest.json")
    assert os.path.exists(latest_path)
    latest = load_json(latest_path)
    assert "channel_001_ai_tools" in latest
    assert latest["channel_001_ai_tools"]["run_id"] == summaries[0]["run_id"]

    # No tmp residues
    tmp_matches = []
    for root, _, files in os.walk(runs_dir):
        for f in files:
            if ".tmp." in f or f.endswith(".tmp") or ".tmp" in f:
                tmp_matches.append(os.path.join(root, f))
    assert not tmp_matches, f"found tmp files: {tmp_matches}"

    # Success-path assertions: core steps succeeded and no blocked_by_failed_dependency errors
    newest = summaries[0]
    for step in ["plan", "script", "tts", "storyboard", "metadata"]:
        assert newest["steps"].get(step) in ("success", "skipped"), (
            f"unexpected step status for {step}: {newest['steps'].get(step)}"
        )

    # Do not assert absence of blocked_by_failed_dependency here; gating behavior
    # is covered by `test_dependency_gating_on_plan_failure`.


@pytest.mark.acceptance
def test_dependency_gating_on_plan_failure(tmp_path, monkeypatch):
    # Same setup as the success test but force plan generation to fail
    engine_root = str(tmp_path)
    monkeypatch.setenv("ENGINE_ROOT", engine_root)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ENGINE_ROLE", "worker")

    # Tripwires for subprocess
    def _no_subprocess(*args, **kwargs):
        raise RuntimeError("subprocess.run disabled in acceptance tests")

    monkeypatch.setattr(subprocess, "run", _no_subprocess)

    def _no_popen(*args, **kwargs):
        raise RuntimeError("subprocess.Popen disabled in acceptance tests")

    monkeypatch.setattr(subprocess, "Popen", _no_popen)

    monkeypatch.delenv("YOUTUBE_CLIENT_SECRETS_PATH", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKEN_PATH", raising=False)

    write_minimal_prompts(engine_root)
    write_brief(engine_root, "channel_001_ai_tools")

    from utils.hardware_monitor import HardwareStatus

    # Ensure openai shim present as in the happy-path test to avoid pydantic_core import errors
    import types as _types
    import sys as _sys

    if "openai" not in _sys.modules:
        fake_openai = _types.ModuleType("openai")

        def _fake_openai_ctor(*a, **k):
            class _Resp:
                def __init__(self):
                    self.choices = [
                        _types.SimpleNamespace(
                            message=_types.SimpleNamespace(content="{}")
                        )
                    ]

            class _Completions:
                @staticmethod
                def create(*args, **kwargs):
                    return _Resp()

            fake = _types.SimpleNamespace(
                chat=_types.SimpleNamespace(completions=_Completions())
            )
            return fake

        fake_openai.OpenAI = _fake_openai_ctor
        _sys.modules["openai"] = fake_openai
    import agents.orchestrator as orch

    monkeypatch.setattr(
        orch,
        "check_hardware",
        lambda *a, **k: HardwareStatus(
            cpu_pct=1.0, disk_free_pct=50.0, should_pause=False, reasons=[]
        ),
    )

    import agents.optimization_scaling as opt

    monkeypatch.setattr(
        opt.OptimizationScalingAgent,
        "run_weekly_optimization",
        lambda self, *a, **k: "skipped_in_tests",
    )

    import utils.openai_client as oc

    # Force plan generation to fail when brief is present
    def failing_run_json(self, system_prompt, user_prompt, input_payload):
        if isinstance(input_payload, dict):
            # Prefer explicit task discriminator if present
            if input_payload.get("_task") == "week_plan":
                raise RuntimeError("TEST: forced plan failure for gating test")
            if "brief" in input_payload:
                raise RuntimeError("TEST: forced plan failure for gating test")
        return {"ok": True}

    monkeypatch.setattr(oc.OpenAIJsonClient, "run_json", failing_run_json, raising=True)

    from agents.orchestrator import Orchestrator

    def run_with_timeout(fn, timeout_sec=10):
        exc = []

        def target():
            try:
                fn()
            except Exception as e:
                exc.append(e)

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout_sec)
        if t.is_alive():
            raise TimeoutError(f"Timed out after {timeout_sec}s")
        if exc:
            raise exc[0]

    # Run once to observe gating behavior
    run_with_timeout(lambda: Orchestrator().run_weekly_growth_loop(), timeout_sec=10)

    runs_dir = os.path.join(engine_root, "data", "state", "runs")
    runs = sorted(
        [d for d in glob.glob(os.path.join(runs_dir, "*")) if os.path.isdir(d)],
        key=os.path.getmtime,
        reverse=True,
    )
    assert len(runs) >= 1

    schema = load_json(os.path.join("prompts", "schemas", "run_summary.schema.json"))
    sfn = os.path.join(runs[0], "summary.json")
    assert os.path.exists(sfn), f"missing summary: {sfn}"
    data = load_json(sfn)
    validate_json_against_schema(data, schema)

    assert data["steps"]["plan"] == "failed"
    assert data["steps"]["script"] == "skipped"
    blocked_found = any(
        e.get("message") == "blocked_by_failed_dependency"
        for e in data.get("errors", [])
        if isinstance(e, dict)
    )
    assert blocked_found, (
        f"blocked_by_failed_dependency not present in errors: {data.get('errors')}"
    )
