"""
Состояние мира: финансы, инвентарь, автомат, заказы, почта, время.
Соответствует разделу 2 плана и статье (Vending-Bench).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class OrderStatus(str, Enum):
    ORDERED = "ordered"           # заказ отправлен
    IN_TRANSIT = "in_transit"     # в пути
    DELIVERED_TO_STORAGE = "delivered_to_storage"  # доставлено на склад


@dataclass
class Slot:
    """Один слот в автомате: ряд/слот, размер (small/large), товар, остаток, вместимость."""
    slot_id: int
    row: int
    column: int
    size_class: str  # "small" | "large"
    item_id: Optional[str] = None
    quantity: int = 0
    capacity: int = 10  # макс единиц в слоте

    def can_fit(self, size_class: str) -> bool:
        return self.size_class == size_class and self.quantity < self.capacity

    @property
    def free(self) -> int:
        return max(0, self.capacity - self.quantity)


@dataclass
class Order:
    """Открытый заказ поставщику."""
    order_id: str
    supplier_id: str
    items: Dict[str, int]  # item_id -> qty
    total_cost: float
    eta_day: int  # день симуляции, когда ожидается доставка
    status: OrderStatus = OrderStatus.ORDERED
    purchase_prices: Dict[str, float] = field(default_factory=dict)  # item_id -> price per unit


@dataclass
class Email:
    """Письмо во входящих или исходящих."""
    email_id: str
    from_addr: str
    to_addr: str
    subject: str
    body: str
    day_sent: int
    is_read: bool = False


@dataclass
class DailyReport:
    """Утренний отчёт: что куплено вчера, что доставлено, новые письма (статья 2.2)."""
    day: int
    sales: Dict[str, int]  # item_id -> units sold yesterday
    deliveries: List[str]  # order_ids или описания доставок
    new_emails: List[Email]
    cash_collected_yesterday: float = 0.0


@dataclass
class ItemInfo:
    """Справочная информация о товаре: размер, закупочная цена (для net worth)."""
    item_id: str
    name: str
    size_class: str
    wholesale_price: float  # для оценки стоимости остатков


@dataclass
class VendingState:
    """
    Полное состояние симуляции (план 2.1–2.5).
    """
    # Финансы
    cash_balance: float
    cash_in_machine: float  # не собранная наличность в автомате
    daily_fee: float

    # Инвентарь: склад (куда приходят заказы)
    storage_inventory: Dict[str, int] = field(default_factory=dict)  # item_id -> qty

    # Автомат: слоты
    machine_slots: List[Slot] = field(default_factory=list)
    prices: Dict[str, float] = field(default_factory=dict)  # item_id -> цена продажи

    # Справочник товаров (id -> размер, закупочная цена)
    item_catalog: Dict[str, ItemInfo] = field(default_factory=dict)

    # Заказы
    open_orders: List[Order] = field(default_factory=list)
    _order_counter: int = 0

    # Почта
    inbox: List[Email] = field(default_factory=list)
    outbox: List[Email] = field(default_factory=list)
    _email_counter: int = 0

    # Время
    current_day: int = 0
    minute_of_day: int = 0  # 0..1439
    total_minutes_elapsed: int = 0

    # Для банкротства (статья: 10 дней подряд не может оплатить fee)
    consecutive_days_unpaid_fee: int = 0

    # Счётчики для eval
    total_units_sold: int = 0
    total_days: int = 0

    def next_order_id(self) -> str:
        self._order_counter += 1
        return f"order_{self._order_counter}"

    def next_email_id(self) -> str:
        self._email_counter += 1
        return f"email_{self._email_counter}"

    def slot_by_id(self, slot_id: int) -> Optional[Slot]:
        for s in self.machine_slots:
            if s.slot_id == slot_id:
                return s
        return None

    def net_worth(self) -> float:
        """Чистая стоимость: наличные + в автомате + стоимость остатков по закупочным ценам (статья 2.4)."""
        cash = self.cash_balance + self.cash_in_machine
        inventory_value = 0.0
        for item_id, qty in self.storage_inventory.items():
            if item_id in self.item_catalog and qty > 0:
                inventory_value += self.item_catalog[item_id].wholesale_price * qty
        for slot in self.machine_slots:
            if slot.item_id and slot.quantity > 0 and slot.item_id in self.item_catalog:
                inventory_value += self.item_catalog[slot.item_id].wholesale_price * slot.quantity
        return cash + inventory_value

    def unread_emails_count(self) -> int:
        return sum(1 for e in self.inbox if not e.is_read)
