from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from config import get_config
from utils.paths import EnginePaths
from utils.db import insert_run_start, update_run_end, insert_alert


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    cfg = get_config()
    paths = EnginePaths(cfg.engine_root)
    db = paths.db_path

    channel_id = 'channel_001_ai_tools'

    # create two runs
    run1 = str(uuid4())
    insert_run_start(db, run1, channel_id, 'manual')
    update_run_end(db, run1, 'success', None)

    run2 = str(uuid4())
    insert_run_start(db, run2, channel_id, 'cron')
    update_run_end(db, run2, 'failed', 'Example error: upload failed')

    # add a couple of alerts
    insert_alert(
        db,
        ts=iso_now(),
        severity='warning',
        code='upload_slow',
        channel_id=channel_id,
        run_id=run2,
        message='Upload took longer than expected',
        meta_json=None,
    )

    insert_alert(
        db,
        ts=iso_now(),
        severity='error',
        code='publish_failed',
        channel_id=channel_id,
        run_id=run2,
        message='Publish step failed with exit code 1',
        meta_json=None,
    )

    print('Seeded sample runs and alerts')


if __name__ == '__main__':
    main()
