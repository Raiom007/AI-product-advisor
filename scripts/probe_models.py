import os
import time
import yaml
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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

MAX_PROBE_CALLS = 15

def probe_gemini(report: dict, limits: dict):
    if not genai or not os.getenv("GEMINI_API_KEY"):
        logger.warning("Gemini SDK or API key not found. Skipping Gemini probe.")
        return
        
    client = genai.Client()
    logger.info("Listing Gemini models...")
    models = list(client.models.list())
    visible_models = [m.name for m in models if "gemini" in m.name]
    logger.info(f"Visible Gemini models: {visible_models}")
    
    report["gemini"] = {"visible_models": visible_models}
    
    # Simple burst test on flash
    target = next((m for m in visible_models if "flash" in m), None)
    if target:
        # Strip models/ prefix if present
        target = target.replace("models/", "")
        logger.info(f"Burst testing {target}...")
        
        success_count = 0
        def _call():
            try:
                resp = client.models.generate_content(
                    model=target,
                    contents="Reply 'OK'",
                )
                return True
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "quota" in err:
                    return False
                logger.error(f"Error calling Gemini: {e}")
                return False
                
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_call) for _ in range(5)]
            for f in as_completed(futures):
                if f.result():
                    success_count += 1
                    
        logger.info(f"Gemini burst test: {success_count}/5 succeeded.")
        # Estimate RPM based on burst success
        rpm = 15 if success_count >= 3 else 2
        
        limits[target] = {
            "RPM": rpm,
            "TPM": 1000000, # Default high TPM
            "RPD": 1500
        }
        report["gemini"]["burst_test"] = f"{success_count}/5 successful"

def probe_groq(report: dict, limits: dict):
    if not Groq or not os.getenv("GROQ_API_KEY"):
        logger.warning("Groq SDK or API key not found. Skipping Groq probe.")
        return
        
    client = Groq()
    logger.info("Listing Groq models...")
    models = client.models.list()
    visible_models = [m.id for m in models.data]
    logger.info(f"Visible Groq models: {visible_models}")
    
    report["groq"] = {"visible_models": visible_models}
    
    target = next((m for m in visible_models if "llama" in m.lower()), None)
    if target:
        logger.info(f"Burst testing {target}...")
        
        success_count = 0
        def _call():
            try:
                resp = client.chat.completions.create(
                    model=target,
                    messages=[{"role": "user", "content": "Reply 'OK'"}],
                    max_tokens=10
                )
                return True
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "quota" in err:
                    return False
                logger.error(f"Error calling Groq: {e}")
                return False
                
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_call) for _ in range(5)]
            for f in as_completed(futures):
                if f.result():
                    success_count += 1
                    
        logger.info(f"Groq burst test: {success_count}/5 succeeded.")
        rpm = 30 if success_count == 5 else 10
        
        limits[target] = {
            "RPM": rpm,
            "TPM": 14400,
            "RPD": 14400
        }
        report["groq"]["burst_test"] = f"{success_count}/5 successful"

def main():
    report = {}
    limits = {}
    
    logger.info("Starting model probe...")
    probe_gemini(report, limits)
    probe_groq(report, limits)
    
    # Save limits
    configs_dir = Path("configs")
    configs_dir.mkdir(exist_ok=True)
    
    with open(configs_dir / "limits.yaml", "w") as f:
        yaml.dump(limits, f)
        
    # Save report
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
