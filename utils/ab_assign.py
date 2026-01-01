from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ABAssignment:
    arm: str  # "base" or "variant"
    reason: str


def stable_bucket(key: str) -> float:
    """
    Deterministic float in [0,1) based on SHA256.
    """
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    # use first 15 hex chars -> int -> normalize
    n = int(h[:15], 16)
    return (n % 10_000_000) / 10_000_000.0


def choose_arm(
    *,
    channel_id: str,
    video_id: str,
    ab_test: dict[str, Any] | None,
    already_assigned: str | None = None,
) -> ABAssignment:
    """
    Determines the A/B arm for a video_id.
    - If already assigned, returns that.
    - If no test or disabled, returns base.
    - Uses allocation weights in ab_test["allocation"], expects keys "base","variant".
    """
    if already_assigned in ("base", "variant"):
        return ABAssignment(arm=already_assigned, reason="existing_assignment")

    if not ab_test or not ab_test.get("enabled", False):
        return ABAssignment(arm="base", reason="ab_disabled_or_missing")

    alloc = ab_test.get("allocation", {"base": 0.5, "variant": 0.5})
    base_w = float(alloc.get("base", 0.5))
    var_w = float(alloc.get("variant", 0.5))
    total = base_w + var_w
    if total <= 0:
        return ABAssignment(arm="base", reason="bad_allocation")

    base_p = base_w / total

    b = stable_bucket(f"{channel_id}:{video_id}")
    arm = "base" if b < base_p else "variant"
    return ABAssignment(arm=arm, reason=f"bucket={b:.6f}, base_p={base_p:.3f}")
