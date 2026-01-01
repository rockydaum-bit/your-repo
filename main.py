import argparse
import os
from config import get_config
from utils.paths import EnginePaths
from agents.orchestrator import Orchestrator
from agents.optimization_scaling import OptimizationScalingAgent
from agents.analytics_metrics import AnalyticsMetricsAgent


def _paths(cfg):
    return EnginePaths(cfg.engine_root)


def cmd_run(args) -> int:
    cfg = get_config()
    paths = _paths(cfg)
    from utils.health import preflight_check

    preflight_check(cfg, paths, mode="run", channel_id=args.channel)
    import uuid
    from datetime import datetime
    from utils.db_runs import (
        insert_run_start as ra_insert_run_start,
        update_run_end as ra_update_run_end,
    )

    run_id = (
        f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_run_{uuid.uuid4().hex[:8]}"
    )
    ra_insert_run_start(
        cfg=cfg,
        paths=paths,
        run_id=run_id,
        channel_id=args.channel,
        mode="run",
        status="started",
        command="run",
        meta={"channel": args.channel, "max_videos": args.max_videos},
    )
    status = "completed"
    try:
        orch = Orchestrator()
        if hasattr(orch, "run"):
            orch.run(channel_id=args.channel, max_videos=args.max_videos)
        else:
            orch.run_weekly_growth_loop()
    except Exception:
        status = "failed"
        raise
    finally:
        ts_end = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        ra_update_run_end(cfg=cfg, paths=paths, run_id=run_id, status=status)
    return 0


def cmd_measure(args) -> int:
    cfg = get_config()
    paths = _paths(cfg)
    from utils.health import preflight_check

    preflight_check(cfg, paths, mode="measure", channel_id=args.channel)
    import uuid
    from datetime import datetime
    from utils.db_runs import (
        insert_run_start as ra_insert_run_start,
        update_run_end as ra_update_run_end,
    )

    run_id = (
        f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_measure_{uuid.uuid4().hex[:8]}"
    )
    ra_insert_run_start(
        cfg=cfg,
        paths=paths,
        run_id=run_id,
        channel_id=args.channel,
        mode="measure",
        status="started",
        command="measure",
        meta={"channel": args.channel, "window": args.window},
    )
    status = "completed"
    try:
        agent = AnalyticsMetricsAgent(cfg, paths)
        if hasattr(agent, "run_daily_rollup"):
            out = agent.run_daily_rollup(
                channel_id=args.channel, window_days=args.window
            )
            print(out)
        else:
            print("AnalyticsMetricsAgent missing run_daily_rollup")
    except Exception:
        status = "failed"
        raise
    finally:
        ts_end = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        ra_update_run_end(cfg=cfg, paths=paths, run_id=run_id, status=status)
    return 0


def cmd_score(args) -> int:
    cfg = get_config()
    paths = _paths(cfg)
    from utils.health import preflight_check

    preflight_check(cfg, paths, mode="score", channel_id=args.channel)
    import uuid
    from datetime import datetime
    from utils.db_runs import (
        insert_run_start as ra_insert_run_start,
        update_run_end as ra_update_run_end,
    )

    run_id = (
        f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_score_{uuid.uuid4().hex[:8]}"
    )
    ra_insert_run_start(
        cfg=cfg,
        paths=paths,
        run_id=run_id,
        channel_id=args.channel,
        mode="score",
        status="started",
        command="score",
        meta={"channel": args.channel, "window": args.window, "apply": args.apply},
    )
    status = "completed"
    try:
        agent = OptimizationScalingAgent(cfg, paths)
        kwargs = {}
        if hasattr(args, "window"):
            kwargs["lookback_days"] = args.window
        out = agent.score_ab_test(args.channel, dry_run=not args.apply, **kwargs)
        print(out)
    except Exception:
        status = "failed"
        raise
    finally:
        ts_end = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        ra_update_run_end(cfg=cfg, paths=paths, run_id=run_id, status=status)
    return 0


