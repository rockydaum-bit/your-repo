from agents.orchestrator import Orchestrator

def main() -> None:
    Orchestrator().run_weekly_growth_loop()

if __name__ == "__main__":
    main()
