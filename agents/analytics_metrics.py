from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, date

from config import EngineConfig
from utils.paths import EnginePaths
from utils.json_validate import save_json, validate_json_against_schema
from utils.db import insert_analytics_daily, list_recent_videos
from utils.youtube_analytics_client import YouTubeAnalyticsClient
from utils.db import sum_costs_month
from utils.json_validate import load_json as load_json_file

@dataclass
class AnalyticsMetricsAgent:
    cfg: EngineConfig
    paths: EnginePaths

    def _ts(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def run_daily_rollup(self, channel_id: str, window_days: int = 7) -> str:
        """
        Writes a rollup JSON and inserts daily rows into SQLite.
        Returns rollup JSON path.
        """
        if not self.cfg.youtube:
            raise RuntimeError("YouTube not configured. Set YOUTUBE_CLIENT_SECRETS_PATH and YOUTUBE_TOKEN_PATH.")

        yta = YouTubeAnalyticsClient(
            client_secrets_path=self.cfg.youtube.client_secrets_path,
            token_path=self.cfg.youtube.token_path,
        )

        end_d = date.today()
        start_d = end_d - timedelta(days=window_days)

        # Channel KPIs
        ch = yta.query_channel_kpis(start=start_d, end=end_d)

        # Costs (monthly to-date), revenue window (estimated)
        month_prefix = datetime.utcnow().strftime("%Y-%m")
        costs_month = sum_costs_month(self.paths.db_path, month_prefix)

        revenue_window = ch.estimated_revenue_usd
        views = ch.views
        rpm = None
        if revenue_window is not None and views and views > 0:
            rpm = (revenue_window / views) * 1000.0

        # Per-video KPIs for recently known videos that have youtube_video_id set
        recent = list_recent_videos(self.paths.db_path, channel_id, limit=50)
        youtube_ids = [r["youtube_video_id"] for r in recent if r.get("youtube_video_id")]
        video_kpis = yta.query_videos_kpis(start=start_d, end=end_d, youtube_video_ids=youtube_ids)

        missing_data: list[str] = []
        if ch.views is None:
            missing_data.append("views")
        if ch.watch_time_hours is None:
            missing_data.append("watch_time_hours")
        if ch.avg_view_duration_sec is None:
            missing_data.append("avg_view_duration_sec")
        if ch.subs_net is None:
            missing_data.append("subs_net")
        # CTR is not always available via Analytics API depending on query; leaving null by design.
        missing_data.append("ctr")  # explicitly unsupported in this rollup implementation

        rollup = {
            "channel_id": channel_id,
            "window_days": window_days,
            "kpis": {
                "views": ch.views,
                "watch_time_hours": ch.watch_time_hours,
                "ctr": None,
                "avg_view_duration_sec": ch.avg_view_duration_sec,
                "rpm": rpm,
                "subs_net": ch.subs_net,
                "costs_usd": costs_month,
                "revenue_usd": revenue_window,
            },
            "anomalies": [],
            "experiments": [],
            "missing_data": missing_data,
        }

        # Insert channel-level row (video_id = None)
        insert_analytics_daily(
            db_path=self.paths.db_path,
            ts=self._ts(),
            channel_id=channel_id,
            video_id=None,
            views=ch.views,
            watch_time_hours=ch.watch_time_hours,
            ctr=None,
            avg_view_duration_sec=ch.avg_view_duration_sec,
            rpm=rpm,
            subs_net=ch.subs_net,
            revenue_usd=revenue_window,
        )

        # Insert per-video rows
        for vk in video_kpis:
            v_rpm = None
            if vk.estimated_revenue_usd is not None and vk.views and vk.views > 0:
                v_rpm = (vk.estimated_revenue_usd / vk.views) * 1000.0

            insert_analytics_daily(
                db_path=self.paths.db_path,
                ts=self._ts(),
                channel_id=channel_id,
                video_id=vk.youtube_video_id,
                views=vk.views,
                watch_time_hours=vk.watch_time_hours,
                ctr=None,
                avg_view_duration_sec=vk.avg_view_duration_sec,
                rpm=v_rpm,
                subs_net=None,  # subs per video not pulled here
                revenue_usd=vk.estimated_revenue_usd,
            )

        # Validate against schema
        schema_path = self.paths.prompt_path("schemas/analytics_rollup.schema.json")
        schema = load_json_file(schema_path)
        validate_json_against_schema(rollup, schema)

        out_dir = os.path.join(self.cfg.engine_root, "assets", "channels", channel_id, "pipeline", "analytics")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"rollup_{window_days}d.json")
        save_json(out_path, rollup)
        return out_path
