import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

try:
    from google import genai
except ImportError:
    genai = None

try:
    from groq import Groq
except ImportError:
    Groq = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class ProbeTracker:
    def __init__(self, limits: dict):
        self.limits = limits
        self.calls = {"gemini": 0, "groq": 0}
        self.halt = {"gemini": threading.Event(), "groq": threading.Event()}
        self.lock = threading.Lock()

    def check_and_increment(self, provider: str) -> bool:
        with self.lock:
            if self.halt[provider].is_set():
                return False
            if self.calls[provider] >= self.limits.get(provider, 15):
                logger.warning(f"Hard maximum call count reached for {provider}. Halting.")
                self.halt[provider].set()
                return False
            self.calls[provider] += 1
            return True

    def trigger_halt(self, provider: str, reason: str):
        logger.error(f"{provider} halted: {reason}")
        self.halt[provider].set()

def probe_gemini(tracker: ProbeTracker, report: dict, limits: dict):
    if not genai or not os.getenv("GEMINI_API_KEY") or tracker.halt["gemini"].is_set():
        return

    client = genai.Client()
    logger.info("Listing Gemini models...")
    models = list(client.models.list())
    visible_models = [m.name for m in models if "gemini" in m.name]
    report["gemini"] = {"visible_models": visible_models}

    target = next((m for m in visible_models if "flash" in m), None)
    if target:
        target = target.replace("models/", "")
        success_count = 0
        def _call():
            if not tracker.check_and_increment("gemini"):
                return False
            try:
                client.models.generate_content(model=target, contents="Reply 'OK'")
                return True
            except Exception as e:
                if "429" in str(e).lower() or "quota" in str(e).lower():
                    tracker.trigger_halt("gemini", "Quota exhausted (429)!")
                return False

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_call) for _ in range(5)]
            for f in as_completed(futures):
                if f.result(): success_count += 1

        rpm = 15 if success_count >= 3 else 2
        limits[target] = {"RPM": rpm, "TPM": 1000000, "RPD": 1500}
        report["gemini"]["burst_test"] = f"{success_count}/5 successful"

def probe_groq(tracker: ProbeTracker, report: dict, limits: dict):
    if not Groq or not os.getenv("GROQ_API_KEY") or tracker.halt["groq"].is_set():
        return

    client = Groq()
    logger.info("Listing Groq models...")
    models = client.models.list()
    visible_models = [m.id for m in models.data]
    report["groq"] = {"visible_models": visible_models}

    target = next((m for m in visible_models if "llama" in m.lower()), None)
    if target:
        success_count = 0
        def _call():
            if not tracker.check_and_increment("groq"):
                return False
            try:
                client.chat.completions.create(model=target, messages=[{"role": "user", "content": "Reply 'OK'"}], max_tokens=10)
                return True
            except Exception as e:
                if "429" in str(e).lower() or "quota" in str(e).lower():
                    tracker.trigger_halt("groq", "Quota exhausted (429)!")
                return False

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_call) for _ in range(5)]
            for f in as_completed(futures):
                if f.result(): success_count += 1

        rpm = 30 if success_count == 5 else 10
        limits[target] = {"RPM": rpm, "TPM": 14400, "RPD": 14400}
        report["groq"]["burst_test"] = f"{success_count}/5 successful"

def main():
    report = {}
    limits = {}

    config_path = Path("configs/probe.yaml")
    probe_caps = {"gemini": 15, "groq": 15}
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
            probe_caps = cfg.get("max_calls_per_provider", probe_caps)

    tracker = ProbeTracker(probe_caps)

    logger.info("Starting model probe...")
    probe_gemini(tracker, report, limits)
    probe_groq(tracker, report, limits)

    configs_dir = Path("configs")
    configs_dir.mkdir(exist_ok=True)

    with open(configs_dir / "limits.yaml", "w") as f:
        yaml.dump(limits, f)

    with open("docs/probe_report.md", "w") as f:
        f.write("# Model Probe Report\n\n")
        f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Gemini\n")
        f.write(yaml.dump(report.get("gemini", {})))
        f.write("\n## Groq\n")
        f.write(yaml.dump(report.get("groq", {})))

    logger.info("Probe complete. Wrote configs/limits.yaml and docs/probe_report.md")

if __name__ == "__main__":
    main()
