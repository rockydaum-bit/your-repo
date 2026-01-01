from config import get_config
from utils.paths import EnginePaths
from utils.db import init_db

def main() -> None:
    cfg = get_config()
    paths = EnginePaths(cfg.engine_root)
    paths.ensure_dirs()
    init_db(paths.db_path)
    print(f"Initialized DB at: {paths.db_path}")

if __name__ == "__main__":
    main()
