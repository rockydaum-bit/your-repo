from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import json
import os

from utils.json_validate import load_json, save_json


@dataclass(frozen=True)
class OrchestratorState:
    """
    Stores active prompt variants per channel/task and A/B test allocation.
    """

    version: int
    active_variants: dict[
        str, dict[str, str]
    ]  # channel_id -> task_name -> prompt_rel_path
    ab_tests: dict[str, Any]  # channel_id -> test metadata


DEFAULT_STATE: OrchestratorState = OrchestratorState(
    version=1, active_variants={}, ab_tests={}
)


def load_state(state_path: str) -> OrchestratorState:
    if not os.path.exists(state_path):
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        save_state(state_path, DEFAULT_STATE)
        return DEFAULT_STATE

    with open(state_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return OrchestratorState(
        version=int(raw.get("version", 1)),
        active_variants=dict(raw.get("active_variants", {})),
        ab_tests=dict(raw.get("ab_tests", {})),
    )


def save_state(state_path: str, state: OrchestratorState) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": state.version,
                "active_variants": state.active_variants,
                "ab_tests": state.ab_tests,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def append_promotion_history(history_path: str, entry: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    if os.path.exists(history_path):
        raw = load_json(history_path)
        data: list[Dict[str, Any]] = raw if isinstance(raw, list) else []
    else:
        data = []

    data.append(entry)
    save_json(history_path, data)
