"""
adapt.py — turn a REAL-WORLD molecular CSV into the clean shape the auditor needs.

Toy files are already `smiles,label,split`. Real public datasets are not:
  * the SMILES column may be called `mol`, `smi`, ...           -> auto-detect
  * the label column varies (`Class`, `p_np`, `exp`, ...)       -> auto-detect / override
  * labels may be CONTINUOUS (regression), not 0/1              -> detect type
  * there may be NO split column at all (BBBP, ESOL, Lipo, ...) -> create one (and SAY SO)
  * the split may be `Train/Test/Valid` instead of `train/test` -> normalize
  * there may be hundreds of junk descriptor columns (BACE: 595)-> ignore them
  * labels may be missing (NaN) for some rows (Tox21)          -> drop those rows

`prepare()` returns (clean_df, notes). `notes` is an HONEST record of every decision the
adapter made, so nothing is silent — the user can see exactly what was audited.
"""

from __future__ import annotations

import pandas as pd
from rdkit import Chem, RDLogger

from backend.checks.scaffold import scaffold_of

# Real datasets contain some malformed SMILES (e.g. BBBP has ~11). We drop those rows
# and count them in notes; silence RDKit's per-row warnings so they don't flood logs.
RDLogger.DisableLog("rdApp.*")

_SMILES_NAMES = ("smiles", "mol", "smi", "canonical_smiles", "structure")
_SPLIT_NAMES = ("split", "model", "set", "subset", "group")


def sniff_smiles_column(df: pd.DataFrame) -> str | None:
    """Find the SMILES column by name first, then by 'looks parseable' as a fallback."""
    for c in df.columns:
        if c.strip().lower() in _SMILES_NAMES:
            return c
    # fallback: the object column whose first non-null value parses as a molecule
    for c in df.columns:
        if df[c].dtype == object:
            sample = df[c].dropna().head(20)
            if len(sample) and (sample.apply(lambda s: Chem.MolFromSmiles(str(s)) is not None).mean() > 0.7):
                return c
    return None


