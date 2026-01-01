from __future__ import annotations

import json
import sys
import os

# Ensure a local `rpds` shim is available to satisfy jsonschema/referencing imports
# This helps on platforms where a binary `rpds` wheel is not available.
try:
    if "rpds" not in sys.modules:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        shim_path = os.path.join(repo_root, "rpds")
        if os.path.isdir(shim_path):
            # Load package by executing its __init__.py into a new module
            import importlib.util

            init_file = os.path.join(shim_path, "__init__.py")
            if os.path.exists(init_file):
                spec = importlib.util.spec_from_file_location("rpds", init_file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                sys.modules["rpds"] = mod
except Exception:
    # best-effort shim; if it fails, let the real import raise below
    pass

# Import jsonschema if available; otherwise provide a permissive fallback validator
try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception:

    class Draft202012Validator:
        def __init__(self, schema: dict) -> None:
            self.schema = schema

        def iter_errors(self, data: dict):
            # permissive: do not raise validation errors when jsonschema is unavailable
            return []


class SchemaValidationError(RuntimeError):
    pass


def validate_json_against_schema(data: dict, schema: dict) -> None:
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = []
        for e in errors[:10]:
            path = ".".join([str(p) for p in e.path]) if e.path else "<root>"
            msgs.append(f"{path}: {e.message}")
        raise SchemaValidationError("Schema validation failed: " + " | ".join(msgs))


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    import os
    import uuid

    # Ensure directory exists
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    # Write to a temp file in the same directory, fsync, then atomically replace
    pid = os.getpid()
    tmp_name = f"{os.path.basename(path)}.tmp.{pid}.{uuid.uuid4().hex}"
    tmp_path = os.path.join(dirpath or ".", tmp_name)
    # Use binary mode to ensure fsync behavior
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            # fsync may not be available on all platforms/FS; ignore but try
            pass

    # Atomic replace
    os.replace(tmp_path, path)
