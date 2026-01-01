import os
from types import SimpleNamespace

from utils.db import init_db
from utils.json_validate import save_json
from utils.paths import EnginePaths
from agents.publishing_seo import PublishingSEOAgent


class FakeYTClient:
    def __init__(self, _cfg):
        pass

    def upload_video_resumable(self, **kwargs):
        return SimpleNamespace(youtube_video_id="yt_123", status="uploaded")


def test_upload_binds_youtube_id_and_logs_event(tmp_path, monkeypatch):
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    paths = EnginePaths(root)
    init_db(paths.db_path)

    # minimal metadata
    meta_path = os.path.join(root, "assets", "meta.json")
    save_json(
        meta_path,
        {
            "video_id": "v1",
            "title": "T",
            "description": "D",
            "tags": [],
            "privacy_status": "private",
        },
    )

    # dummy video file
    vid_path = os.path.join(root, "assets", "final.mp4")
    with open(vid_path, "wb") as f:
        f.write(b"\x00\x00")

    # stub cfg
    cfg = SimpleNamespace(
        engine_root=root,
        youtube=SimpleNamespace(client_secrets_path="s", token_path="t"),
        enable_auto_promote=False,
    )

    # patch YT client constructor used in agent
    monkeypatch.setattr("agents.publishing_seo.YouTubeClient", FakeYTClient)

    agent = PublishingSEOAgent(cfg, paths)
    yt_id = agent.upload_to_youtube(
        channel_id="ch1",
        run_id="r1",
        final_video_path=vid_path,
        metadata_path=meta_path,
        thumbnail_path=None,
    )
    assert yt_id == "yt_123"

    # verify DB row
    import sqlite3

    con = sqlite3.connect(paths.db_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT youtube_video_id, status, published_ts FROM videos WHERE channel_id=? AND video_id=?",
        ("ch1", "v1"),
    ).fetchone()
    assert row is not None
    assert row["youtube_video_id"] == "yt_123"
    assert row["status"] == "published"
    assert row["published_ts"] is not None

    ev = con.execute(
        "SELECT event, payload_json FROM orchestrator_events WHERE event='video_published'"
    ).fetchone()
    assert ev is not None
    assert "yt_123" in ev["payload_json"]
    con.close()
