"""Снимки состояния для логирования и генерации данных."""
from __future__ import annotations

from typing import Any, Dict

from vending_env.tools.tool_runtime import ToolRuntime


def state_snapshot(runtime: ToolRuntime) -> Dict[str, Any]:
    """Компактный снимок состояния для наблюдения (RL/LLM)."""
    s = runtime.state
    return {
        "day": s.current_day,
        "cash_balance": round(s.cash_balance, 2),
        "cash_in_machine": round(s.cash_in_machine, 2),
        "net_worth": round(s.net_worth(), 2),
        "storage": dict(s.storage_inventory),
        "open_orders": [
            {"order_id": o.order_id, "eta_day": o.eta_day, "items": o.items}
            for o in s.open_orders
        ],
        "machine_slots": [
            {"slot_id": sl.slot_id, "item_id": sl.item_id, "qty": sl.quantity}
            for sl in s.machine_slots
        ],
        "prices": dict(s.prices),
        "unread_emails": s.unread_emails_count(),
    }
