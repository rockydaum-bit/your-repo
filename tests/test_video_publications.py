import os
import sqlite3
from utils.paths import EnginePaths
from utils.db import init_db, upsert_video_publication


def test_upsert_video_publication_roundtrip(tmp_path):
    root = str(tmp_path)
    paths = EnginePaths(root)
    os.makedirs(os.path.dirname(paths.db_path), exist_ok=True)
    init_db(paths.db_path)

    upsert_video_publication(
        paths.db_path,
        channel_id="ch1",
        video_id="v1",
        platform="youtube",
        platform_video_id="yt_123",
        run_id=None,
        published_ts="2025-01-01T00:00:00Z",
        status="published",
    )

    # second call should not create duplicates
    upsert_video_publication(
        paths.db_path,
        channel_id="ch1",
        video_id="v1",
        platform="youtube",
        platform_video_id="yt_123",
        run_id=None,
        published_ts="2025-01-01T00:00:00Z",
        status="published",
    )

    con = sqlite3.connect(paths.db_path)
    try:
        rows = con.execute(
            "SELECT channel_id, video_id, platform, platform_video_id, published_ts, status FROM video_publications"
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 1
    (ch, vid, plat, ext_id, ts, st) = rows[0]
    assert ch == "ch1"
    assert vid == "v1"
    assert plat == "youtube"
    assert ext_id == "yt_123"
    assert ts == "2025-01-01T00:00:00Z"
    assert st == "published"
