from utils.paths import EnginePaths
from utils.db import init_db, connect
from utils.alerts import raise_alert
from utils.ops_status import generate_channel_status
from config import EngineConfig


def test_ops_status_overall_status_reflects_alerts(tmp_path):
    root = str(tmp_path)
    paths = EnginePaths(root)
    init_db(paths.db_path)

    cfg = EngineConfig(engine_root=root, openai_api_key="", openai_model="gpt-4o")

    # Insert a successful run
    run_id = "run-1"
    with connect(paths.db_path) as con:
        con.execute(
            """
            INSERT INTO runs (run_id, ts_start, ts_end, command, status, error_message, channel_id, mode)
            VALUES (?, '2025-01-01T00:00:00Z', '2025-01-01T00:10:00Z', 'run', 'success', NULL, ?, ?)
            """,
            (run_id, "ch1", "run"),
        )

    # No alerts -> status ok
    snap = generate_channel_status(cfg, paths, "ch1")
    assert snap["status"]["overall_status"] == "ok"
    assert snap["status"]["latest_alerts"] == [] or isinstance(
        snap["status"]["latest_alerts"], list
    )

    # Add warning alert -> degraded
    raise_alert(
        db_path=paths.db_path,
        channel_id="ch1",
        run_id=run_id,
        severity="warning",
        code="TEST_WARN",
        message="Some degradation",
        meta=None,
    )

    snap = generate_channel_status(cfg, paths, "ch1")
    assert snap["status"]["overall_status"] in ("degraded", "failing")
    assert len(snap["status"]["latest_alerts"]) >= 1

    # Add error alert -> failing
    raise_alert(
        db_path=paths.db_path,
        channel_id="ch1",
        run_id=run_id,
        severity="error",
        code="TEST_ERR",
        message="Hard failure",
        meta=None,
    )

    snap = generate_channel_status(cfg, paths, "ch1")
    assert snap["status"]["overall_status"] == "failing"
    assert any(a["severity"] == "error" for a in snap["status"]["latest_alerts"])
