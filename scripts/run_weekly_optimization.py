from config import get_config
from utils.paths import EnginePaths
from agents.optimization_scaling import OptimizationScalingAgent

def main() -> None:
    cfg = get_config()
    paths = EnginePaths(cfg.engine_root)
    agent = OptimizationScalingAgent(cfg, paths)
    out = agent.run_weekly_optimization(channel_id="channel_001_ai_tools")
    print(out)

if __name__ == "__main__":
    main()
