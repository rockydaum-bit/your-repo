import os
import json
from utils.prompt_manager import PromptManager, PromptPatch


def test_apply_operations_and_create_variant(tmp_path):
    engine_root = str(tmp_path)
    prompts_dir = os.path.join(engine_root, "prompts")
    os.makedirs(os.path.join(prompts_dir, "tasks"), exist_ok=True)

    base_rel = "tasks/script_generation.txt"
    base_path = os.path.join(prompts_dir, base_rel)
    os.makedirs(os.path.dirname(base_path), exist_ok=True)
    with open(base_path, "w", encoding="utf-8") as f:
        f.write("line1\nmarker_line\nline3")

    pm = PromptManager(engine_root)

    # apply append
    out = pm.apply_operations("hello", [{"op": "append", "text": "world"}])
    assert out.strip().endswith("world")

    # insert_after
    base = "a\nMARKER\nb"
    out2 = pm.apply_operations(base, [{"op": "insert_after", "marker": "MARKER", "text": "INSERTED"}])
    assert "INSERTED" in out2

    # replace
    out3 = pm.apply_operations("foo old bar", [{"op": "replace", "old": "old", "new": "NEW"}])
    assert "NEW" in out3

    # create variant
    patches = [PromptPatch(target_rel_path=base_rel, operations=[{"op": "append", "text": "\n// variant"}])]
    variant = pm.create_variant(channel_id="ch1", variant_name="v1", patches=patches, notes="n", created_by="t")

    manifest_path = os.path.join(prompts_dir, variant.manifest_path)
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
    assert "mapping" in m
