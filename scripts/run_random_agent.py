#!/usr/bin/env python3
"""
CLI: прогон случайного агента на 200 дней (план 12, этап A).
"""
import argparse
import random
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Run random vending agent")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-days", type=int, default=200)
    parser.add_argument("--max-steps", type=int, default=500)
    args = parser.parse_args()

    from vending_env.tools.tool_runtime import ToolRuntime
    from vending_env.eval.runner import run_episode
    from vending_env.config import EnvConfig

    config = EnvConfig(max_days=args.max_days, max_messages=args.max_steps)
    rng = random.Random(args.seed)
    tools_cycle = [
        ("get_money_balance", {}),
        ("get_storage_inventory", {}),
        ("wait_for_next_day", {}),
        ("run_sub_agent", {"instruction": "collect cash"}),
    ]

    def random_agent(runtime):
        if runtime._terminated:
            return None
        if rng.random() < 0.15 and runtime.state.cash_balance > 60:
            return {"tool": "send_email", "args": {"to_addr": "supplier_1", "subject": "Order", "body": "cola 50"}}
        t, a = rng.choice(tools_cycle)
        return {"tool": t, "args": a}

    runtime, metrics, trace = run_episode(
        random_agent,
        config=config,
        seed=args.seed,
        max_steps=args.max_steps,
        setup_suppliers=True,
    )
    print("=== Episode finished ===")
    print(f"Net worth (final): {metrics.net_worth_final:.2f}")
    print(f"Units sold: {metrics.units_sold}")
    print(f"Days simulated: {metrics.days_simulated}")
    print(f"Steps: {len(trace)}")
    print(f"Terminated: {metrics.terminated_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
