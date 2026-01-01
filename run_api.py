"""run_api.py
Entrypoint to run the FastAPI app with uvicorn. Supports `--config` to
point at a YAML file instead of relying on `ENGINE_CONFIG_PATH`.
"""

import argparse
import os
import uvicorn
from config import get_config, get_config_from_path
from utils.paths import EnginePaths

# Importing `api` module below after config is loaded ensures the module
# picks up the ENGINE_CONFIG_PATH we set from CLI before it reads config.


def main() -> None:
    parser = argparse.ArgumentParser(prog="textautonomous-api")
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to engine YAML config (overrides ENGINE_CONFIG_PATH).",
    )
    args = parser.parse_args()

    if getattr(args, "config_path", None):
        os.environ["ENGINE_CONFIG_PATH"] = str(args.config_path)

    # Load configuration (respecting ENGINE_CONFIG_PATH env var set above)
    cfg = get_config()
    if getattr(cfg, "role", "brain") != "brain":
        raise SystemExit(f"Refusing to start API: role={cfg.role!r} is not 'brain'")

    # Import API module now so it uses the loaded configuration and
    # module-level `cfg`/`paths` inside `api.py` are populated correctly.
    import api as api_module  # type: ignore

    # Ensure engine dirs exist (api.py creates `paths` at module import)
    try:
        api_module.paths.ensure_dirs()
    except Exception:
        # best-effort; continue even if ensure_dirs isn't present
        pass

    # Run uvicorn with the in-memory FastAPI app object to avoid
    # uvicorn's string-based module import (which fails inside PyInstaller EXEs).
    uvicorn.run(
        api_module.app,
        host=getattr(cfg, "server_host", "127.0.0.1"),
        port=getattr(cfg, "server_port", 8000),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
