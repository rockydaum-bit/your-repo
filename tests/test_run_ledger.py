import sqlite3
from utils.paths import EnginePaths
from utils.db import init_db, insert_run_start, update_run_end


def test_run_ledger_inserts_and_updates(tmp_path):
    root = str(tmp_path)
    paths = EnginePaths(root)
    init_db(paths.db_path)

    run_id = "ch1-run-123"
    channel_id = "ch1"
    mode = "run"

    insert_run_start(paths.db_path, run_id, channel_id, mode)
    update_run_end(paths.db_path, run_id, "failed", "boom")

    con = sqlite3.connect(paths.db_path)
    try:
        cur = con.execute(
            "SELECT run_id, channel_id, mode, status, error_message FROM runs"
        )
        row = cur.fetchone()
        cur.close()
    finally:
        con.close()

    # row is a tuple: (run_id, channel_id, mode, status, error_message)
    assert row is not None
    assert row[0] == run_id
    assert row[1] == channel_id
    assert row[2] == mode
    assert row[3] == "failed"
    assert row[4] == "boom"
