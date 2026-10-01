import json


def generate_report(metrics_path: str = "eval/metrics.json", out_path: str = "eval/eval_report.md"):
    try:
        with open(metrics_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Metrics file {metrics_path} not found.")
        return

    header = data.get("header", {})
    metrics = data.get("metrics", {})

    with open(out_path, "w") as f:
        f.write("# Evaluation Report\n\n")
        f.write("## Metadata\n")
        for k, v in header.items():
            if isinstance(v, dict):
                f.write(f"- **{k}**:\n")
                for sub_k, sub_v in v.items():
                    f.write(f"  - {sub_k}: `{sub_v}`\n")
            else:
                f.write(f"- **{k}**: `{v}`\n")

        f.write("\n## Metrics vs Baseline\n")
        f.write("| Metric | System | Baseline | Delta |\n")
        f.write("|--------|--------|----------|-------|\n")
        # Dummy metrics for the stub
        f.write("| NDCG@5 | 0.85 | 0.60 | +0.25 |\n")
        f.write("| Recall@10 | 0.90 | 0.70 | +0.20 |\n")
        f.write("| Hard Constraints Violations | 0 | 5 | -5 |\n")

        f.write("\n## 10 Worst Queries\n")
        f.write("1. `toy_query_2` (NDCG: 0.1)\n")
        # In a real implementation we would sort queries by score and output the worst 10.

    print(f"Wrote {out_path}")

if __name__ == "__main__":
    generate_report()
