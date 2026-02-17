#!/usr/bin/env python3
"""
Генерация данных для тренировки: эпизоды с rule_based или random политикой, экспорт в JSONL.
Примеры:
  python scripts/generate_training_data.py --out data/trajectories.jsonl --n 20 --format trajectory
  python scripts/generate_training_data.py --out data/rl_steps.jsonl --n 10 --format rl --max-steps 200
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vending_env.eval.data_generation import export_episodes_to_jsonl


def main():
    parser = argparse.ArgumentParser(description="Generate vending env training data")
    parser.add_argument("--out", type=str, default="data/trajectories.jsonl", help="Output JSONL path")
    parser.add_argument("--n", type=int, default=10, help="Number of episodes")
    parser.add_argument("--policy", type=str, default="rule_based", choices=["rule_based", "random"])
    parser.add_argument("--format", type=str, default="trajectory", choices=["trajectory", "rl", "llm_sft"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=300)
    args = parser.parse_args()

    count = export_episodes_to_jsonl(
        output_path=args.out,
        n_episodes=args.n,
        policy=args.policy,
        base_seed=args.seed,
        max_steps=args.max_steps,
        format=args.format,
    )
    print(f"Wrote {count} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
