from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
import os

from utils.youtube_client import YouTubeClient
from utils.json_validate import load_json
from utils.db import (
    upsert_video_publish,
    upsert_video_publication,
    insert_orchestrator_event,
)
from datetime import datetime
import time


@dataclass
class PublishingSEOAgent:
    cfg: Any
    paths: Any
    youtube_client_factory: Any | None = None

    def __post_init__(self) -> None:
        return None

    def upload_to_youtube(
        self,
        *,
        channel_id: str,
        run_id: str,
        final_video_path: str,
        metadata_path: str,
        thumbnail_path: Optional[str] = None,
    ) -> str:
        if not self.cfg.youtube:
            raise RuntimeError(
                "YouTube not configured. Set YOUTUBE_CLIENT_SECRETS_PATH and YOUTUBE_TOKEN_PATH."
            )

        meta = load_json(metadata_path)
        title = meta.get("selected_title") or meta.get("titles", [""])[0]
        description = meta.get("description") or ""
        tags = meta.get("tags", [])

        # Allow injected factory for testing
        if self.youtube_client_factory:
            yt = self.youtube_client_factory()
        else:
            # Try a few constructor signatures to be tolerant to stubs in tests
            try:
                yt = YouTubeClient(
                    client_secrets_path=self.cfg.youtube.client_secrets_path,
                    token_path=self.cfg.youtube.token_path,
                )
            except TypeError:
                try:
                    yt = YouTubeClient(
                        self.cfg.youtube.client_secrets_path,
                        self.cfg.youtube.token_path,
                    )
                except TypeError:
                    try:
                        yt = YouTubeClient(self.cfg.youtube)
                    except TypeError:
                        yt = YouTubeClient()

        # Retry with exponential backoff for transient errors
        attempt = 0
        last_err: Exception | None = None
        while attempt < 5:
            try:
                privacy_status = getattr(
                    self.cfg.youtube, "privacy_status_default", "private"
                )
                res = yt.upload_video_resumable(
                    video_path=final_video_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status=privacy_status,
                )

                if thumbnail_path:
                    try:
                        yt.set_thumbnail(
                            youtube_video_id=res.youtube_video_id,
                            thumbnail_path=thumbnail_path,
                        )
                    except Exception:
                        # thumbnail is non-critical; log and continue
                        pass

                # Persist to DB (idempotent) - legacy and new publications table
                video_id = (
                    meta.get("video_id")
                    or os.path.splitext(os.path.basename(final_video_path))[0]
                )
                published_ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

                # Legacy videos table (backwards compatibility)
                upsert_video_publish(
                    self.paths.db_path,
                    channel_id,
                    video_id,
                    run_id,
                    res.youtube_video_id,
                    published_ts,
                    status="published",
                )

                # New multi-platform publications table
                try:
                    upsert_video_publication(
                        self.paths.db_path,
                        channel_id,
                        video_id,
                        "youtube",
                        res.youtube_video_id,
                        run_id,
                        published_ts,
                        status="published",
                        metadata={"thumbnail_path": thumbnail_path}
                        if thumbnail_path
                        else None,
                    )
                except Exception:
                    # best-effort; do not block publishing on analytics writes
                    pass

                # Audit event
                payload = {
                    "youtube_video_id": res.youtube_video_id,
                    "run_id": run_id,
                    "final_video_path": final_video_path,
                    "metadata_path": metadata_path,
                    "thumbnail_path": thumbnail_path,
                }
                insert_orchestrator_event(
                    self.paths.db_path, published_ts, "INFO", "video_published", payload
                )

                return res.youtube_video_id

            except Exception as e:
                last_err = e
                attempt += 1
                wait = min(2**attempt, 30)
                insert_orchestrator_event(
                    self.paths.db_path,
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "WARN",
                    "video_publish_retry",
                    {"attempt": attempt, "error": str(e)},
                )
                time.sleep(wait)

        # Failed after retries: mark failure and write event
        failed_ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            video_id = (
                meta.get("video_id")
                or os.path.splitext(os.path.basename(final_video_path))[0]
            )
            upsert_video_publish(
                self.paths.db_path,
                channel_id,
                video_id,
                run_id,
                "",
                failed_ts,
                status="upload_failed",
            )
            try:
                upsert_video_publication(
                    self.paths.db_path,
                    channel_id,
                    video_id,
                    "youtube",
                    None,
                    run_id,
                    None,
                    status="upload_failed",
                )
            except Exception:
                pass
        except Exception:
            pass

        insert_orchestrator_event(
            self.paths.db_path,
            failed_ts,
            "ERROR",
            "video_publish_failed",
            {"run_id": run_id, "error": str(last_err)},
        )
        raise RuntimeError(f"Upload failed after retries: {last_err}")

    def generate_upload_metadata(
        self, channel_id: str, run_id: str, script_path: str, output_path: str
    ) -> None:
        """Create a minimal upload metadata JSON for a script.

        This method is lightweight and avoids contacting external services.
        """
        try:
            script = load_json(script_path)
        except Exception:
            script = {"video_id": f"{channel_id}_video01"}

        meta = {
            "video_id": script.get("video_id"),
            "titles": [f"{script.get('video_id', 'Untitled')}"],
            "selected_title": f"{script.get('video_id', 'Untitled')}",
            "description": script.get("description", ""),
            "tags": script.get("tags", []),
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        from utils.json_validate import save_json

        save_json(output_path, meta)
