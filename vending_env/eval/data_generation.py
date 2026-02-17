"""
Генерация данных для тренировки: прогон эпизодов с разными политиками и экспорт в JSONL.
Форматы: траектории для RL (obs, action, reward), пары (контекст, действие) для imitation/LLM.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from vending_env.config import EnvConfig
from vending_env.tools.tool_runtime import ToolRuntime
from vending_env.eval.runner import run_episode, StepRecord
from vending_env.eval.metrics import EpisodeMetrics
from vending_env.eval.snapshots import state_snapshot


def rule_based_policy(runtime: ToolRuntime, rng: random.Random) -> Optional[Dict[str, Any]]:
    """
    Простая эвристическая политика для генерации «хороших» трасс:
    - раз в N шагов — wait_for_next_day;
    - при наличии денег и пустом складе/мало товара — заказ;
    - при наличии товара на складе — restock через sub_agent;
    - периодически — collect_cash, get_money_balance.
    """
    if runtime._terminated:
        return None
    s = runtime.state
    # Каждый 3–5 шаг — следующий день
    if rng.random() < 0.25:
        return {"tool": "wait_for_next_day", "args": {}}
    # Собирать наличные, если есть в автомате
    if s.cash_in_machine > 5:
        return {"tool": "run_sub_agent", "args": {"instruction": "collect cash"}}
    # Заказ: если баланс достаточный и мало товара на складе
    total_storage = sum(s.storage_inventory.values())
    if s.cash_balance > 80 and total_storage < 30:
        body = "cola 30\nchips 20" if rng.random() < 0.5 else "water 40\nsnickers 20"
        return {"tool": "send_email", "args": {"to_addr": "supplier_1", "subject": "Order", "body": body}}
    # Restock: если на складе есть товар и в автомате есть пустые слоты
    if total_storage > 0:
        for item_id, qty in list(s.storage_inventory.items())[:3]:
            if qty <= 0:
                continue
            info = s.item_catalog.get(item_id)
            if not info:
                continue
            for slot in s.machine_slots:
                if slot.size_class != info.size_class or slot.quantity >= slot.capacity:
                    continue
                if slot.item_id and slot.item_id != item_id:
                    continue
                put = min(qty, slot.capacity - slot.quantity)
                if put > 0:
                    return {"tool": "run_sub_agent", "args": {"instruction": f"restock {item_id} {put} in slot {slot.slot_id}"}}
    # Проверить баланс / склад
    if rng.random() < 0.3:
        return {"tool": "get_money_balance", "args": {}}
    if rng.random() < 0.3:
        return {"tool": "get_storage_inventory", "args": {}}
    return {"tool": "wait_for_next_day", "args": {}}


def random_policy(runtime: ToolRuntime, rng: random.Random) -> Optional[Dict[str, Any]]:
    """Случайный выбор из базовых инструментов."""
    if runtime._terminated:
        return None
    tools = [
        ("get_money_balance", {}),
        ("get_storage_inventory", {}),
        ("read_inbox", {}),
        ("wait_for_next_day", {}),
        ("run_sub_agent", {"instruction": "collect cash"}),
    ]
    if runtime.state.cash_balance > 60:
        tools.append(("send_email", {"to_addr": "supplier_1", "subject": "Order", "body": "cola 50"}))
    t, a = rng.choice(tools)
    return {"tool": t, "args": a}


def generate_episodes(
    n_episodes: int,
    policy: str | Callable[[ToolRuntime], Optional[Dict[str, Any]]] = "rule_based",
    config: Optional[EnvConfig] = None,
    base_seed: Optional[int] = None,
    max_steps: int = 500,
    capture_state_snapshots: bool = True,
) -> Iterator[Tuple[List[StepRecord], EpisodeMetrics, List[Dict[str, Any]]]]:
    """
    Генерирует n_episodes траекторий.
    policy: "rule_based" | "random" | или callable(runtime) -> action | None.
    capture_state_snapshots: сохранять state_snapshot в каждом StepRecord (для RL/обучения).
    Yields (trace, metrics, snapshots), где snapshots — список снимков из trace (если capture_state_snapshots).
    """
    from vending_env.config import EnvConfig as DefaultConfig
    cfg = config or DefaultConfig()
    rng = random.Random(base_seed)
    if policy == "rule_based":
        def _policy(rt):
            return rule_based_policy(rt, rng)
    elif policy == "random":
        def _policy(rt):
            return random_policy(rt, rng)
    else:
        _policy = policy
    for i in range(n_episodes):
        seed = (base_seed + i * 1000) if base_seed is not None else None
        runtime, metrics, trace = run_episode(
            _policy, config=cfg, seed=seed, max_steps=max_steps,
            setup_suppliers=True, capture_state_snapshots=capture_state_snapshots,
        )
        snapshots = [r.state_snapshot for r in trace if r.state_snapshot is not None]
        yield trace, metrics, snapshots


def trace_to_rl_sequences(
    trace: List[StepRecord],
    runtime_after_episode: Optional[ToolRuntime] = None,
) -> List[Dict[str, Any]]:
    """
    Преобразует трассу в последовательность (obs, action, reward, next_obs) для RL.
    Если в StepRecord есть state_snapshot — используем его как obs/next_obs.
    """
    out = []
    for i, rec in enumerate(trace):
        next_rec = trace[i + 1] if i + 1 < len(trace) else None
        reward = (next_rec.net_worth - rec.net_worth) if next_rec else 0.0
        obs = rec.state_snapshot if rec.state_snapshot is not None else {"day": rec.day, "net_worth": rec.net_worth}
        next_obs = (next_rec.state_snapshot if next_rec.state_snapshot is not None else {"day": next_rec.day, "net_worth": next_rec.net_worth}) if next_rec else None
        out.append({
            "step": rec.step,
            "obs": obs,
            "action": {"tool": rec.tool_name, "args": rec.tool_args},
            "reward": reward,
            "next_obs": next_obs,
        })
    return out


def trace_to_llm_sft_records(
    trace: List[StepRecord],
    system_prompt: str,
) -> List[Dict[str, Any]]:
    """
    Формирует примеры для SFT LLM: список сообщений (role, content) с tool_calls.
    Один пример = один шаг: контекст (предыдущие шаги) + ответ ассистента с tool_call.
    """
    from vending_env.agents.llm.loop import LLMAgentLoop
    loop = LLMAgentLoop()
    base_system = loop.get_system_prompt()
    system = system_prompt or base_system
    records = []
    messages = [{"role": "system", "content": system}]
    for rec in trace:
        # Ответ ассистента = вызов инструмента
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": rec.tool_name, "args": rec.tool_args}],
        })
        messages.append({"role": "tool", "content": rec.result[:500]})
        # Один SFT пример: всё до ответа ассистента — input, ответ ассистента — target
        records.append({
            "messages": messages[:-1].copy(),
            "target_tool": rec.tool_name,
            "target_args": rec.tool_args,
        })
    return records


def export_episodes_to_jsonl(
    output_path: str | Path,
    n_episodes: int = 10,
    policy: str = "rule_based",
    config: Optional[EnvConfig] = None,
    base_seed: int = 42,
    max_steps: int = 300,
    format: str = "trajectory",
) -> int:
    """
    Генерирует эпизоды и сохраняет в JSONL.
    format: "trajectory" (каждая строка = полный эпизод), "rl" (каждая строка = шаг), "llm_sft" (каждая строка = один SFT пример).
    Возвращает число записанных строк.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for trace, metrics, _ in generate_episodes(n_episodes, policy=policy, config=config, base_seed=base_seed, max_steps=max_steps):
            if format == "trajectory":
                episode = {
                    "trace": [
                        {"step": r.step, "tool": r.tool_name, "args": r.tool_args, "result": r.result, "net_worth": r.net_worth, "day": r.day}
                        for r in trace
                    ],
                    "metrics": {
                        "net_worth_final": metrics.net_worth_final,
                        "units_sold": metrics.units_sold,
                        "days_simulated": metrics.days_simulated,
                        "terminated_reason": metrics.terminated_reason,
                    },
                }
                f.write(json.dumps(episode, ensure_ascii=False) + "\n")
                count += 1
            elif format == "rl":
                seqs = trace_to_rl_sequences(trace)
                for rec in seqs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    count += 1
            elif format == "llm_sft":
                records = trace_to_llm_sft_records(trace, system_prompt="")
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    count += 1
    return count
