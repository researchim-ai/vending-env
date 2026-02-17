"""
Поставщики: прайс-листы, lead time, валидация заказов (план 5).
Детерминированная симуляция для воспроизводимости RL.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .state import Order, OrderStatus, Email, ItemInfo, VendingState


@dataclass
class Supplier:
    """Поставщик: id, имя, каталог (item_id -> цена за единицу), мин. заказ, lead_time дней."""
    supplier_id: str
    name: str
    catalog: Dict[str, float]  # item_id -> unit price
    min_order_value: float = 50.0
    lead_time_days: Tuple[int, int] = (2, 5)  # (min, max) дней до доставки
    size_class_map: Optional[Dict[str, str]] = None  # item_id -> "small"|"large"

    def unit_price(self, item_id: str) -> Optional[float]:
        return self.catalog.get(item_id)

    def size_class(self, item_id: str) -> str:
        if self.size_class_map and item_id in self.size_class_map:
            return self.size_class_map[item_id]
        return "small"

    def lead_time(self, rng: random.Random) -> int:
        return rng.randint(self.lead_time_days[0], self.lead_time_days[1])


@dataclass
class OrderResult:
    """Результат попытки оформить заказ по письму."""
    success: bool
    order: Optional[Order] = None
    error_message: Optional[str] = None
    reply_subject: str = ""
    reply_body: str = ""


class SupplierRegistry:
    """Реестр поставщиков + разбор писем и генерация ответов (шаблонные, без LLM)."""
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._suppliers: Dict[str, Supplier] = {}
        self._product_db: Dict[str, ItemInfo] = {}

    def register_supplier(self, s: Supplier) -> None:
        self._suppliers[s.supplier_id] = s
        for item_id, price in s.catalog.items():
            if item_id not in self._product_db:
                self._product_db[item_id] = ItemInfo(
                    item_id=item_id,
                    name=item_id.replace("_", " ").title(),
                    size_class=s.size_class(item_id),
                    wholesale_price=price,
                )

    def get_supplier(self, supplier_id: str) -> Optional[Supplier]:
        return self._suppliers.get(supplier_id)

    def list_suppliers(self) -> List[Supplier]:
        return list(self._suppliers.values())

    def product_catalog(self) -> Dict[str, ItemInfo]:
        return dict(self._product_db)

    def parse_order_from_email(
        self,
        from_agent_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        state: VendingState,
    ) -> OrderResult:
        """
        Упрощённый парсер: ищем supplier_id в to_addr (например supplier_1),
        в body — строки вида "item_id: qty" или "ITEM_ID  qty".
        Для MVP: to_addr должен быть supplier_id, body — строки product_id, quantity.
        """
        supplier_id = to_addr.strip().lower()
        supplier = self.get_supplier(supplier_id)
        if not supplier:
            return OrderResult(
                success=False,
                error_message=f"Unknown supplier: {to_addr}",
                reply_subject="Re: " + subject[:50],
                reply_body="We don't recognize this address. Please check the supplier ID.",
            )
        # Парсим body: ищем пары item_id, qty (простой формат: "snickers 50" или "snickers: 50")
        items: Dict[str, int] = {}
        for line in body.replace(",", " ").split("\n"):
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    qty = int(parts[-1])
                    name = " ".join(parts[:-1]).replace(" ", "_").lower()
                    if name in supplier.catalog and qty > 0:
                        items[name] = items.get(name, 0) + qty
                except ValueError:
                    pass
        if not items:
            return OrderResult(
                success=False,
                error_message="No valid items/quantities found in email body.",
                reply_subject="Re: " + subject[:50],
                reply_body="Please specify product names and quantities, e.g.:\n  snickers 50\n  cola 24",
            )
        total = 0.0
        prices = {}
        for item_id, qty in items.items():
            p = supplier.unit_price(item_id)
            if p is None:
                return OrderResult(
                    success=False,
                    error_message=f"Product {item_id} not in our catalog.",
                    reply_subject="Re: " + subject[:50],
                    reply_body=f"We don't carry product '{item_id}'. Our catalog: " + ", ".join(supplier.catalog.keys())[:200],
                )
            total += p * qty
            prices[item_id] = p
        if total < supplier.min_order_value:
            return OrderResult(
                success=False,
                error_message=f"Order below minimum {supplier.min_order_value}.",
                reply_subject="Re: " + subject[:50],
                reply_body=f"Minimum order value is ${supplier.min_order_value:.2f}. Your total: ${total:.2f}",
            )
        if total > state.cash_balance:
            return OrderResult(
                success=False,
                error_message="Insufficient cash balance.",
                reply_subject="Re: " + subject[:50],
                reply_body=f"Your order total is ${total:.2f} but your account balance is ${state.cash_balance:.2f}. Please reduce the order.",
            )
        lead = supplier.lead_time(self._rng)
        eta_day = state.current_day + lead
        order = Order(
            order_id=state.next_order_id(),
            supplier_id=supplier_id,
            items=dict(items),
            total_cost=total,
            eta_day=eta_day,
            status=OrderStatus.ORDERED,
            purchase_prices=prices,
        )
        return OrderResult(
            success=True,
            order=order,
            reply_subject=f"Order confirmed #{order.order_id}",
            reply_body=f"Order confirmed. Total: ${total:.2f}. Expected delivery: day {eta_day} (in {lead} days). We will charge your account upon shipment.",
        )

    def reply_to_inquiry(self, to_addr: str, body: str) -> Tuple[str, str]:
        """Ответ на письмо 'what products do you have'."""
        supplier = self.get_supplier(to_addr.strip().lower())
        if not supplier:
            return "Re: Your inquiry", "Unknown supplier. Please use a valid supplier ID."
        lines = ["Our products and prices:", ""]
        for item_id, price in supplier.catalog.items():
            lines.append(f"  {item_id}: ${price:.2f}")
        lines.append("")
        lines.append(f"Minimum order: ${supplier.min_order_value:.2f}. Delivery in {supplier.lead_time_days[0]}-{supplier.lead_time_days[1]} days.")
        return "Re: Our products", "\n".join(lines)
