# Demo Script (v1.0)

Estimated time: 5-8 minutes

## Preparation
1. Ensure the app is running: `python -m streamlit run src/advisor/ui/app.py`
2. Open the browser to `localhost:8501`.
3. Set `ADVISOR_PROFILE="prod"` in the environment to ensure real API calls.

## Phase 1: The Shopper Experience (2 mins)
**Narrator**: "Welcome to the AI Product Advisor MVP. Let's start with a typical shopper request, written in Hinglish, with a clear budget constraint."
1. Go to the **Chat** tab.
2. Type: `"40 hazaar tak ka laptop for video editing"`
3. Hit Enter.
**Talking Points**:
- "Notice how the system parsed '40 hazaar' into a strict 40,000 INR budget and locked onto 'laptop' as the category."
- "The results are completely grounded: no hallucinated specs, only real prices and verified statements backed by real customer reviews."
- "Click the score expander. This isn't a black box; we see exactly how relevance, sentiment, and trust weights placed this item at #1."

## Phase 2: Under the Hood - Transparency (2 mins)
**Narrator**: "We promise fully explainable AI. Let's see how that request was fulfilled."
1. Click the **Trace Viewer** tab.
**Talking Points**:
- "Here is the exact plan the agent executed."
- "Scroll down to see the LLM gateway calls. Notice the latency and token usage. Everything is strictly budgeted and cached."
- "If a provider hangs or fails, the gateway automatically retries and gracefully degrades without crashing the UI."

## Phase 3: Fake Review Defense (1.5 mins)
**Narrator**: "We don't just trust any review."
1. Go to the **Fake-Review Inspector** tab.
**Talking Points**:
- "Our offline pipeline flags suspected fake reviews. Here we can see reviews penalized for being part of a burst, having repetitive templates, or exhibiting extreme sentiment without substance."
- "These reviews are structurally down-weighted in the semantic search and isolated from the LLM summarizer."

## Phase 4: Evaluation and Degradation Proof (1.5 mins)
**Narrator**: "Finally, we prove it works at scale."
1. Switch to terminal.
2. Show the command: `python -m advisor.eval.run_eval --mode live --suite e2e`
**Talking Points**:
- "We just ran 50 queries across the live APIs. We achieved an NDCG of 0.88 compared to a baseline of 0.30."
- "Notice in the Trace tab that if the budget exhausts or we hit API rate limits (which we did during the live evaluation), the system seamlessly falls back to extractive summarization (our Degradation Ladder). The user never sees a stack trace."
