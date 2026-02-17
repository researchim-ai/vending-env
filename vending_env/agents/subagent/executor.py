"""
Саб-агент: выполняет физические операции (план 6) — stock, set_price, collect_cash.
Main-agent вызывает run_sub_agent(instruction) / chat_with_sub_agent(question).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from vending_env.core.state import VendingState
from vending_env.core.sim import Sim


@dataclass
class SubAgentResult:
    """Результат выполнения инструкции саб-агентом."""
    success: bool
    message: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    last_state_snapshot: Optional[str] = None


class SubAgentExecutor:
    """
    Исполняет инструменты sub-agent и отвечает на chat_with_sub_agent.
    run_sub_agent: парсит instruction и вызывает stock_from_storage / set_price / collect_cash.
    """
    def __init__(self, sim: Sim):
        self.sim = sim
        self._last_actions: List[str] = []
        self._last_report: str = ""

    def _apply_stock(self, item_id: str, quantity: int, slot_id: int) -> tuple[bool, str]:
        state = self.sim.state
        slot = state.slot_by_id(slot_id)
        if slot is None:
            return False, f"Slot {slot_id} not found."
        storage = state.storage_inventory.get(item_id, 0)
        if storage < quantity:
            return False, f"Not enough {item_id} in storage (have {storage}, need {quantity}). Check storage later if you just received a delivery."
        if item_id not in state.item_catalog:
            return False, f"Unknown item {item_id}."
        size_class = state.item_catalog[item_id].size_class
        if slot.size_class != size_class:
            return False, f"Slot {slot_id} is for {slot.size_class} items, but {item_id} is {size_class}."
        if slot.item_id is not None and slot.item_id != item_id:
            return False, f"Slot {slot_id} already has {slot.item_id}. Use an empty slot or same item."
        space = slot.capacity - slot.quantity
        put = min(quantity, space)
        if put <= 0:
            return False, f"Slot {slot_id} is full."
        state.storage_inventory[item_id] = state.storage_inventory.get(item_id, 0) - put
        if state.storage_inventory[item_id] <= 0:
            del state.storage_inventory[item_id]
        slot.item_id = item_id
        slot.quantity += put
        if item_id not in state.prices:
            state.prices[item_id] = state.item_catalog[item_id].wholesale_price * 1.5
        return True, f"Stocked {put} x {item_id} into slot {slot_id}."

    def _apply_set_price(self, item_id: str, price: float) -> tuple[bool, str]:
        state = self.sim.state
        if price < 0:
            return False, "Price cannot be negative."
        state.prices[item_id] = round(price, 2)
        return True, f"Set price of {item_id} to ${price:.2f}."

    def _apply_collect_cash(self) -> tuple[bool, str]:
        state = self.sim.state
        amount = state.cash_in_machine
        state.cash_in_machine = 0.0
        state.cash_balance += amount
        return True, f"Collected ${amount:.2f} from the machine."

    def _apply_machine_inventory(self) -> str:
        state = self.sim.state
        lines = ["Slot | Item    | Qty | Price"]
        for s in state.machine_slots:
            item = s.item_id or "-"
            qty = s.quantity
            price = state.prices.get(s.item_id or "", 0)
            lines.append(f"{s.slot_id:4} | {item:8} | {qty:3} | ${price:.2f}")
        return "\n".join(lines)

    def run_tool(self, tool_name: str, args: Dict[str, Any]) -> tuple[bool, str]:
        """Выполнить один инструмент sub-agent. Возвращает (success, message)."""
        if tool_name == "machine_inventory":
            msg = self._apply_machine_inventory()
            self._last_actions.append(f"machine_inventory -> {msg[:100]}")
            return True, msg
        if tool_name == "stock_from_storage":
            item_id = args.get("item_id", "").strip().lower()
            quantity = int(args.get("quantity", 0))
            slot_id = int(args.get("slot_id", 0))
            ok, msg = self._apply_stock(item_id, quantity, slot_id)
            self._last_actions.append(f"stock_from_storage({item_id}, {quantity}, {slot_id}) -> {msg}")
            return ok, msg
        if tool_name == "set_price":
            item_id = args.get("item_id", "").strip().lower()
            price = float(args.get("price", 0))
            ok, msg = self._apply_set_price(item_id, price)
            self._last_actions.append(f"set_price({item_id}, {price}) -> {msg}")
            return ok, msg
        if tool_name == "collect_cash":
            ok, msg = self._apply_collect_cash()
            self._last_actions.append(f"collect_cash -> {msg}")
            return ok, msg
        return False, f"Unknown sub-agent tool: {tool_name}"

    def run_instruction(self, instruction: str) -> SubAgentResult:
        """
        Парсит instruction и выполняет одну или несколько операций (rule-based).
        Примеры: "restock cola 10 in slot 0", "set price of cola to 2", "collect cash".
        """
        self._last_actions = []
        instruction = instruction.strip().lower()
        # collect cash
        if "collect" in instruction and "cash" in instruction:
            ok, msg = self.run_tool("collect_cash", {})
            return SubAgentResult(success=ok, message=msg, tool_calls=[{"name": "collect_cash", "args": {}}])
        # set price ... to X
        price_match = re.search(r"set\s+price\s+(?:of\s+)?(\w+)\s+to\s+([\d.]+)", instruction)
        if price_match:
            item_id = price_match.group(1)
            price = float(price_match.group(2))
            ok, msg = self.run_tool("set_price", {"item_id": item_id, "price": price})
            return SubAgentResult(success=ok, message=msg, tool_calls=[{"name": "set_price", "args": {"item_id": item_id, "price": price}}])
        # restock / stock X N in slot K (или slot K)
        restock_match = re.search(r"(?:restock|stock)\s+(\w+)\s+(\d+)\s+(?:in\s+)?slot\s+(\d+)", instruction)
        if restock_match:
            item_id = restock_match.group(1)
            qty = int(restock_match.group(2))
            slot_id = int(restock_match.group(3))
            ok, msg = self.run_tool("stock_from_storage", {"item_id": item_id, "quantity": qty, "slot_id": slot_id})
            return SubAgentResult(success=ok, message=msg, tool_calls=[{"name": "stock_from_storage", "args": {"item_id": item_id, "quantity": qty, "slot_id": slot_id}}])
        # "get inventory" / "machine inventory"
        if "inventory" in instruction or "what is in" in instruction:
            msg = self._apply_machine_inventory()
            return SubAgentResult(success=True, message=msg, tool_calls=[{"name": "machine_inventory", "args": {}}])
        return SubAgentResult(
            success=False,
            message="I didn't understand. Try: 'restock cola 10 in slot 0', 'set price of cola to 2', 'collect cash', or 'show machine inventory'.",
            tool_calls=[],
        )

    def chat(self, question: str) -> str:
        """Ответ на chat_with_sub_agent: что сделал, текущий инвентарь и т.д."""
        q = question.strip().lower()
        if "inventory" in q or "what" in q and "slot" in q:
            return self._apply_machine_inventory()
        if "did" in q or "what did" in q or "last" in q:
            if self._last_actions:
                return "Last actions:\n" + "\n".join(self._last_actions[-5:])
            return "No actions performed yet."
        # default: last actions + current inventory
        parts = []
        if self._last_actions:
            parts.append("Last actions:\n" + "\n".join(self._last_actions[-3:]))
        parts.append("Current machine:\n" + self._apply_machine_inventory())
        return "\n\n".join(parts)
