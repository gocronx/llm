"""Split raw samples into train/valid/test and convert to MLX chat format."""

import json
import random
from pathlib import Path

random.seed(42)
DATA_DIR = Path(__file__).parent / "data"

SYSTEM_PROMPT = (
    "You are a Python engineer who writes code using the internal Saber framework. "
    "Always import from saber.web / saber.db / saber.errors. "
    "Routes use @handler('METHOD', '/path'). "
    "Database queries use Q.from_(table).where(field, op, value).fetch(). "
    "Handlers must return a tuple (Response, headers_dict)."
)


def to_chat(sample):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sample["instruction"]},
            {"role": "assistant", "content": sample["code"]},
        ]
    }


def stratified_split(samples, valid_ratio=0.1, test_ratio=0.1):
    by_kind = {}
    for s in samples:
        by_kind.setdefault(s["kind"], []).append(s)
    train, valid, test = [], [], []
    for group in by_kind.values():
        random.shuffle(group)
        n = len(group)
        n_test = max(1, int(n * test_ratio))
        n_valid = max(1, int(n * valid_ratio))
        train.extend(group[: n - n_test - n_valid])
        valid.extend(group[n - n_test - n_valid : n - n_test])
        test.extend(group[n - n_test :])
    for ds in (train, valid, test):
        random.shuffle(ds)
    return train, valid, test


def main():
    raw = DATA_DIR / "raw_samples.jsonl"
    if not raw.exists():
        raise SystemExit(f"missing {raw}; run 01_design_dataset.py first")

    with raw.open(encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    train, valid, test = stratified_split(samples)

    for name, ds in [("train", train), ("valid", valid)]:
        with (DATA_DIR / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for s in ds:
                f.write(json.dumps(to_chat(s), ensure_ascii=False) + "\n")

    with (DATA_DIR / "test.jsonl").open("w", encoding="utf-8") as f:
        for s in test:
            record = {
                "id": s["id"],
                "kind": s["kind"],
                "instruction": s["instruction"],
                "expected_code": s["code"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"train={len(train)}  valid={len(valid)}  test={len(test)}")
    if len(train) < 50:
        print("warning: <50 training samples, expect underfitting")


if __name__ == "__main__":
    main()
