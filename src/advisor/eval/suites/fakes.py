import json

from advisor.core.config import load_config
from advisor.core.registries import suite
from advisor.reviews.fake_detector import run_detector


@suite("fakes")
def run_fakes_suite(queries: list[dict]=None, gold: list[dict]=None, mode: str="replay", data: list=None) -> dict:
    """Evaluate fake detector against seeded TEST split."""
    if not data and not queries:
        raise ValueError("FAIL LOUDLY: no data")
    # Read truth file
    truth_file = "eval/data/seeded_fakes.jsonl"
    truths = []
    with open(truth_file) as f:
        for line in f:
            if line.strip():
                truths.append(json.loads(line))

    test_split = {t["review_id"] for t in truths if t["split"] == "test"}
    all_seeded_fakes = {t["review_id"] for t in truths}

    cfg = load_config()
    # Run detector on advisor_fakes.db
    flags = run_detector("data/advisor_fakes.db", cfg.get("fakes", {}))

    flagged_ids = {f.review_id for f in flags if f.action != "keep"}

    # We only calculate precision/recall on the test split seeded fakes + non-seeded reviews
    # Wait, precision = True Positives / (True Positives + False Positives)
    # A true positive is a flagged review that is in test_split.
    # A false positive is a flagged review that is NOT in all_seeded_fakes (it's a real review that got flagged).
    # We ignore dev split fakes for both precision and recall.

    tp = 0
    fp = 0
    for fid in flagged_ids:
        if fid in test_split:
            tp += 1
        elif fid not in all_seeded_fakes:
            fp += 1

    fn = len(test_split) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "total_test_fakes": len(test_split),
        "total_flagged": len(flagged_ids),
        "false_positives": fp
    }
