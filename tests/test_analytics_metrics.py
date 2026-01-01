import json
import os
from datetime import date

from config import EngineConfig, YouTubePolicy
from utils.paths import EnginePaths
from utils.db import init_db, connect

from agents.analytics_metrics import AnalyticsMetricsAgent


class FakeChannelKpis:
    def __init__(self, views=None, watch_time_hours=None, avg_view_duration_sec=None, subs_net=None, estimated_revenue_usd=None):
        self.views = views
        self.watch_time_hours = watch_time_hours
        self.avg_view_duration_sec = avg_view_duration_sec
        self.subs_net = subs_net
        self.estimated_revenue_usd = estimated_revenue_usd


class FakeVideoKpis:
    def __init__(self, youtube_video_id, views=None, watch_time_hours=None, avg_view_duration_sec=None, estimated_revenue_usd=None):
        self.youtube_video_id = youtube_video_id
        self.views = views
        self.watch_time_hours = watch_time_hours
        self.avg_view_duration_sec = avg_view_duration_sec
        self.estimated_revenue_usd = estimated_revenue_usd


class FakeYTA:
    def __init__(self, *args, **kwargs):
        pass

    def query_channel_kpis(self, *, start: date, end: date):
        return FakeChannelKpis(views=1000, watch_time_hours=50.0, avg_view_duration_sec=180.0, subs_net=10, estimated_revenue_usd=120.0)

    def query_videos_kpis(self, *, start: date, end: date, youtube_video_ids: list):
        return [FakeVideoKpis(vid, views=100, watch_time_hours=5.0, avg_view_duration_sec=120.0, estimated_revenue_usd=12.0) for vid in youtube_video_ids]


def test_run_daily_rollup_creates_rollup_and_inserts_db(tmp_path, monkeypatch):
    engine_root = str(tmp_path)
    # Provide a dummy YouTubePolicy so the agent doesn't raise on missing config
    yt = YouTubePolicy(client_secrets_path="/dev/null", token_path="/dev/null")
    cfg = EngineConfig(engine_root=engine_root, openai_api_key="test", openai_model="gpt-4o", youtube=yt)
    paths = EnginePaths(cfg.engine_root)
    paths.ensure_dirs()

    # Create minimal analytics schema
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "schemas").mkdir(parents=True, exist_ok=True)
    analytics_schema = {
        "type": "object",
        "required": ["channel_id", "window_days", "kpis", "anomalies", "experiments", "missing_data"],
        "properties": {
            "channel_id": {"type": "string"},
            "window_days": {"type": "integer"},
            "kpis": {"type": "object"},
            "anomalies": {"type": "array"},
            "experiments": {"type": "array"},
            "missing_data": {"type": "array"}
        }
    }
    (prompts_dir / "schemas" / "analytics_rollup.schema.json").write_text(json.dumps(analytics_schema))

    # Initialize DB
    init_db(paths.db_path)

    # Ensure videos table has one entry with youtube_video_id so per-video query runs
    with connect(paths.db_path) as con:
        con.execute("INSERT INTO videos (channel_id, video_id, run_id, topic, status, youtube_video_id) VALUES (?, ?, ?, ?, ?, ?)",
                    ("channel_001_ai_tools", "vid1", "run1", "topic", "published", "yt_vid_1"))

    # Monkeypatch YouTubeAnalyticsClient used by the AnalyticsMetricsAgent to our fake
    import agents.analytics_metrics as amod
    monkeypatch.setattr(amod, "YouTubeAnalyticsClient", FakeYTA)

    agent = AnalyticsMetricsAgent(cfg, paths)
    out_path = agent.run_daily_rollup(channel_id="channel_001_ai_tools", window_days=7)

    assert out_path and (tmp_path / out_path).exists() or os.path.exists(out_path)

    # Validate DB inserted rows in analytics_daily
    with connect(paths.db_path) as con:
        rows = con.execute("SELECT COUNT(*) AS c FROM analytics_daily").fetchone()
        assert rows and rows["c"] >= 1
