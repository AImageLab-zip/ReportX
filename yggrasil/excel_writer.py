import json
import sys
from pathlib import Path

import pandas as pd


def split_sort_key(key: str):
    prefix, sep, suffix = key.rpartition("_")
    if sep and suffix.isdigit():
        return prefix, int(suffix)
    return key, 0


def save_splits_to_excel(path: str, splits: dict, annotators: dict):
    ordered = sorted([k for k in splits if k != "REMAINING"], key=split_sort_key)
    if "REMAINING" in splits:
        ordered.append("REMAINING")

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for key in ordered:
            samples = splits[key]
            ann_name = annotators.get(key, "")
            sheet_name = key[:31]
            df = pd.DataFrame({
                "#": list(range(1, len(samples) + 1)),
                "Sample ID": samples,
            })

            df.to_excel(writer, sheet_name=sheet_name, startrow=2, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet["A1"] = f"Annotator: {ann_name}"


def save_splits_to_json(path: str, splits: dict):
    json_path = Path(path).with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(splits, f, indent=2)


def main():
    payload = json.loads(sys.stdin.read())
    save_splits_to_excel(payload["path"], payload["splits"], payload["annotators"])
    save_splits_to_json(payload["path"], payload["splits"])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
