# Vending Env

Окружение в стиле **Vending-Bench** для обучения RL- и LLM-агентов: длинный горизонт, управление автоматом (запасы, заказы, цены, ежедневный сбор).

Воспроизведено по статье [Vending-Bench: A Benchmark for Long-Term Coherence of Autonomous Agents](https://arxiv.org/abs/2502.15840)

## Установка

```bash
pip install -e .
# или
pip install -r requirements.txt
```

## Структура проекта

- **`vending_env/core/`** — ядро симуляции: состояние (`state`), события (`events`), экономика спроса (`economy`), поставщики и e-mail (`suppliers`), движок (`sim`).
- **`vending_env/tools/`** — описание инструментов (JSON schema), исполнение (`tool_runtime`), память (scratchpad, kv).
- **`vending_env/agents/subagent/`** — саб-агент «физического мира»: restock, set_price, collect_cash.
- **`vending_env/agents/llm/`** — цикл LLM-агента с tool calling и памятью.
- **`vending_env/env/`** — Gymnasium-окружение для RL.
- **`vending_env/eval/`** — прогон эпизодов, метрики (net worth, units sold, days).

## Быстрый старт

### Случайный агент (CLI)

```bash
python scripts/run_random_agent.py --seed 42 --max-steps 300
```

### Программно: Tool Runtime (LLM-стиль)

```python
from vending_env.tools.tool_runtime import ToolRuntime

runtime = ToolRuntime()
runtime.setup_default_suppliers()

msg, term = runtime.run_main_tool("get_money_balance", {})
# "Cash at hand: $500.00. Cash in machine: $0.00."

msg, term = runtime.run_main_tool("send_email", {
    "to_addr": "supplier_1", "subject": "Order", "body": "cola 50"
})
msg, term = runtime.run_main_tool("wait_for_next_day", {})
```

### Gymnasium (RL)

```python
from vending_env.env import VendingEnv

env = VendingEnv(seed=42)
obs, info = env.reset()
action = env.action_space.sample()
obs, reward, terminated, truncated, info = env.step(action)
```

## Конфигурация

- Стартовый баланс: **$500**, ежедневный сбор **$2**.
- Банкротство: **10** дней подряд без оплаты сбора.
- Автомат: **4 ряда × 3 слота**; два ряда под small, два под large.
- Время за инструменты: 5 / 25 / 75 мин (по умолчанию).

См. `vending_env/config.py` и `EnvConfig`.

## Метрики (как в статье)

- **Net worth** — основной скор: наличные + наличные в автомате + стоимость остатков по закупочным ценам.
- Units sold, days simulated, tool use, причина завершения (bankruptcy / max_days / max_messages).

## Лицензия

См. `LICENSE`.
