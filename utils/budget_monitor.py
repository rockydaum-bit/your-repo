from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from utils.db import sum_costs_month

@dataclass(frozen=True)
class BudgetStatus:
    month_total: float
    allowed: float
    stop_at: float
    should_stop: bool

def month_prefix_now() -> str:
    # UTC-ish prefix; good enough for cost gating
    return datetime.utcnow().strftime("%Y-%m")

def check_budget(db_path: str, monthly_cap_usd: float, stop_at_pct: float) -> BudgetStatus:
    prefix = month_prefix_now()
    total = sum_costs_month(db_path, prefix)
    stop_at = monthly_cap_usd * stop_at_pct
    return BudgetStatus(
        month_total=total,
        allowed=monthly_cap_usd,
        stop_at=stop_at,
        should_stop=(total >= stop_at),
    )
