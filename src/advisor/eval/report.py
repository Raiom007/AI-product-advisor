import json
import statistics


def generate_report(metrics_path: str = "eval/metrics.json", out_path: str = "eval/eval_report.md"):
    try:
        with open(metrics_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Metrics file {metrics_path} not found.")
        return

    header = data.get("header", {})
    metrics = data.get("metrics", {})

    with open(out_path, "w", encoding="utf-8") as f:
        # Smoketest banner
        if "smoketest" in metrics_path or "smoketest" in header.get("data_hash", ""):
            f.write("> ⚠️ **SYNTHETIC SMOKE-TEST DATA**\n\n")

        f.write("# Evaluation Report\n\n")
        f.write("## Metadata\n")
        for k, v in header.items():
            if isinstance(v, dict):
                f.write(f"- **{k}**:\n")
                for sub_k, sub_v in v.items():
                    f.write(f"  - {sub_k}: `{sub_v}`\n")
            else:
                f.write(f"- **{k}**: `{v}`\n")

        latencies = metrics.get("latency_ms", [])
        median_lat = statistics.median(latencies) / 1000 if latencies else 0
        p95_lat = sorted(latencies)[int(len(latencies)*0.95)] / 1000 if latencies else 0

        stmts = metrics.get("statements_total", 0)
        grounded = metrics.get("statements_grounded", 0)
        grounding_rate = (grounded / stmts * 100) if stmts else 100.0

        f.write("\n## Metrics vs Baseline\n")
        f.write("| Metric | System | Baseline | Delta |\n")
        f.write("|--------|--------|----------|-------|\n")

        ndcg = metrics.get("ndcg_5", 0)
        base_ndcg = metrics.get("baseline_ndcg_5", 0)
        f.write(f"| NDCG@5 | {ndcg:.2f} | {base_ndcg:.2f} | {ndcg - base_ndcg:+.2f} |\n")

        rec = metrics.get("recall_10", 0)
        base_rec = metrics.get("baseline_recall_10", 0)
        f.write(f"| Recall@10 | {rec:.2f} | {base_rec:.2f} | {rec - base_rec:+.2f} |\n")
        f.write(f"| Hard Constraints Violations | {metrics.get('hard_constraint_violations', 0)} | N/A | N/A |\n")
        f.write(f"| Groundedness | {grounding_rate:.1f}% | N/A | N/A |\n")
        f.write(f"| Median Latency | {median_lat:.1f}s | N/A | N/A |\n")
        f.write(f"| p95 Latency | {p95_lat:.1f}s | N/A | N/A |\n")

        f.write("\n## 10 Worst Queries\n")
        f.write("*(Per-query metrics not implemented in MVP)*\n")

    print(f"Wrote {out_path}")

if __name__ == "__main__":
    generate_report()
