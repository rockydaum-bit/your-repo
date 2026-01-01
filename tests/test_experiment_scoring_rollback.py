import os
import sqlite3
from types import SimpleNamespace

from utils.db import init_db
from utils.json_validate import save_json, load_json
from utils.paths import EnginePaths
from agents.optimization_scaling import OptimizationScalingAgent


def seed_assignment(con, channel_id, video_id, arm, manifest_rel="m.json"):
    con.execute(
        "INSERT OR REPLACE INTO prompt_assignments (ts, channel_id, video_id, arm, variant_manifest_rel, notes) VALUES (?, ?, ?, ?, ?, ?)",
        ("2025-01-01T00:00:00Z", channel_id, video_id, arm, manifest_rel, "t"),
    )


def seed_analytics(con, channel_id, video_id, views, revenue, avd):
    con.execute(
        """
        INSERT INTO analytics_daily (ts, channel_id, video_id, views, revenue_usd, avg_view_duration_sec)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2025-01-01T00:00:00Z", channel_id, video_id, views, revenue, avd),
    )


def test_score_ab_test_rollback(tmp_path):
    root = str(tmp_path)
    paths = EnginePaths(root)
    init_db(paths.db_path)

    state_dir = os.path.join(root, "data", "state")
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "orchestrator_state.json")
    save_json(
        state_path,
        {
            "version": 1,
            "active_variants": {
                "ch1": {"tasks/script_generation.txt": "prompts/variants/ch1/v1.txt"}
            },
            "ab_tests": {
                "ch1": {"enabled": True, "videos": 6, "variant_manifest_rel": "m.json"}
            },
        },
    )

    con = sqlite3.connect(paths.db_path)

    for i in range(6):
        seed_assignment(con, "ch1", f"b{i}", "base")
        seed_assignment(con, "ch1", f"v{i}", "variant")
        seed_analytics(
            con, "ch1", f"b{i}", views=100, revenue=1.0, avd=60
        )  # base rpm=0.01
        seed_analytics(
            con, "ch1", f"v{i}", views=100, revenue=0.8, avd=55
        )  # variant rpm=0.008 (down)
    con.commit()
    con.close()

    cfg = SimpleNamespace(
        engine_root=root,
        enable_auto_promote=False,
        auto_promote_min_videos=6,
        auto_promote_min_days=7,
    )

    agent = OptimizationScalingAgent(cfg, paths)
    out = agent.score_ab_test("ch1", dry_run=True)
    assert out["decision"] == "rollback"

    sugg = load_json(
        os.path.join(
            root,
            "assets",
            "channels",
            "ch1",
            "pipeline",
            "optimization",
            "promotion_suggestions.json",
        )
    )
    assert sugg["decision"] == "rollback"
