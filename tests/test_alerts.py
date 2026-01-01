import os
from utils.paths import EnginePaths
from utils.db import init_db
from utils.alerts import raise_alert, get_recent_alerts

def test_raise_and_get_recent_alerts(tmp_path):
    root = str(tmp_path)
    paths = EnginePaths(root)
    init_db(paths.db_path)

    # No alerts initially
    alerts = get_recent_alerts(paths.db_path)
    assert alerts == []

    # Insert two alerts for same channel
    raise_alert(
        db_path=paths.db_path,
        channel_id="ch1",
        run_id="run-1",
        severity="warning",
        code="TEST_WARN",
        message="First warning",
        meta={"foo": "bar"},
    )
    raise_alert(
        db_path=paths.db_path,
        channel_id="ch1",
        run_id="run-2",
        severity="error",
        code="TEST_ERR",
        message="Second error",
        meta={"baz": 123},
    )

    # Fetch most recent first
    alerts = get_recent_alerts(paths.db_path, channel_id="ch1", limit=10)
    assert len(alerts) == 2
    assert alerts[0].code == "TEST_ERR"
    assert alerts[0].severity == "error"
    assert alerts[1].code == "TEST_WARN"
    assert alerts[1].severity == "warning"

    # Global fetch also sees them
    all_alerts = get_recent_alerts(paths.db_path, limit=10)
    assert len(all_alerts) >= 2
