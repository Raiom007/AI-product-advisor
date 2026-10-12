import datetime
import json
from pathlib import Path

# Ensure signals are registered
from advisor.core.registries import fake_signals
from advisor.core.schemas import ReviewFlag
from advisor.store.sqlite_store import open_db


def run_detector(db_path: str, fakes_config: dict) -> list[ReviewFlag]:
    """Run all registered fake signals and combine them into ReviewFlags."""
    conn = open_db(Path(db_path))

    # Fetch all reviews with product info
    query = """
        SELECT r.*, p.name as product_name, p.description as product_description 
        FROM reviews r 
        LEFT JOIN products p ON r.product_id = p.product_id
    """
    rows = conn.execute(query).fetchall()
    reviews = [dict(r) for r in rows]

    weights = fakes_config.get("weights", {})
    thresholds = fakes_config.get("thresholds", {})
    tau_high = thresholds.get("tau_high", 0.70)
    tau_low = thresholds.get("tau_low", 0.40)

    high_conf = thresholds.get("high_confidence", {})

    # Run each signal
    signal_results = {}
    for sig_name in fake_signals.all_names():
        if sig_name not in weights:
            continue
        sig_fn = fake_signals.get(sig_name)
        if sig_fn:
            signal_results[sig_name] = sig_fn(reviews, thresholds)

    flags = []

    for r in reviews:
        rid = r["review_id"]
        total_score = 0.0
        signals = {}
        reasons = []

        single_signal_triggered = False

        for sig_name, w in weights.items():
            if sig_name in signal_results:
                s = signal_results[sig_name].get(rid, 0.0)
                signals[sig_name] = s
                total_score += w * s

                # High-confidence single path
                hc_thresh = high_conf.get(sig_name, 2.0)
                if s >= hc_thresh:
                    single_signal_triggered = True
                    reasons.append(f"High-confidence {sig_name} ({s:.2f} >= {hc_thresh})")

                elif s > 0.5:
                    reasons.append(f"High {sig_name} signal")

        action = "keep"
        if single_signal_triggered or total_score > tau_high:
            action = "exclude"
        elif total_score > tau_low:
            action = "downweight"

        if action != "keep":
            flag = ReviewFlag(
                review_id=rid,
                score=total_score if not single_signal_triggered else max(total_score, 1.0),
                signals=signals,
                reasons=reasons,
                action=action
            )
            flags.append(flag)

    conn.close()
    return flags

def save_flags(db_path: str, flags: list[ReviewFlag]):
    """Save the ReviewFlags to the SQLite DB."""
    conn = open_db(Path(db_path))

    # Clear existing
    conn.execute("DELETE FROM review_flags")

    now = datetime.datetime.utcnow().isoformat()
    for flag in flags:
        conn.execute(
            """INSERT INTO review_flags (review_id, score, signals, reasons, action, flagged_at) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                flag.review_id,
                flag.score,
                json.dumps(flag.signals),
                json.dumps(flag.reasons),
                flag.action,
                now
            )
        )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Pre-load features so they register
    from advisor.core.config import load_config
    cfg = load_config()
    flags = run_detector("data/advisor.db", cfg.get("fakes", {}))
    print(f"Generated {len(flags)} flags")
    save_flags("data/advisor.db", flags)
