import os
import sqlite3
from pathlib import Path

import pytest

from config import get_config
from utils.paths import EnginePaths
from utils.state import save_state, OrchestratorState
from utils.db import init_db
from agents.optimization_scaling import OptimizationScalingAgent


def test_enable_auto_promote_default_and_blocked_apply(monkeypatch, tmp_path: Path):
    # Ensure no env var is set and ENGINE_ROOT is our temp dir
    monkeypatch.delenv("ENABLE_AUTO_PROMOTE", raising=False)
    monkeypatch.setenv("ENGINE_ROOT", str(tmp_path))

    cfg = get_config()
    # Safety invariant: default must be False
    assert cfg.enable_auto_promote is False

    paths = EnginePaths(str(tmp_path))
    paths.ensure_dirs()

    # Initialize DB schema so agent and helpers can query safely
    init_db(paths.db_path)

    # Write a minimal orchestrator state with an AB test configured for our channel
    state_path = tmp_path / "data" / "state" / "orchestrator_state.json"
    state = OrchestratorState(version=1, active_variants={}, ab_tests={
        "test_channel": {"variant_manifest_rel": "variants/foo.json"}
    })
    save_state(str(state_path), state)

    # Stub deterministic scorer to force a 'promote' suggestion without hitting DB
    def fake_score_ab_test(db_path, channel_id, variant_manifest_rel, **kwargs):
        return {"suggestion": "promote", "base_score": 0.1, "variant_score": 0.2, "delta": 1.0}

    monkeypatch.setattr("agents.optimization_scaling.score_ab_test", fake_score_ab_test)

    agent = OptimizationScalingAgent(cfg, paths)

    # Call with dry_run=False to simulate attempted apply; because ENABLE_AUTO_PROMOTE is False,
    # the system must not mutate state (applied==False) and must remain a safe no-op.
    result = agent.score_ab_test("test_channel", dry_run=False)

    assert result["decision"] == "promote"
    assert result["applied"] is False

    # promotion_suggestions.json should be written even in guarded mode
    suggestions_path = tmp_path / "assets" / "channels" / "test_channel" / "pipeline" / "optimization" / "promotion_suggestions.json"
    assert suggestions_path.exists()

    # DB should contain no promotion_suggestion orchestrator event (apply blocked)
    conn = sqlite3.connect(paths.db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM orchestrator_events WHERE event = 'promotion_suggestion'")
    count = cur.fetchone()[0]
    conn.close()

    assert count == 0
