from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

@dataclass(frozen=True)
class ChannelKpis:
    views: float | None
    watch_time_hours: float | None
    avg_view_duration_sec: float | None
    subs_net: float | None
    estimated_revenue_usd: float | None

@dataclass(frozen=True)
class VideoKpis:
    youtube_video_id: str
    views: float | None
    watch_time_hours: float | None
    avg_view_duration_sec: float | None
    estimated_revenue_usd: float | None

class YouTubeAnalyticsClient:
    """
    YouTube Analytics API v2 client.
    Requires OAuth scope: https://www.googleapis.com/auth/yt-analytics.readonly
    """

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    def __init__(self, client_secrets_path: str, token_path: str) -> None:
        self.client_secrets_path = client_secrets_path
        self.token_path = token_path
        self._yt = None
        self._yta = None

    def _get_credentials(self) -> Credentials:
        creds: Credentials | None = None
        if self.token_path and self.token_path.strip():
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
            except Exception:
                creds = None

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_path, self.SCOPES)
            creds = flow.run_local_server(port=0)

        # persist token
        import os
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        return creds

    def _clients(self):
        if self._yt is None or self._yta is None:
            creds = self._get_credentials()
            self._yt = build("youtube", "v3", credentials=creds)
            self._yta = build("youtubeAnalytics", "v2", credentials=creds)
        return self._yt, self._yta

    def get_channel_id(self) -> str:
        yt, _ = self._clients()
        resp = yt.channels().list(part="id", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            raise RuntimeError("No YouTube channel found for authenticated user.")
        return items[0]["id"]

    def query_channel_kpis(self, *, start: date, end: date) -> ChannelKpis:
        """
        Pull channel-level KPIs for date range [start, end].
        """
        _, yta = self._clients()
        try:
            resp = yta.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views,watchTime,averageViewDuration,subscribersGained,subscribersLost,estimatedRevenue",
                dimensions=None,
                sort=None,
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"YouTube Analytics channel query failed: {e}")

        rows = resp.get("rows", [])
        if not rows:
            return ChannelKpis(None, None, None, None, None)

        # Single aggregate row
        # columns order matches metrics order above
        r = rows[0]
        views = float(r[0]) if r[0] is not None else None
        watch_time_minutes = float(r[1]) if r[1] is not None else None
        avg_view_duration_sec = float(r[2]) if r[2] is not None else None
        subs_gained = float(r[3]) if r[3] is not None else None
        subs_lost = float(r[4]) if r[4] is not None else None
        est_rev = float(r[5]) if r[5] is not None else None

        watch_time_hours = (watch_time_minutes / 60.0) if watch_time_minutes is not None else None
        subs_net = (subs_gained - subs_lost) if (subs_gained is not None and subs_lost is not None) else None

        return ChannelKpis(
            views=views,
            watch_time_hours=watch_time_hours,
            avg_view_duration_sec=avg_view_duration_sec,
            subs_net=subs_net,
            estimated_revenue_usd=est_rev,
        )

    def query_videos_kpis(self, *, start: date, end: date, youtube_video_ids: list[str]) -> list[VideoKpis]:
        """
        Pull per-video KPIs for given IDs and date window.
        Returns list aligned to returned rows (not necessarily input order).
        """
        if not youtube_video_ids:
            return []

        _, yta = self._clients()

        # Analytics API supports filtering by video in one query:
        # filters="video==id1,id2,..." is not supported as a single comma list in all cases.
        # Most reliable: query with dimensions=video and filters=video==<id> per video in loop.
        # Keep it simple and robust.
        results: list[VideoKpis] = []

        for vid in youtube_video_ids:
            try:
                resp = yta.reports().query(
                    ids="channel==MINE",
                    startDate=start.isoformat(),
                    endDate=end.isoformat(),
                    metrics="views,watchTime,averageViewDuration,estimatedRevenue",
                    dimensions=None,
                    filters=f"video=={vid}",
                ).execute()
            except HttpError:
                # If a given video returns no data or access error, record nulls
                results.append(VideoKpis(vid, None, None, None, None))
                continue

            rows = resp.get("rows", [])
            if not rows:
                results.append(VideoKpis(vid, None, None, None, None))
                continue

            r = rows[0]
            views = float(r[0]) if r[0] is not None else None
            watch_time_minutes = float(r[1]) if r[1] is not None else None
            avg_view_duration_sec = float(r[2]) if r[2] is not None else None
            est_rev = float(r[3]) if r[3] is not None else None

            watch_time_hours = (watch_time_minutes / 60.0) if watch_time_minutes is not None else None

            results.append(VideoKpis(vid, views, watch_time_hours, avg_view_duration_sec, est_rev))

        return results
