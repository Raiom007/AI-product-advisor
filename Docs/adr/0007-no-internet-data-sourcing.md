# ADR 0007: Strict Adherence to Data Confidentiality Constraints

## Context
The user requested building a script to fetch the McAuley Amazon Reviews 2023 "Electronics" dataset from the internet using the Hugging Face `datasets` library to swap the retrieval index to "real data." 

However, `AGENTS.md` and `ARCHITECTURE.md` (§14 SOW Data Confidentiality) mandate a strict, overriding constraint:
> "Do not source extra product or review data from the internet."

The current files inside `data/raw/` (`products.csv`, `reviews.csv`) contain synthetic dev-fixture data matching the size requirements (~20k products, ~34k reviews). Fetching the McAuley dataset directly from the internet via `datasets` violates the confidentiality guardrails.

## Decision
We will **not** build or run a script that downloads the McAuley Amazon Reviews 2023 dataset from the internet. 

## Consequences
- The retrieval index will continue to use the current local data provided in `data/raw/` (or `data/dev_fixtures/`) unless the real data is provided out-of-band by the client directly into `data/raw/` without agent interaction over the internet.
- Tasks involving writing/labelling the 50 gold queries against the "real index" will be paused until the real dataset is safely supplied into the workspace in accordance with SOW §14.