def sniff_split_column(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if c.strip().lower() in _SPLIT_NAMES:
            # must actually contain split-like values
            vals = {str(v).strip().lower() for v in df[c].dropna().unique()}
            if vals & {"train", "test", "valid", "validation", "val"}:
                return c
    return None


def sniff_label_column(df: pd.DataFrame, smiles_col: str, split_col: str | None) -> str | None:
    """Pick a label column when the user didn't name one. Prefer obvious names, else the
    first numeric column that isn't the SMILES/split/id column. Returns None if unsure."""
    skip = {smiles_col}
    if split_col:
        skip.add(split_col)
    obvious = ("label", "class", "target", "y", "activity", "p_np", "active", "outcome")
    for c in df.columns:
        if c in skip:
            continue
        if c.strip().lower() in obvious:
            return c
    # else first numeric, non-id column
    for c in df.columns:
        if c in skip:
            continue
        if c.strip().lower() in ("id", "cid", "num", "name", "compound id", "cmpd_chemblid"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            return c
    return None


def detect_label_type(series: pd.Series) -> str:
    """'binary' if values are essentially {0,1}; else 'continuous'."""
    vals = pd.to_numeric(series, errors="coerce").dropna()
    uniq = set(vals.unique())
    if uniq.issubset({0, 1}) and len(uniq) <= 2:
        return "binary"
    # small number of integer classes -> still treat as binary-ish only if exactly 2
    if len(uniq) == 2:
        return "binary"
    return "continuous"


def normalize_split(series: pd.Series) -> pd.Series:
    """Map any split labelling onto {train, test}. Valid/validation/val fold into TRAIN
    (the audit only cares about test-vs-everything-the-model-could-learn-from)."""
    s = series.astype(str).str.strip().str.lower()
    s = s.replace({"validation": "train", "valid": "train", "val": "train",
                   "training": "train", "testing": "test"})
    return s


def make_split(df: pd.DataFrame, method: str, test_frac: float, seed: int) -> pd.Series:
    """Create a split when the file has none. 'random' = the naive default most people
    use (and the one that leaks); 'scaffold' = the safer one."""
    if method == "scaffold":
        scaf = df["smiles_canonical"].apply(scaffold_of)
        groups = sorted(df.groupby(scaf, dropna=False).groups.items(),
                        key=lambda kv: len(kv[1]), reverse=True)
        target, n_test, assign = test_frac * len(df), 0, {}
        for _g, idx in groups:
            to_test = n_test < target
            for i in idx:
                assign[i] = "test" if to_test else "train"
            if to_test:
                n_test += len(idx)
        return df.index.map(assign)
    # random
    out = pd.Series("train", index=df.index)
    test_idx = df.sample(frac=test_frac, random_state=seed).index
    out.loc[test_idx] = "test"
    return out


def prepare(
    df: pd.DataFrame,
    smiles_col: str | None = None,
    label_col: str | None = None,
    split_col: str | None = None,
    make_split_method: str = "random",
    test_frac: float = 0.2,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict]:
    """Standardize any molecular CSV to columns [smiles_canonical, label, split].

    Returns (clean_df, notes). `notes` records every decision so nothing is hidden.
    `notes['label_type']` is 'binary' or 'continuous' and drives the baseline metric.
    """
    notes: dict = {"n_input": int(len(df))}

    # 1. SMILES column
    smiles_col = smiles_col or sniff_smiles_column(df)
    if smiles_col is None or smiles_col not in df.columns:
        raise ValueError("Could not find a SMILES column. Pass smiles_col explicitly.")
    notes["smiles_col"] = smiles_col

    # 2. split column (detect if not given)
    split_col = split_col or sniff_split_column(df)

    # 3. label column
    label_col = label_col or sniff_label_column(df, smiles_col, split_col)
    if label_col is None or label_col not in df.columns:
        raise ValueError("Could not find a label column. Pass label_col explicitly "
                         f"(columns: {list(df.columns)[:20]}).")
    notes["label_col"] = label_col

    work = pd.DataFrame({
        "smiles_canonical": df[smiles_col].apply(
            lambda s: Chem.MolToSmiles(Chem.MolFromSmiles(str(s))) if Chem.MolFromSmiles(str(s)) else None
        ),
        "label_raw": df[label_col],
    })

    # 4. drop unparseable SMILES and missing labels
    n_bad_smiles = int(work["smiles_canonical"].isna().sum())
    work = work.dropna(subset=["smiles_canonical"])
    n_bad_label = int(work["label_raw"].isna().sum())
    work = work.dropna(subset=["label_raw"])
    notes["dropped_unparseable_smiles"] = n_bad_smiles
    notes["dropped_missing_label"] = n_bad_label

    # 5. label type + coercion
    label_type = detect_label_type(work["label_raw"])
    notes["label_type"] = label_type
    if label_type == "binary":
        work["label"] = pd.to_numeric(work["label_raw"], errors="coerce").astype(int)
    else:
        work["label"] = pd.to_numeric(work["label_raw"], errors="coerce")

    # 6. split: use provided (normalized) or create one
    if split_col and split_col in df.columns:
        sp = normalize_split(df[split_col]).reindex(work.index)
        sp = sp.where(sp.isin(["train", "test"]))  # anything weird -> NaN -> handled below
        if sp.isna().any():
            # rows with no usable split label: drop them (rare)
            keep = sp.notna()
            work, sp = work[keep], sp[keep]
        work["split"] = sp.values
        notes["split_source"] = f"provided column '{split_col}' (valid folded into train)"
    else:
        work = work.reset_index(drop=True)
        work["split"] = make_split(work, make_split_method, test_frac, seed).values
        notes["split_source"] = (
            f"NO split column found -> created a {make_split_method.upper()} "
            f"{int((1-test_frac)*100)}/{int(test_frac*100)} split (seed {seed}). "
            "THIS is the split being audited."
        )

    work = work[["smiles_canonical", "label", "split"]].reset_index(drop=True)
    notes["n_kept"] = int(len(work))
    notes["n_train"] = int((work["split"] == "train").sum())
    notes["n_test"] = int((work["split"] == "test").sum())
    return work, notes
