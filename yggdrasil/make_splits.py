import json
import math
import random
from pathlib import Path
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_JSON   = Path(__file__).parent.parent / "split_files" / "BraTS23.json"
OUTPUT_JSON  = Path(__file__).parent / "annotation_splits.json"
SPLIT_SIZE   = 60          # N: number of samples per annotator split
SPLIT_PREFIX = "BATCH"
RANDOM_SEED  = 42

TRAIN_REPEATS = 1          # how many splits each train sample appears in
VAL_REPEATS   = 1          # idem for val
TEST_REPEATS  = 3          # idem for test
# ──────────────────────────────────────────────────────────────────────────────


def patient_id(sample: str) -> str:
    """BraTS-GLI-00002-000 → BraTS-GLI-00002"""
    return "-".join(sample.split("-")[:-1])


def build_pool(data: dict) -> list[str]:
    pool = []
    repeats = {"train": TRAIN_REPEATS, "val": VAL_REPEATS, "test": TEST_REPEATS}
    for subset, factor in repeats.items():
        for sample in data[subset]:
            pool.extend([sample] * factor)
    return pool


def spread_pool(pool: list[str], rng: random.Random) -> list[str]:
    """Shuffle so same-patient copies are as far apart as possible."""
    by_patient = defaultdict(list)
    for s in pool:
        by_patient[patient_id(s)].append(s)

    # interleave patient groups (longest first → fewest clashes)
    groups = sorted(by_patient.values(), key=len, reverse=True)
    interleaved = []
    while any(groups):
        rng.shuffle(groups)
        for g in groups:
            if g:
                interleaved.append(g.pop())
        groups = [g for g in groups if g]
    return interleaved


def assign_splits(pool: list[str], n: int) -> list[list[str]]:
    num_splits = math.ceil(len(pool) / n)
    splits:   list[list[str]] = [[] for _ in range(num_splits)]
    patients: list[set[str]]  = [set() for _ in range(num_splits)]
    images:   list[set[str]]  = [set() for _ in range(num_splits)]

    unplaced = []
    for sample in pool:
        pid = patient_id(sample)
        placed = False

        # try: no duplicate image AND no same-patient
        for i in range(num_splits):
            if len(splits[i]) < n and sample not in images[i] and pid not in patients[i]:
                splits[i].append(sample)
                patients[i].add(pid)
                images[i].add(sample)
                placed = True
                break

        if not placed:
            # relax: allow duplicate image, still no same-patient
            for i in range(num_splits):
                if len(splits[i]) < n and pid not in patients[i]:
                    splits[i].append(sample)
                    patients[i].add(pid)
                    images[i].add(sample)
                    placed = True
                    break

        if not placed:
            unplaced.append(sample)

    # last resort: fill remaining space ignoring all constraints
    for sample in unplaced:
        for i in range(num_splits):
            if len(splits[i]) < n:
                splits[i].append(sample)
                break
        else:
            splits.append([sample])

    return splits


def main():
    rng = random.Random(RANDOM_SEED)

    with open(INPUT_JSON) as f:
        data = json.load(f)

    pool = build_pool(data)
    pool = spread_pool(pool, rng)

    splits = assign_splits(pool, SPLIT_SIZE)

    output = {
        f"{SPLIT_PREFIX}_{i+1:02d}": splits[i]
        for i in range(len(splits))
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    total = sum(len(v) for v in output.values())
    print(f"Created {len(output)} splits of up to {SPLIT_SIZE} samples each ({total} total assignments)")
    print(f"Output → {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
