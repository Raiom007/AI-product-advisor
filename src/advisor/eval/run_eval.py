import argparse
import hashlib
import json
import random
from pathlib import Path

from advisor.core.registries import eval_suites


def get_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:8]

def load_jsonl(path: str):
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def main():
    parser = argparse.ArgumentParser(description="Run evaluation suite")
    parser.add_argument("--mode", choices=["replay", "live"], required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    random.seed(42)

    suite_runner = eval_suites.get(args.suite)
    if not suite_runner:
        raise ValueError(f"Unknown suite: {args.suite}")

    print(f"Running suite {args.suite} in mode {args.mode}...")

    # Read files
    queries = load_jsonl("eval/data/queries.jsonl")
    try:
        gold = load_jsonl("eval/data/gold.jsonl")
    except FileNotFoundError:
        gold = []

    try:
        # Pass to the suite
        suite_metrics = suite_runner(queries, gold, args.mode)
    except Exception as e:
        print(f"Error running suite: {e}")
        raise

    report = {
        "header": {
            "mode": args.mode,
            "suite": args.suite,
            "data_hash": get_hash(json.dumps(queries)),
            "config_hash": "dummy_config",
        },
        "metrics": suite_metrics or {"dummy": 1}
    }

    Path("eval").mkdir(exist_ok=True)
    with open("eval/metrics.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("Wrote eval/metrics.json")

if __name__ == "__main__":
    main()
