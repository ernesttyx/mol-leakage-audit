"""
sweep_benchmarks.py — run the auditor over every local benchmark dataset under BOTH
a random split (the naive method) and a scaffold split (the safer one), and print a
comparison table. The gap between the two baseline scores is the leakage signal:
if the dumb baseline scores high on RANDOM but drops on SCAFFOLD, the dataset leaks
under naive splitting -> any paper using a random split on it reports inflated numbers.

Honest scope: this measures the DATASET's leakiness under naive splitting. It does NOT
prove any specific paper used a random split — that's a manual read of the paper.
"""
import sys, traceback
import pandas as pd
sys.path.insert(0, ".")

from backend import adapt
from backend import report

DATASETS = [
    ("BACE",    "data/validation/bace_raw.csv",        None),
    ("BBBP",    "data/validation/bbbp_raw.csv",         None),
    ("ESOL",    "data/validation/esol_raw.csv",         "measured log solubility in mols per litre"),
    ("Lipo",    "data/validation/lipo_raw.csv",         None),
    ("Tox21",   "data/validation/tox21_raw.csv.gz",     None),
    ("ClinTox", "data/validation/clintox_raw.csv.gz",   None),
]

def run_one(name, path, label_col):
    rows = []
    raw = pd.read_csv(path)
    for method in ("random", "scaffold"):
        try:
            clean, notes = adapt.prepare(raw.copy(), label_col=label_col,
                                         make_split_method=method, test_frac=0.2, seed=42)
            res = report.audit(clean)
            c = res["checks"]
            rows.append({
                "dataset": name, "split": method,
                "label_type": notes["label_type"],
                "n": notes["n_kept"],
                "verdict": res["verdict"],
                "baseline_metric": c["baseline"]["metric_name"],
                "baseline_score": round(float(c["baseline"]["score"]), 3),
                "dup_frac": round(float(c["duplicates"]["fraction_leaked"]), 3),
                "sim>0.8": round(float(c["similarity"]["fraction_above_0_8"]), 3),
                "scaffold_shared": round(float(c["scaffold"]["fraction_shared"]), 3),
            })
        except Exception as e:
            rows.append({"dataset": name, "split": method, "verdict": f"ERROR: {e}"})
            traceback.print_exc()
    return rows

all_rows = []
for name, path, lab in DATASETS:
    all_rows.extend(run_one(name, path, lab))

df = pd.DataFrame(all_rows)
pd.set_option("display.width", 200, "display.max_columns", 30)
print("\n================ AUDIT SWEEP RESULTS ================\n")
print(df.to_string(index=False))
