"""
probe_real.py — run the auditor against many REAL public datasets, end to end.

This is the "does it survive contact with real data?" harness. Each dataset has a
different shape (different column names, missing splits, continuous labels, hundreds of
junk columns, sparse NaN labels). The adapter (backend/adapt.py) must standardize each
one, and the audit must produce a sane verdict — without hand-editing the files.

Run:  python -m scripts.probe_real
"""

import os
import pandas as pd
from rdkit import RDLogger

from backend.adapt import prepare
from backend.report import audit

RDLogger.DisableLog("rdApp.*")

V = "data/validation"

# (name, path, label_col override or None, gzip?)
DATASETS = [
    ("BACE (cls, has split=Model)", f"{V}/bace_raw.csv", "Class", False),
    ("BBBP (cls, no split)",        f"{V}/bbbp_raw.csv", "p_np", False),
    ("ESOL (regression, no split)", f"{V}/esol_raw.csv", "measured log solubility in mols per litre", False),
    ("Lipophilicity (reg, no split)", f"{V}/lipo_raw.csv", "exp", False),
    ("ClinTox (cls, pick CT_TOX)",  f"{V}/clintox_raw.csv.gz", "CT_TOX", True),
    ("Tox21 (cls, sparse NaN)",     f"{V}/tox21_raw.csv.gz", "NR-AR", True),
]


def main():
    rows = []
    for name, path, label_col, gz in DATASETS:
        if not os.path.exists(path):
            rows.append((name, "MISSING FILE", "", "", "", ""))
            continue
        df = pd.read_csv(path, compression="gzip" if gz else None)
        try:
            clean, notes = prepare(df, label_col=label_col, make_split_method="random")
            rep = audit(clean)
            b = rep["checks"]["baseline"]
            rows.append((
                name,
                rep["verdict"],
                notes["label_type"],
                f"{notes['n_kept']} ({notes['n_train']}tr/{notes['n_test']}te)",
                f"{b['metric_name']}={b['score']:.2f}",
                notes["split_source"][:42],
            ))
        except Exception as exc:  # noqa: BLE001
            rows.append((name, f"ERROR: {exc}", "", "", "", ""))

    hdr = ("dataset", "verdict", "label_type", "kept", "baseline", "split_source")
    widths = [max(len(str(r[i])) for r in (rows + [hdr])) for i in range(len(hdr))]
    line = lambda r: "  ".join(str(r[i]).ljust(widths[i]) for i in range(len(hdr)))
    print(line(hdr))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))


if __name__ == "__main__":
    main()
