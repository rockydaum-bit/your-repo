**Overview**
- Purpose: how to build, package, install and run the TextAutonomous node (brain or worker).

**Pre-flight (local dev)**
- Activate venv and run tests:

```powershell
cd D:\textautonomous_media_engine
& .\.venv\Scripts\Activate.ps1
python -m pytest -q
```

- Build frontend (produces `ui/dist`):

```powershell
cd ui
npm run build
cd ..
```

**Build a single EXE (brain+worker binary)**
- Use the packaging wrapper which builds the UI, installs PyInstaller into the venv if needed, and runs the repeatable spec:

```powershell
cd D:\textautonomous_media_engine
& .\.venv\Scripts\Activate.ps1
.\scripts\build_exe.ps1
```

- Output: `dist\\textautonomous_node.exe` (single-file EXE produced by PyInstaller).  If you need debugging, the spec `textautonomous_node.spec` is at the repo root.

**Simple smoke test (brain mode)**
1. Run the EXE (keep the process running):

```powershell
cd D:\textautonomous_media_engine\dist
.\textautonomous_node.exe --config "C:\textauto\engine-brain.yaml"
```

2. In another shell verify endpoints (non-interactive):

```powershell
Invoke-WebRequest 'http://localhost:8000/api/version' -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest 'http://localhost:8000/api/channels' -UseBasicParsing | Select-Object -ExpandProperty Content
# Then open http://localhost:8000/ in a browser
```

Expected: API responds; UI loads; header shows version/role/worker_id; channels and panels render.

**Quick worker simulation (same EXE)**
- On a worker machine (or same machine after stopping the brain), set env and run:

```powershell
cd D:\textautonomous_media_engine\dist
.\textautonomous_node.exe --config "C:\textauto\engine-worker.yaml"
```

Note: Alternatively you can set `ENGINE_CONFIG_PATH` and omit `--config`. If both are set, `--config` wins.

- When the brain is running against the same DB, `/api/workers` should list the worker after a short delay.

**Install helper (recommended for new nodes)**
- Use `scripts\\install_node.ps1` to copy EXE + configs and create a run script.

Example: install a brain locally

```powershell
cd D:\textautonomous_media_engine
& .\.venv\Scripts\Activate.ps1
.\scripts\install_node.ps1 -Role brain -InstallRoot "C:\\TextAutonomousBrain"
powershell -ExecutionPolicy Bypass -File "C:\\TextAutonomousBrain\\run_node_brain.ps1"
```

Example: install a worker

```powershell
.\scripts\install_node.ps1 -Role worker -InstallRoot "C:\\TextAutonomousWorker" -NodeName "worker-01"
powershell -ExecutionPolicy Bypass -File "C:\\TextAutonomousWorker\\run_node_worker.ps1"
```

**Config files**
- Templates shipped: `config\\engine-brain.yaml` and `config\\engine-worker.yaml`.  The node resolves config in this order: environment variables (e.g., `ENGINE_CONFIG_PATH`, `ENGINE_ROLE`, `WORKER_ID`) -> `config/engine.yaml` -> sensible defaults.

**Configuration**

For detailed configuration (db/storage/role/worker_id/platforms), see `docs/CONFIG.md`.

Starter configs included in this repo:

- `config/engine-brain.yaml` – default brain profile (recommend copying to a system path and updating credentials)
- `config/engine-worker.yaml` – default worker profile (minimal credentials required)
- `config/yt_client_secrets.example.json` / `config/yt_token.example.json` – templates for YouTube OAuth; copy to the paths referenced in your YAML or set the `YOUTUBE_CLIENT_SECRETS_PATH` / `YOUTUBE_TOKEN_PATH` env vars.

**Scaling notes (no code changes required)**
- Multi-machine: copy the same EXE to multiple worker machines and set `ENGINE_ROLE=worker` + `WORKER_ID` or use the role-specific YAML.
- NAS: set `storage.mode: nas` and `storage.nas_root: "\\\\nas-box\\\\media"` in YAML. Path resolution is centralized in `utils/paths.py`.
- Central DB: switch `db.driver` to `postgres` and set `db.dsn` in YAML; `utils/db.py` centralizes DB access for a clean adapter swap.
- New platforms / AI providers: config-driven; add client + agent code when ready and toggle via YAML feature flags.

**Troubleshooting**
- If PyInstaller fails with a missing-module error, run the wrapper again and capture the PyInstaller output; add the missing name to `hiddenimports` in `textautonomous_node.spec`.
- If UI build fails, run `cd ui; npm run build` and fix TypeScript/JSX errors. A temporary `AppClean` shim exists to help packaging if the full UI is broken.
- If the EXE starts but API refuses to bind: confirm `engine.role` is `brain` in the loaded config (`ENGINE_CONFIG_PATH`), or verify `ENGINE_ROLE` env var.

**Next steps**
- Run the one clean smoke test above. If green, package + install on additional nodes with `scripts\\install_node.ps1`.
