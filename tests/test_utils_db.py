import os
import json
from datetime import datetime
from utils import db


def test_db_init_and_costs(tmp_path):
    db_path = os.path.join(str(tmp_path), "data", "revenue.db")
    # initialize DB
    db.init_db(db_path)

    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    db.insert_cost(db_path, ts, "openai", "api", 12.34, run_id="r1", notes="note")

    prefix = ts[:7]  # YYYY-MM
    total = db.sum_costs_month(db_path, prefix)
    assert total >= 12.34

    # log an event
    db.log_event(db_path, ts, "INFO", "test_event", json.dumps({"k": "v"}))

    # insert analytics daily
    db.insert_analytics_daily(
        db_path, ts, "channel_x", "vid1", 100.0, 1.5, 0.1, 30.0, 2.5, 1, 123.45
    )

    # direct insert into videos table and then list_recent_videos
    with db.connect(db_path) as con:
        con.execute(
            "INSERT INTO videos (channel_id, video_id, run_id, topic, status) VALUES (?, ?, ?, ?, ?)",
            ("channel_x", "vid1", "r1", "topic", "published"),
        )

    recent = db.list_recent_videos(db_path, "channel_x")
    assert any(v["video_id"] == "vid1" for v in recent)

    # test prompt assignments upsert/get
    db.upsert_prompt_assignment(
        db_path,
        ts,
        "channel_x",
        "vid1",
        "base",
        variant_manifest_rel="m.json",
        notes="n",
    )
    arm = db.get_prompt_assignment(db_path, "channel_x", "vid1")
    assert arm == "base"