def cmd_status(args) -> int:
    cfg = get_config()
    paths = _paths(cfg)
    from utils.health import preflight_check

    preflight_check(cfg, paths, mode="status", channel_id=args.channel)
    from utils.ops_status import generate_channel_status
    import uuid
    from datetime import datetime
    from utils.db_runs import (
        insert_run_start as ra_insert_run_start,
        update_run_end as ra_update_run_end,
    )

    run_id = (
        f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_status_{uuid.uuid4().hex[:8]}"
    )
    ts_start = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    ra_insert_run_start(
        cfg=cfg,
        paths=paths,
        run_id=run_id,
        channel_id=args.channel,
        mode="status",
        status="started",
        command="status",
        meta={"channel": args.channel},
    )
    status = "completed"
    try:
        out = generate_channel_status(cfg, paths, args.channel)
        print(out)
    except Exception:
        status = "failed"
        raise
    finally:
        ts_end = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        ra_update_run_end(cfg=cfg, paths=paths, run_id=run_id, status=status)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engine")
    # allow passing explicit config file via CLI
    p.add_argument(
        "--config",
        dest="config_path",
        help="Path to engine YAML config (overrides ENGINE_CONFIG_PATH).",
    )
    # subcommands are optional (workers may run without commands)
    sub = p.add_subparsers(dest="cmd", required=False)

    p_run = sub.add_parser("run", help="Run pipeline for a channel")
    p_run.add_argument("--channel", required=True)
    p_run.add_argument("--max-videos", type=int, default=1)
    p_run.set_defaults(fn=cmd_run)

    p_measure = sub.add_parser("measure", help="Ingest/roll up analytics for a channel")
    p_measure.add_argument("--channel", required=True)
    p_measure.add_argument("--window", type=int, default=7)
    p_measure.set_defaults(fn=cmd_measure)

    p_score = sub.add_parser("score", help="Score A/B test (dry-run by default)")
    p_score.add_argument("--channel", required=True)
    p_score.add_argument("--window", type=int, default=7)
    p_score.add_argument("--apply", action="store_true")
    p_score.set_defaults(fn=cmd_score)

    p_status = sub.add_parser(
        "status", help="Write/print ops status snapshot for a channel"
    )
    p_status.add_argument("--channel", required=True)
    p_status.set_defaults(fn=cmd_status)

    return p


import time
import socket
import uuid
from utils.logger import get_logger


def run_worker_loop(cfg, paths) -> None:
    """
    Minimal worker loop: periodically write a worker heartbeat run record.
    """
    log = get_logger("worker", paths.logs_dir)
    db_path = paths.db_path
    worker_id = getattr(cfg, "worker_id", None) or socket.gethostname()

    log.info("Worker starting", extra={"worker_id": worker_id, "db": db_path})

    while True:
        run_id = f"worker-{worker_id}-{uuid.uuid4().hex[:8]}"
        try:
            # store worker_id in channel_id so we can query heartbeats without schema changes
            from utils.db_runs import (
                insert_run_start as ra_insert_run_start,
                update_run_end as ra_update_run_end,
            )

            ra_insert_run_start(
                cfg=cfg,
                paths=paths,
                run_id=run_id,
                channel_id=worker_id,
                mode="worker_heartbeat",
                status="success",
            )
            # Immediately mark success to act as a short-lived heartbeat entry
            ra_update_run_end(cfg=cfg, paths=paths, run_id=run_id, status="success")
            log.info("Worker heartbeat recorded", extra={"run_id": run_id})
        except Exception:
            try:
                update_run_end(db_path, run_id, "error")
            except Exception:
                pass
            log.exception("Worker heartbeat failed")

        time.sleep(60)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # If CLI provided a config path, honor it (and export for downstream get_config calls)
    if getattr(args, "config_path", None):
        os.environ["ENGINE_CONFIG_PATH"] = str(args.config_path)

    cfg = get_config()
    paths = _paths(cfg)
    paths.ensure_dirs()

    # Preflight for both brain and worker
    from utils.health import preflight_check

    preflight_check(cfg, paths)

    if getattr(cfg, "role", "brain") == "worker":
        run_worker_loop(cfg, paths)
        return 0

    # If no command supplied, print help and exit
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 2

    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
