"""Lightweight compatibility loader for the audited API runner."""
import json
def load_jsonl(path):
    with open(path,encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
