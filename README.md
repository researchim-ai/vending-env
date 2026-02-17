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
- **`vending_env/eval/`** — прогон эпизодов, метрики, **генерация данных для тренировки** (траектории, RL-пары, LLM SFT).

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

## Генерация данных для тренировки

Можно генерировать датасеты для imitation learning, RL или SFT LLM.

**Политики:** `rule_based` (эвристика: заказы при низком запасе, restock, collect_cash, wait_for_next_day) и `random`.

**Форматы экспорта (JSONL):**
- **`trajectory`** — один эпизод на строку: список шагов (tool, args, result, net_worth, day) + метрики.
- **`rl`** — один шаг на строку: `obs`, `action`, `reward`, `next_obs` (при `capture_state_snapshots` в `obs` полный снимок состояния).
- **`llm_sft`** — один пример на строку: `messages` (контекст) + `target_tool`, `target_args` для supervised fine-tuning.

**CLI:**
```bash
# 20 эпизодов, rule_based, полные траектории
python scripts/generate_training_data.py --out data/trajectories.jsonl --n 20 --format trajectory

# 10 эпизодов, пары (obs, action, reward) для RL
python scripts/generate_training_data.py --out data/rl_steps.jsonl --n 10 --format rl --max-steps 200

# Примеры для SFT LLM (контекст → следующий tool call)
python scripts/generate_training_data.py --out data/llm_sft.jsonl --n 5 --format llm_sft
```

**Программно:**
```python
from vending_env.eval import generate_episodes, export_episodes_to_jsonl, trace_to_rl_sequences

# Итерация по эпизодам
for trace, metrics, snapshots in generate_episodes(5, policy="rule_based", base_seed=42, max_steps=200):
    print(metrics.net_worth_final, metrics.units_sold)

# Сразу экспорт в файл
export_episodes_to_jsonl("data/out.jsonl", n_episodes=10, format="rl", policy="rule_based")
```

## Метрики (как в статье)

- **Net worth** — основной скор: наличные + наличные в автомате + стоимость остатков по закупочным ценам.
- Units sold, days simulated, tool use, причина завершения (bankruptcy / max_days / max_messages).

## Лицензия

См. `LICENSE`.
