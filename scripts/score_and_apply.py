from __future__ import annotations

import argparse
import json

from config import get_config
from utils.paths import EnginePaths
from agents.optimization_scaling import OptimizationScalingAgent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    cfg = get_config()
    paths = EnginePaths(cfg.engine_root)
    agent = OptimizationScalingAgent(cfg, paths)

    out = agent.score_ab_test(args.channel, dry_run=not args.apply)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
