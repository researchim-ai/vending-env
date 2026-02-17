"""
Метрики по статье 2.4: net worth, units sold, tool use, days until stagnation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EpisodeMetrics:
    net_worth_final: float = 0.0
    net_worth_min: float = 0.0
    units_sold: int = 0
    days_simulated: int = 0
    messages: int = 0
    tool_use_count: Dict[str, int] = field(default_factory=dict)
    terminated_reason: Optional[str] = None
    days_until_sales_stopped: Optional[int] = None  # если считаем stagnation


def compute_metrics(
    net_worth_final: float,
    net_worth_min: float,
    units_sold: int,
    days_simulated: int,
    messages: int,
    tool_use_count: Dict[str, int],
    terminated_reason: Optional[str] = None,
    days_until_sales_stopped: Optional[int] = None,
) -> EpisodeMetrics:
    return EpisodeMetrics(
        net_worth_final=net_worth_final,
        net_worth_min=net_worth_min,
        units_sold=units_sold,
        days_simulated=days_simulated,
        messages=messages,
        tool_use_count=dict(tool_use_count),
        terminated_reason=terminated_reason,
        days_until_sales_stopped=days_until_sales_stopped,
    )
