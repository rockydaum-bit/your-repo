from config import get_config
from utils.paths import EnginePaths
from agents.analytics_metrics import AnalyticsMetricsAgent

def main() -> None:
    cfg = get_config()
    paths = EnginePaths(cfg.engine_root)
    agent = AnalyticsMetricsAgent(cfg, paths)

    channel_id = "channel_001_ai_tools"
    p7 = agent.run_daily_rollup(channel_id=channel_id, window_days=7)
    p28 = agent.run_daily_rollup(channel_id=channel_id, window_days=28)

    print("Wrote rollups:")
    print(p7)
    print(p28)

if __name__ == "__main__":
    main()
