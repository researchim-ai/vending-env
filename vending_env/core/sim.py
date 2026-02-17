"""
Движок симуляции: применение действий, продвижение времени, события, продажи (план 3).
Соответствует статье: tool step двигает время (5/25/75/300 мин), wait_for_next_day — конец дня.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..config import EnvConfig
from .state import (
    VendingState,
    Slot,
    Order,
    OrderStatus,
    Email,
    DailyReport,
    ItemInfo,
)
from .events import Event, EventType, EventQueue
from .economy import Economy
from .suppliers import SupplierRegistry, OrderResult, Supplier


def _build_initial_slots(config: EnvConfig) -> List[Slot]:
    slots = []
    slot_id = 0
    for row in range(config.rows):
        size_class = config.size_class_by_row[row] if row < len(config.size_class_by_row) else "small"
        for col in range(config.slots_per_row):
            slots.append(Slot(
                slot_id=slot_id,
                row=row,
                column=col,
                size_class=size_class,
                item_id=None,
                quantity=0,
                capacity=10,
            ))
            slot_id += 1
    return slots


def create_initial_state(config: EnvConfig, seed: int | None = None) -> VendingState:
    """Создать начальное состояние (пустой автомат, баланс, пустая почта)."""
    slots = _build_initial_slots(config)
    return VendingState(
        cash_balance=config.initial_cash,
        cash_in_machine=0.0,
        daily_fee=config.daily_fee,
        storage_inventory={},
        machine_slots=slots,
        prices={},
        item_catalog={},
        open_orders=[],
        inbox=[],
        outbox=[],
        current_day=0,
        minute_of_day=0,
        total_minutes_elapsed=0,
        consecutive_days_unpaid_fee=0,
        total_units_sold=0,
        total_days=0,
    )


@dataclass
class SimStepResult:
    """Результат одного шага симуляции."""
    state: VendingState
    daily_report: Optional[DailyReport] = None  # только после wait_for_next_day
    events_processed: List[Event] = field(default_factory=list)
    error: Optional[str] = None
    terminated: bool = False  # банкротство или лимит
    termination_reason: Optional[str] = None


class Sim:
    """
    Главный движок: состояние, очередь событий, экономика, поставщики.
    Два вида шагов: tool step (время +Δt) и end_of_day (продажи, fee, отчёт).
    """
    def __init__(self, config: EnvConfig, seed: int | None = None):
        self.config = config
        self._seed = seed
        self._rng = random.Random(seed)
        self.state = create_initial_state(config, seed)
        self.event_queue = EventQueue()
        self.economy = Economy(seed)
        self.suppliers = SupplierRegistry(seed)
        self._last_report: Optional[DailyReport] = None
        self._message_count = 0

    def _process_events_until(self, day: int, minute: int) -> List[Event]:
        """Обработать все события до (day, minute). Доставки добавляют товар на склад и письмо."""
        processed = []
        for ev in self.event_queue.pop_until(day, minute):
            processed.append(ev)
            if ev.kind == EventType.DELIVERY:
                order_id = ev.payload.get("order_id")
                for o in self.state.open_orders:
                    if o.order_id == order_id:
                        for item_id, qty in o.items.items():
                            self.state.storage_inventory[item_id] = \
                                self.state.storage_inventory.get(item_id, 0) + qty
                        # Деньги списаны при оформлении заказа
                        break
                # Удаляем заказ из open_orders и помечаем доставленным
                self.state.open_orders = [o for o in self.state.open_orders if o.order_id != order_id]
                # Письмо о доставке
                self.state.inbox.append(Email(
                    email_id=self.state.next_email_id(),
                    from_addr=ev.payload.get("supplier_id", "supplier"),
                    to_addr="agent",
                    subject=f"Delivery completed #{order_id}",
                    body=f"Your order {order_id} has been delivered. Items are now in your storage.",
                    day_sent=day,
                ))
            elif ev.kind == EventType.DAILY_FEE:
                fee = ev.payload.get("amount", self.config.daily_fee)
                self.state.cash_balance -= fee
        return processed

    def _charge_for_order(self, order: Order) -> bool:
        """Списать деньги при принятии заказа (резервирование). Возвращает True если успех."""
        if self.state.cash_balance < order.total_cost:
            return False
        self.state.cash_balance -= order.total_cost
        return True

    def _schedule_delivery(self, order: Order, delivery_day: int) -> None:
        """Доставка может быть в середине дня (статья — источник срывов агентов)."""
        delivery_minute = self._rng.randint(0, 1439)  # случайный момент в течение дня
        self.event_queue.push(Event(
            ts=0,
            day=delivery_day,
            minute=delivery_minute,
            kind=EventType.DELIVERY,
            payload={"order_id": order.order_id, "supplier_id": order.supplier_id},
        ))

    def apply_tool_step(self, tool_name: str, tool_args: Dict[str, Any]) -> SimStepResult:
        """
        Применить один вызов инструмента (без wait_for_next_day).
        Время двигается на config.get_time_cost_minutes(tool_name).
        События (доставки) обрабатываются при переходе времени.
        """
        self._message_count += 1
        dt = self.config.get_time_cost_minutes(tool_name)
        state = self.state
        # Переход времени
        state.minute_of_day += dt
        state.total_minutes_elapsed += dt
        while state.minute_of_day >= 1440:
            state.minute_of_day -= 1440
            state.current_day += 1
            state.total_days = state.current_day
        # Обработать события до текущего момента
        processed = self._process_events_until(state.current_day, state.minute_of_day)
        return SimStepResult(state=state, events_processed=processed)

    def process_order_email(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
    ) -> OrderResult:
        """Обработать исходящее письмо агента как заказ поставщику."""
        result = self.suppliers.parse_order_from_email(
            from_addr, to_addr, subject, body, self.state
        )
        if result.success and result.order:
            order = result.order
            if self.state.cash_balance >= order.total_cost:
                self.state.cash_balance -= order.total_cost
                self.state.open_orders.append(order)
                self._schedule_delivery(order, order.eta_day)
            else:
                result.success = False
                result.error_message = "Insufficient balance."
                result.reply_body = "Insufficient account balance for this order."
        return result

    def end_day_and_report(self) -> SimStepResult:
        """
        Вызвать после wait_for_next_day: перейти в конец текущего дня,
        симулировать продажи, списать fee, сформировать утренний отчёт на следующий день.
        """
        state = self.state
        state.total_days = max(state.total_days, state.current_day)
        # Перейти в конец дня (или начало следующего — как в статье "every morning agent is notified")
        # Статья: "wait_for_next_day" -> уведомление утром о том, что куплено, и о новых письмах.
        # Значит: мы в конце дня N делаем продажи дня N, списываем fee за день N, затем переходим на утро дня N+1 и выдаём отчёт.
        day = state.current_day
        # Обработать все события до конца дня
        processed = self._process_events_until(day, 1439)
        # Продажи за этот день
        sales, revenue, cash_collected = self.economy.compute_daily_sales(state, day)
        # Обновить слоты и cash_in_machine
        for item_id, qty in sales.items():
            state.total_units_sold += qty
            for slot in state.machine_slots:
                if slot.item_id == item_id and qty > 0:
                    take = min(slot.quantity, qty)
                    slot.quantity -= take
                    qty -= take
                    if qty <= 0:
                        break
        state.cash_in_machine += cash_collected
        # Списание daily fee (в конце дня)
        if state.cash_balance >= state.daily_fee:
            state.cash_balance -= state.daily_fee
            state.consecutive_days_unpaid_fee = 0
        else:
            state.consecutive_days_unpaid_fee += 1
        # Переход на утро следующего дня
        state.current_day += 1
        state.minute_of_day = 0
        state.total_minutes_elapsed = state.current_day * 1440
        state.total_days = state.current_day
        # Утренний отчёт
        new_emails = [e for e in state.inbox if not e.is_read]
        report = DailyReport(
            day=state.current_day,
            sales=sales,
            deliveries=[],  # можно заполнить из processed DELIVERY
            new_emails=new_emails,
            cash_collected_yesterday=cash_collected,
        )
        self._last_report = report
        # Проверка банкротства
        terminated = False
        reason = None
        if state.consecutive_days_unpaid_fee >= self.config.bankruptcy_consecutive_days:
            terminated = True
            reason = "bankruptcy"
        if state.current_day >= self.config.max_days:
            terminated = True
            reason = reason or "max_days"
        if self._message_count >= self.config.max_messages:
            terminated = True
            reason = reason or "max_messages"
        return SimStepResult(
            state=state,
            daily_report=report,
            events_processed=processed,
            terminated=terminated,
            termination_reason=reason,
        )

    def get_last_report(self) -> Optional[DailyReport]:
        return self._last_report

    def register_supplier(self, supplier: Supplier) -> None:
        """Зарегистрировать поставщика и обновить каталог товаров в state."""
        self.suppliers.register_supplier(supplier)
        self.state.item_catalog = self.suppliers.product_catalog()

    def copy_state(self) -> VendingState:
        """Глубокий копия состояния (для логирования/реплеев)."""
        return copy.deepcopy(self.state)
