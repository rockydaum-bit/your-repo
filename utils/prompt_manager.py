from __future__ import annotations

import os
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PromptPatch:
    target_rel_path: str  # e.g. "tasks/script_generation.txt"
    operations: list[dict[str, Any]]  # bounded operations: insert/replace/append


@dataclass(frozen=True)
class VariantResult:
    variant_root: str
    files_written: list[str]
    manifest_path: str


class PromptManager:
    """
    Creates variant prompt files by copying base prompts + applying bounded operations.
    Never overwrites base prompts.
    """

    def __init__(self, engine_root: str) -> None:
        self.engine_root = engine_root
        self.prompts_root = os.path.join(engine_root, "prompts")

    def read_prompt(self, rel_path: str) -> str:
        path = os.path.join(self.prompts_root, rel_path)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def write_prompt(self, rel_path: str, content: str) -> str:
        path = os.path.join(self.prompts_root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def apply_operations(self, base: str, operations: list[dict[str, Any]]) -> str:
        """
        Supported operations (safe subset):
        - {"op":"append", "text":"..."}
        - {"op":"insert_after", "marker":"...", "text":"..."}  (first match only)
        - {"op":"replace", "old":"...", "new":"..."}           (first match only)
        """
        out = base
        for op in operations:
            t = op.get("op")
            if t == "append":
                out = out.rstrip() + "\n\n" + str(op["text"]).rstrip() + "\n"
            elif t == "insert_after":
                marker = str(op["marker"])
                text = str(op["text"])
                idx = out.find(marker)
                if idx >= 0:
                    insert_at = idx + len(marker)
                    out = out[:insert_at] + "\n" + text + "\n" + out[insert_at:]
            elif t == "replace":
                old = str(op["old"])
                new = str(op["new"])
                idx = out.find(old)
                if idx >= 0:
                    out = out.replace(old, new, 1)
            else:
                # ignore unknown ops to stay safe
                continue
        return out

    def create_variant(
        self,
        *,
        channel_id: str,
        variant_name: str,
        patches: list[PromptPatch],
        notes: str,
        created_by: str,
    ) -> VariantResult:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        variant_root_rel = os.path.join("variants", channel_id, f"{ts}_{variant_name}")
        variant_root_abs = os.path.join(self.prompts_root, variant_root_rel)

        os.makedirs(variant_root_abs, exist_ok=True)

        files_written: list[str] = []
        mapping: dict[str, str] = {}  # task_rel_path -> variant_rel_path

        for p in patches:
            base_rel = p.target_rel_path
            base_txt = self.read_prompt(base_rel)

            new_txt = self.apply_operations(base_txt, p.operations)

            # Write into variant folder while preserving basename
            base_name = os.path.basename(base_rel)
            out_rel = os.path.join(variant_root_rel, base_name)
            out_abs = os.path.join(self.prompts_root, out_rel)
            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
            with open(out_abs, "w", encoding="utf-8") as f:
                f.write(new_txt)

            files_written.append(out_rel)
            mapping[base_rel] = out_rel

        manifest = {
            "channel_id": channel_id,
            "variant_name": variant_name,
            "created_utc": ts,
            "created_by": created_by,
            "notes": notes,
            "mapping": mapping,
            "files_written": files_written,
        }

        manifest_rel = os.path.join(variant_root_rel, "manifest.json")
        manifest_abs = os.path.join(self.prompts_root, manifest_rel)
        with open(manifest_abs, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return VariantResult(
            variant_root=variant_root_rel,
            files_written=files_written,
            manifest_path=manifest_rel,
        )

    def resolve_task_prompt_for_video(
        self,
        *,
        base_task_rel_path: str,
        channel_id: str,
        video_id: str,
        state: dict,
        db_path: str,
        ts: str,
    ) -> tuple[str, str]:
        """
        Returns (prompt_text, chosen_rel_path).
        Implements true per-video A/B:
          - base arm -> base_task_rel_path
          - variant arm -> mapped variant prompt if exists; else base
        Persists assignment in DB for auditability.
        """
        from utils.ab_assign import choose_arm
        from utils.db import get_prompt_assignment, upsert_prompt_assignment

        ab_test = (state.get("ab_tests", {}) or {}).get(channel_id)
        already = get_prompt_assignment(db_path, channel_id, video_id)

        assignment = choose_arm(
            channel_id=channel_id,
            video_id=video_id,
            ab_test=ab_test,
            already_assigned=already,
        )

        variant_manifest_rel = None
        if ab_test and ab_test.get("variant_manifest_rel"):
            variant_manifest_rel = ab_test["variant_manifest_rel"]

        # Save assignment for auditability
        upsert_prompt_assignment(
            db_path=db_path,
            ts=ts,
            channel_id=channel_id,
            video_id=video_id,
            arm=assignment.arm,
            variant_manifest_rel=variant_manifest_rel,
            notes=assignment.reason,
        )

        chosen = base_task_rel_path

        # Only attempt variant if the arm is variant and a mapping exists
        if assignment.arm == "variant":
            mapping = (state.get("active_variants", {}) or {}).get(channel_id, {})
            # mapping uses base_rel_path -> variant_rel_path
            if base_task_rel_path in mapping:
                chosen = mapping[base_task_rel_path]

        txt = self.read_prompt(chosen)
        return txt, chosen
