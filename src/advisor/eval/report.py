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
            if k == "mode" and v == "replay":
                f.write(f"- **{k}**: `{v}` *(Note: 'replay' uses cached API calls, but ADVISOR_PROFILE=prod means un-cached calls hit live Groq)*\n")
            elif isinstance(v, dict):
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

        ndcg_val = metrics.get("ndcg_5", 0)
        base_ndcg = metrics.get("baseline_ndcg_5", 0)
        f.write(f"| NDCG@5 | {ndcg_val:.2f} | {base_ndcg:.2f} | {ndcg_val - base_ndcg:+.2f} |\n")

        rec = metrics.get("recall_10", 0)
        base_rec = metrics.get("baseline_recall_10", 0)
        f.write(f"| Recall@10 | {rec:.2f} | {base_rec:.2f} | {rec - base_rec:+.2f} |\n")
        f.write(f"| Hard Constraints Violations | {metrics.get('hard_constraint_violations', 0)} | N/A | N/A |\n")
        f.write(f"| Groundedness | {grounding_rate:.1f}% | N/A | N/A |\n")
        f.write(f"| Median Latency | {median_lat:.1f}s | N/A | N/A |\n")
        f.write(f"| p95 Latency | {p95_lat:.1f}s | N/A | N/A |\n")

        f.write("\n## 10 Worst Queries\n")
        try:
            import math
            def dcg(relevances, k=5):
                score = 0.0
                for i, rel in enumerate(relevances[:k]):
                    score += rel / math.log2(i + 2)
                return score
            def calc_ndcg(sys_ids, gold_rel, k=5):
                sys_rels = [gold_rel.get(pid, 0) for pid in sys_ids]
                ideal_rels = sorted(gold_rel.values(), reverse=True)
                idcg = dcg(ideal_rels, k)
                return dcg(sys_rels, k) / idcg if idcg > 0 else 0.0

            gold = {}
            with open("eval/data/gold.jsonl") as gf:
                for line in gf:
                    if line.strip():
                        j = json.loads(line)
                        gold[j["query_id"]] = j.get("relevance", {})
                        
            with open("eval/results/per_query.jsonl") as pqf:
                queries = []
                for line in pqf:
                    if line.strip():
                        q = json.loads(line)
                        g = gold.get(q["query_id"], {})
                        score = calc_ndcg(q.get("system_top10", []), g, 5)
                        q["sys_ndcg_5"] = score
                        queries.append(q)
                
                queries.sort(key=lambda x: (x["sys_ndcg_5"], x["query_id"]))
                f.write("| query_id | status | NDCG@5 |\n")
                f.write("|----------|--------|--------|\n")
                for q in queries[:10]:
                    f.write(f"| {q['query_id']} | {q.get('status', '')} | {q['sys_ndcg_5']:.2f} |\n")
        except Exception as e:
            f.write(f"*(Could not compute worst queries: {e})*\n")

    print(f"Wrote {out_path}")

if __name__ == "__main__":
    generate_report()
