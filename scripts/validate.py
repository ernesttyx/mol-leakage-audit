"""
validate.py — prove the auditor itself is correct.

Reproducible validation: run the tool on inputs whose leakage status is already
known, and show the verdicts agree.

The centerpiece is a CONTROLLED SAME-DATA experiment on a real public dataset
(MoleculeNet BACE, 1513 molecules, binary label):

  * RANDOM split   — molecular random splits are KNOWN to leak: analog series get
                     scattered across train/test, so a memorization baseline scores
                     high. (This is the published finding behind LIT-PCBA / DataSAIL.)
  * SCAFFOLD split — the SAME molecules, re-split so no scaffold spans the boundary.
                     Leakage should drop sharply.

Only the split changes between those two rows, so any difference in verdict is
attributable to the split alone — the cleanest possible internal-validity test.

Run:  python -m scripts.validate
"""

import os
import pandas as pd
from rdkit import Chem, RDLogger

from backend.report import audit
from backend.checks.scaffold import scaffold_of

RDLogger.DisableLog("rdApp.*")  # quiet RDKit parse warnings during the sweep

VALID_DIR = os.path.join("data", "validation")
BACE_RAW = os.path.join(VALID_DIR, "bace_raw.csv")


def _canon(s):
    m = Chem.MolFromSmiles(s) if isinstance(s, str) else None
    return Chem.MolToSmiles(m) if m else None


def load_bace() -> pd.DataFrame:
    """Real public dataset: SMILES in 'mol', binary label in 'Class'."""
    df = pd.read_csv(BACE_RAW)
    out = pd.DataFrame({"smiles": df["mol"], "label": df["Class"].astype(int)})
    out["smiles_canonical"] = out["smiles"].apply(_canon)
    return out.dropna(subset=["smiles_canonical"]).reset_index(drop=True)


def random_split(df: pd.DataFrame, test_frac=0.2, seed=42) -> pd.DataFrame:
    out = df.copy()
    test_idx = out.sample(frac=test_frac, random_state=seed).index
    out["split"] = "train"
    out.loc[test_idx, "split"] = "test"
    return out


def scaffold_split(df: pd.DataFrame, test_frac=0.2) -> pd.DataFrame:
    """Whole scaffold groups go entirely to train OR test, never both."""
    out = df.copy()
    out["_scaf"] = out["smiles_canonical"].apply(scaffold_of)
    groups = sorted(out.groupby("_scaf", dropna=False).groups.items(),
                    key=lambda kv: len(kv[1]), reverse=True)
    target = test_frac * len(out)
    n_test, assign = 0, {}
    for _scaf, idx in groups:
        to_test = n_test < target
        for i in idx:
            assign[i] = "test" if to_test else "train"
        if to_test:
            n_test += len(idx)
    out["split"] = out.index.map(assign)
    return out.drop(columns="_scaf")


def row(name, expected, df):
    r = audit(df)
    c = r["checks"]
    return {
        "dataset": name,
        "expected": expected,
        "verdict": r["verdict"],
        "dup_%": round(c["duplicates"]["fraction_leaked"] * 100, 1),
        "nn>0.8_%": round(c["similarity"]["fraction_above_0_8"] * 100, 1),
        "scaf_%": round(c["scaffold"]["fraction_shared"] * 100, 1),
        "baseline": round(c["baseline"]["score"], 3),
    }


def main():
    rows = []

    # Hand-made controls (status known by construction).
    for fname, name, exp in [
        ("toy_leaky.csv", "toy_leaky (hand-made)", "LEAKING"),
        ("toy_clean.csv", "toy_clean (hand-made)", "CLEAN"),
    ]:
        from backend.parse import load_dataset
        rows.append(row(name, exp, load_dataset(os.path.join("data", "examples", fname))))

    # Real dataset, controlled same-data experiment.
    bace = load_bace()
    rows.append(row("BACE random split", "LEAKING/SUSPECT", random_split(bace)))
    rows.append(row("BACE scaffold split", "CLEANER", scaffold_split(bace)))

    # Print a markdown table.
    cols = ["dataset", "expected", "verdict", "dup_%", "nn>0.8_%", "scaf_%", "baseline"]
    print("| " + " | ".join(cols) + " |")
    print("|" + "|".join("---" for _ in cols) + "|")
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")

    return rows


if __name__ == "__main__":
    main()
