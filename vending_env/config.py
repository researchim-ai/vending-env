"""
Конфигурация окружения по умолчанию (соответствует Vending-Bench из статьи).
"""
from dataclasses import dataclass, field
from typing import List

# По статье: $500 старт, $2/день, 4 ряда x 3 слота, 2 ряда small / 2 large
DEFAULT_INITIAL_CASH = 500.0
DEFAULT_DAILY_FEE = 2.0
DEFAULT_ROWS = 4
DEFAULT_SLOTS_PER_ROW = 3
# Слоты 0,1 — small; 2,3 — large (индексы рядов)
DEFAULT_SIZE_CLASS_BY_ROW: List[str] = ["small", "small", "large", "large"]

# Банкротство: не может оплатить fee 10 дней подряд (статья)
BANKRUPTCY_CONSECUTIVE_DAYS = 10

# Лимиты прогона (статья: 2000 сообщений, ~25M токенов)
DEFAULT_MAX_MESSAGES = 2000
DEFAULT_MAX_DAYS = 400  # опциональный лимит по дням

# Время на инструмент (минуты) — по статье: 5 min, 25 min, 75 min, 5 h
TIME_COST_MINUTES = {
    "get_money_balance": 5,
    "get_storage_inventory": 5,
    "read_inbox": 25,
    "send_email": 25,
    "search_products": 25,
    "wait_for_next_day": 0,  # специальный: переход в конец дня
    "sub_agent_specs": 5,
    "run_sub_agent": 75,
    "chat_with_sub_agent": 25,
    # sub-agent tools
    "machine_inventory": 5,
    "stock_from_storage": 25,
    "set_price": 5,
    "collect_cash": 25,
}
# 5h = 300 min для долгих операций (например run_sub_agent можно считать 75 min по статье)
FALLBACK_TIME_MINUTES = 30


@dataclass
class EnvConfig:
    initial_cash: float = DEFAULT_INITIAL_CASH
    daily_fee: float = DEFAULT_DAILY_FEE
    rows: int = DEFAULT_ROWS
    slots_per_row: int = DEFAULT_SLOTS_PER_ROW
    size_class_by_row: List[str] = field(default_factory=lambda: list(DEFAULT_SIZE_CLASS_BY_ROW))
    bankruptcy_consecutive_days: int = BANKRUPTCY_CONSECUTIVE_DAYS
    max_messages: int = DEFAULT_MAX_MESSAGES
    max_days: int = DEFAULT_MAX_DAYS
    time_cost_minutes: dict = field(default_factory=lambda: dict(TIME_COST_MINUTES))
    fallback_time_minutes: int = FALLBACK_TIME_MINUTES

    @property
    def total_slots(self) -> int:
        return self.rows * self.slots_per_row

    def get_time_cost_minutes(self, tool_name: str) -> int:
        return self.time_cost_minutes.get(tool_name, self.fallback_time_minutes)
