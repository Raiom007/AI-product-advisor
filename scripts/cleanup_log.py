import json
from pathlib import Path


def run():
    path = Path('data/processed/cleaning_log.jsonl')
    lines = path.read_text(encoding="utf-8").strip().split("\n")

    last_run = []
    for line in reversed(lines):
        if not line.strip(): continue
        last_run.append(line)
        if json.loads(line)['rule'] == 'products.loaded':
            break

    path.write_text("\n".join(reversed(last_run)) + "\n", encoding="utf-8")

    from advisor.ingest.__main__ import _write_data_cleaning_md
    _write_data_cleaning_md(path, Path('docs/data_cleaning.md'))

if __name__ == "__main__":
    run()
