"""
parse.py — Step 2 of the pipeline: read a dataset and standardize the molecules.

Input:  a CSV with at least 3 columns: a SMILES column, a label column, and a
        split column (values "train" / "test").
Output: a clean pandas DataFrame where every SMILES is CANONICAL (one standard
        spelling) and unparseable rows are dropped (and counted).

Why canonicalize? The SAME molecule can be written as different SMILES strings.
"CCO" and "OCC" are both ethanol. If you don't canonicalize, a duplicate hiding in
both train and test slips past you. Canonical form makes identical molecules look
identical so the duplicate check can catch them.

You'll fill in the TODOs on Day 1.
"""

import pandas as pd
from rdkit import Chem


def canonical_smiles(smiles: str) -> str | None:
    """Return the canonical SMILES for a molecule, or None if RDKit can't parse it."""
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol)


def load_dataset(
    csv_path: str,
    smiles_col: str = "smiles",
    label_col: str = "label",
    split_col: str = "split",
) -> pd.DataFrame:
    """
    Load a dataset CSV and return a clean DataFrame with columns:
        smiles_canonical, label, split
    Rows with unparseable SMILES are dropped. Prints how many were dropped.
    """
    df = pd.read_csv(csv_path)

    for col in (smiles_col, label_col, split_col):
        if col not in df.columns:
            raise ValueError(
                f"Column '{col}' not found. CSV has: {list(df.columns)}"
            )

    # 1. Canonicalize every SMILES so identical molecules look identical.
    df["smiles_canonical"] = df[smiles_col].apply(canonical_smiles)

    # 2. Count + report how many RDKit couldn't parse.
    n_bad = int(df["smiles_canonical"].isna().sum())
    if n_bad:
        print(f"[parse] dropped {n_bad} unparseable SMILES rows")

    # 3. Drop the unparseable rows.
    df = df.dropna(subset=["smiles_canonical"]).copy()

    # 4. Normalize label / split column names so the rest of the code is simple.
    df = df.rename(columns={label_col: "label", split_col: "split"})
    df["split"] = df["split"].astype(str).str.strip().str.lower()

    # 5. Sanity-check the split values.
    allowed = {"train", "test"}
    seen = set(df["split"].unique())
    unexpected = seen - allowed
    if unexpected:
        print(f"[parse] WARNING: unexpected split values {unexpected} — keeping only train/test")
        df = df[df["split"].isin(allowed)].copy()
    for needed in allowed:
        if needed not in seen:
            print(f"[parse] WARNING: no rows with split == '{needed}'")

    # 6. Return only the columns the pipeline relies on (keeps things predictable).
    return df[["smiles_canonical", "label", "split"]].reset_index(drop=True)


def split_frames(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convenience: return (train_df, test_df) based on the 'split' column."""
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    return train, test
