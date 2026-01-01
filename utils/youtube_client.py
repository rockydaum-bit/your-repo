from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


@dataclass(frozen=True)
class YouTubeUploadResult:
    youtube_video_id: str
    status: str


class YouTubeClient:
    """
    YouTube Data API v3 client for video uploads and thumbnail updates.
    Uses OAuth2 user credentials (recommended for channel uploads).
    """

    # Upload scope
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    def __init__(self, client_secrets_path: str, token_path: str) -> None:
        self.client_secrets_path = client_secrets_path
        self.token_path = token_path
        self._service = None

    def _get_credentials(self) -> Credentials:
        creds: Credentials | None = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_path, self.SCOPES
            )
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        return creds

    def _service_client(self):
        if self._service is None:
            creds = self._get_credentials()
            self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def upload_video_resumable(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category_id: str = "27",  # Education default
        privacy_status: str = "private",
        made_for_kids: bool = False,
        max_retries: int = 10,
    ) -> YouTubeUploadResult:
        yt = self._service_client()

        body: dict[str, Any] = {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }
        if tags:
            body["snippet"]["tags"] = tags

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        request = yt.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        retry = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                if response and "id" in response:
                    return YouTubeUploadResult(
                        youtube_video_id=response["id"], status="uploaded"
                    )

            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504, 429):
                    retry += 1
                    if retry > max_retries:
                        raise
                    sleep = min(2**retry, 60)
                    time.sleep(sleep)
                    continue
                raise

        raise RuntimeError("Upload failed: no response id returned.")

    def set_thumbnail(
        self,
        *,
        youtube_video_id: str,
        thumbnail_path: str,
        max_retries: int = 6,
    ) -> None:
        yt = self._service_client()
        media = MediaFileUpload(thumbnail_path, mimetype="image/png")

        request = yt.thumbnails().set(videoId=youtube_video_id, media_body=media)

        retry = 0
        while True:
            try:
                request.execute()
                return
            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504, 429):
                    retry += 1
                    if retry > max_retries:
                        raise
                    time.sleep(min(2**retry, 60))
                    continue
                raise
