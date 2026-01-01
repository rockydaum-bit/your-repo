# Configuration Guide

This document describes the engine configuration schema, precedence rules, and recommended operator practices.

## Where config comes from (precedence)
- `ENGINE_CONFIG_PATH` (environment) — if set, this YAML file is used.
- `config/engine.yaml` (repository default) — used when `ENGINE_CONFIG_PATH` is not set.
- Environment variable overrides (secrets and quick overrides):
  - `ENGINE_ROLE` or legacy `ROLE` — runtime role (brain|worker)
  - `WORKER_ID` — explicit worker identifier
  - `OPENAI_API_KEY` — OpenAI API key
  - `YOUTUBE_CLIENT_SECRETS_PATH`, `YOUTUBE_TOKEN_PATH` — YouTube OAuth files

Env vars override values defined in the YAML file for secret/configuration values.

## Top-level YAML structure (recommended)

version: "0.3.0"
role: "brain"    # or "worker"
mode: "local"

engine_root: "D:/textautonomous_media_engine"

db:
  driver: "sqlite"          # future: "postgres"
  path: "data/revenue.db"   # or url for postgres

storage:
  mode: "local"             # future: "nas"
  local_root: "D:/textautonomous_media_engine"
  nas_root: "\\NAS01\\textauto\\engine"

worker:
  id: "worker-01"
  queue_poll_interval_seconds: 30

platforms:
  youtube:
    enabled: true
  tiktok:
    enabled: false
  instagram:
    enabled: false

ai:
  provider: "openai"
  model: "gpt-4o"

features:
  enable_auto_promote: false

## Important fields
- `role`: Controls behavior. Use `brain` for API/UI/coordination; `worker` for background processing.
- `worker.id`: If present, used as `worker_id`. Otherwise environment `WORKER_ID` or hostname is used.
- `engine_root`: Base path for `data`, `logs`, `assets`, and `ui_dist`.
- `db.path` / `db.url`: Location of the DB. For sqlite use a filesystem path under `engine_root`.
- `storage.mode`: Switch between `local` and `nas`. `EnginePaths` resolves directories accordingly.

## Secrets & Credentials
- Prefer environment variables for sensitive values in production (e.g. `OPENAI_API_KEY`).
- For YouTube OAuth, set either env vars `YOUTUBE_CLIENT_SECRETS_PATH` and `YOUTUBE_TOKEN_PATH`, or set them in YAML under `youtube.client_secrets_path` / `youtube.token_path`.

## Example: brain vs worker
- `config/engine-brain.yaml` should contain publish credentials (OpenAI, YouTube) and `role: brain`.
- `config/engine-worker.yaml` may omit publish credentials and only include DB/storage and `role: worker` plus `worker.id`.

## Operator tips
- To start the brain:

```powershell
$env:ENGINE_CONFIG_PATH = "D:\textautonomous_media_engine\config\engine-brain.yaml"
python run_api.py
```

- To start a worker:

```powershell
$env:ENGINE_CONFIG_PATH = "D:\textautonomous_media_engine\config\engine-worker.yaml"
python main.py
```

- To move to NAS:
  - Set `storage.mode: nas` and `storage.nas_root` in YAML, then restart nodes.

## Precedence summary
1. `ENGINE_CONFIG_PATH` file
2. YAML values
3. Environment variables override YAML for secrets and runtime flags as described above

## Backwards-compatibility
- `ENGINE_ROLE` will be honored before legacy `ROLE` env.
- `worker.id` in YAML is supported in addition to `worker_id`.


