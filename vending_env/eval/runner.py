"""
Прогон эпизодов: seed, лимиты, early stop при банкротстве (план 10, 12).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from vending_env.config import EnvConfig
from vending_env.tools.tool_runtime import ToolRuntime
from .metrics import EpisodeMetrics, compute_metrics


@dataclass
class StepRecord:
    """Один шаг для трассы."""
    step: int
    tool_name: str
    tool_args: Dict[str, Any]
    result: str
    net_worth: float
    day: int
    terminated: bool


def run_episode(
    agent_callback: Callable[[ToolRuntime], Optional[Dict[str, Any]]],
    config: Optional[EnvConfig] = None,
    seed: Optional[int] = None,
    max_steps: int = 2000,
    setup_suppliers: bool = True,
    trace: Optional[List[StepRecord]] = None,
) -> tuple[ToolRuntime, EpisodeMetrics, List[StepRecord]]:
    """
    Запустить один эпизод: agent_callback(runtime) вызывается каждый шаг и возвращает
    {"tool": name, "args": dict} или None для завершения.
    Возвращает (runtime, metrics, trace).
    """
    from vending_env.config import EnvConfig as DefaultConfig
    cfg = config or DefaultConfig()
    runtime = ToolRuntime(cfg, seed)
    if setup_suppliers:
        runtime.setup_default_suppliers()
    trace = trace or []
    tool_use_count: Dict[str, int] = {}
    net_worths: List[float] = [runtime.state.net_worth()]
    step = 0
    while not runtime._terminated and step < max_steps:
        action = agent_callback(runtime)
        if action is None:
            break
        tool_name = action.get("tool", "")
        tool_args = action.get("args", {})
        msg, step_result, term = runtime.execute(tool_name, tool_args)
        tool_use_count[tool_name] = tool_use_count.get(tool_name, 0) + 1
        nw = runtime.state.net_worth()
        net_worths.append(nw)
        trace.append(StepRecord(
            step=step,
            tool_name=tool_name,
            tool_args=tool_args,
            result=msg[:200],
            net_worth=nw,
            day=runtime.state.current_day,
            terminated=term,
        ))
        if term:
            break
        step += 1
    s = runtime.state
    metrics = compute_metrics(
        net_worth_final=s.net_worth(),
        net_worth_min=min(net_worths) if net_worths else 0.0,
        units_sold=s.total_units_sold,
        days_simulated=s.current_day,
        messages=step + 1,
        tool_use_count=tool_use_count,
        terminated_reason=runtime._termination_reason,
    )
    return runtime, metrics, trace
