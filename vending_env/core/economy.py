"""
Модель спроса: эластичность по цене, день недели, месяц, погода, разнообразие, шум (статья 2.2.2).
Без LLM внутри — сэмплируем параметры при первом появлении товара.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List

from .state import VendingState, Slot, ItemInfo


@dataclass
class ItemDemandParams:
    """Кэш параметров спроса на товар (как в статье: elasticity, reference_price, base_sales)."""
    item_id: str
    elasticity: float   # отрицательная эластичность по цене
    reference_price: float
    base_sales: float   # базовая дневная продажа при ref_price


class Economy:
    """
    Расчёт дневных продаж по слотам автомата.
    demand_i = base_sales_i * f_price * f_dow * f_season * f_weather * f_variety + noise
    """
    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._demand_params: Dict[str, ItemDemandParams] = {}
        # Погода: простой марковский вариант (0=плохо, 1=норма, 2=хорошо)
        self._weather_state = 1
        self._weather_seed = seed

    def _get_or_create_params(self, item_id: str, wholesale_price: float) -> ItemDemandParams:
        if item_id in self._demand_params:
            return self._demand_params[item_id]
        # Логнормальная эластичность (отрицательная), ref_price около wholesale * 1.5
        elasticity = -self._rng.lognormvariate(0.8, 0.3)
        ref_price = wholesale_price * (1.0 + self._rng.uniform(0.2, 0.8))
        base_sales = max(0.5, self._rng.lognormvariate(1.0, 0.5))
        params = ItemDemandParams(
            item_id=item_id,
            elasticity=elasticity,
            reference_price=ref_price,
            base_sales=base_sales,
        )
        self._demand_params[item_id] = params
        return params

    def _f_price(self, price: float, params: ItemDemandParams) -> float:
        """Процентное отклонение от reference_price и эластичность."""
        if params.reference_price <= 0:
            return 1.0
        pct_diff = (price - params.reference_price) / params.reference_price
        # impact = (1 + pct_diff)^elasticity (elasticity < 0 => выше цена — меньше продажи)
        return math.pow(1.0 + pct_diff, params.elasticity)

    def _f_dow(self, day: int) -> float:
        """День недели: 0=пн .. 6=вс. Выходные выше (как в статье)."""
        dow = day % 7
        if dow >= 5:  # сб, вс
            return 1.2
        return 1.0

    def _f_season(self, day: int) -> float:
        """Упрощённо: месяц из дня (30 дней = 1 месяц). Лето чуть выше."""
        month = (day // 30) % 12
        if 5 <= month <= 7:  # июнь–август
            return 1.1
        return 1.0

    def _f_weather(self) -> float:
        """Погода: марковский шаг."""
        r = self._rng.random()
        if r < 0.1:
            self._weather_state = max(0, self._weather_state - 1)
        elif r > 0.9:
            self._weather_state = min(2, self._weather_state + 1)
        return 0.85 + 0.15 * self._weather_state

    def _f_variety(self, num_distinct_items: int) -> float:
        """Поощрение разнообразия, штраф за избыток (статья: cap 50% reduction)."""
        if num_distinct_items <= 0:
            return 0.5
        if num_distinct_items <= 4:
            return 0.8 + 0.05 * num_distinct_items  # 0.85..1.0
        if num_distinct_items <= 8:
            return 1.0
        # Слишком много SKU — штраф, макс 50%
        return max(0.5, 1.0 - 0.05 * (num_distinct_items - 8))

    def compute_daily_sales(
        self,
        state: VendingState,
        day: int,
    ) -> tuple[Dict[str, int], Dict[str, float], float]:
        """
        Рассчитать продажи за день по всем слотам.
        Returns: (sales_per_item, revenue_per_item, total_cash_collected)
        """
        sales: Dict[str, int] = {}
        revenue: Dict[str, float] = {}
        distinct_items = set()
        for slot in state.machine_slots:
            if slot.item_id and slot.quantity > 0:
                distinct_items.add(slot.item_id)
        variety = self._f_variety(len(distinct_items))
        weather = self._f_weather()
        f_dow = self._f_dow(day)
        f_season = self._f_season(day)

        total_cash = 0.0
        for slot in state.machine_slots:
            if not slot.item_id or slot.quantity <= 0:
                continue
            item_id = slot.item_id
            price = state.prices.get(item_id, 0.0)
            if item_id not in state.item_catalog:
                continue
            info = state.item_catalog[item_id]
            params = self._get_or_create_params(item_id, info.wholesale_price)
            f_price = self._f_price(price, params)
            raw_demand = (
                params.base_sales
                * f_price
                * f_dow
                * f_season
                * weather
                * variety
            )
            noise = self._rng.gauss(0, 0.15 * raw_demand)
            demand = max(0, raw_demand + noise)
            sold = min(slot.quantity, int(round(demand)))
            if sold > 0:
                sales[item_id] = sales.get(item_id, 0) + sold
                rev = sold * price
                revenue[item_id] = revenue.get(item_id, 0.0) + rev
                total_cash += rev

        return sales, revenue, total_cash
