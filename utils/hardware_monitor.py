from __future__ import annotations

import shutil
import psutil
from dataclasses import dataclass

@dataclass(frozen=True)
class HardwareStatus:
    cpu_pct: float
    disk_free_pct: float
    should_pause: bool
    reasons: list[str]

def check_hardware(engine_root: str, cpu_pause_pct: float, disk_free_pause_pct: float) -> HardwareStatus:
    cpu = psutil.cpu_percent(interval=1.0)
    total, used, free = shutil.disk_usage(engine_root)
    disk_free_pct = (free / total) * 100.0

    reasons: list[str] = []
    if cpu >= cpu_pause_pct:
        reasons.append(f"CPU {cpu:.1f}% >= {cpu_pause_pct:.1f}%")
    if disk_free_pct <= disk_free_pause_pct:
        reasons.append(f"Disk free {disk_free_pct:.1f}% <= {disk_free_pause_pct:.1f}%")

    return HardwareStatus(
        cpu_pct=cpu,
        disk_free_pct=disk_free_pct,
        should_pause=(len(reasons) > 0),
        reasons=reasons,
    )
