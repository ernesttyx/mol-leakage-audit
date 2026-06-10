"""
Check 1 — NEAR-DUPLICATES.

The simplest, most damning leak: the *exact same molecule* sitting in both the
training set and the test set. After canonicalization (parse.py), identical molecules
have identical SMILES strings, so this is just a set-overlap.

Returns: how many test molecules are exact duplicates of a training molecule.

Fill in on Day 1.
"""

import pandas as pd


def check_duplicates(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """
    Find molecules that appear in BOTH train and test (by canonical SMILES).

    Returns a dict like:
        {
          "n_test": <int>,
          "n_leaked": <int>,                 # test molecules also present in train
          "fraction_leaked": <float 0..1>,
          "message": "<plain-English summary>",
        }
    """
    train_set = set(train["smiles_canonical"])
    leaked = [s for s in test["smiles_canonical"] if s in train_set]

    n_test = int(len(test))
    n_leaked = int(len(leaked))
    fraction_leaked = (n_leaked / n_test) if n_test else 0.0
    pct = round(fraction_leaked * 100, 1)

    message = (
        f"{n_leaked} of {n_test} test molecules ({pct}%) are exact duplicates "
        f"of a training molecule."
    )

    return {
        "n_test": n_test,
        "n_leaked": n_leaked,
        "fraction_leaked": fraction_leaked,
        "message": message,
    }
