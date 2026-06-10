"""
Check 2 — NEAREST-NEIGHBOR SIMILARITY.

For every TEST molecule, find its most-similar TRAINING molecule (highest Tanimoto).
If lots of test molecules have a near-identical twin in training, the "held-out" test
set isn't really held out — it's a slightly-reworded copy of the training set.

The output distribution of these max-similarities is also what you'll plot in the UI:
a wall of values near 1.0 = leaking; a spread toward 0 = genuinely novel test set.

Fill in on Day 2.
"""

import pandas as pd
from rdkit import DataStructs

from backend.featurize import fingerprints_for


def nearest_neighbor_similarities(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """
    Returns a dict like:
        {
          "similarities": [<float>, ...],    # one max-similarity per test molecule
          "mean": <float>,
          "fraction_above_0_8": <float>,     # how many test mols have a >0.8 train twin
          "message": "<plain-English summary>",
        }
    """
    train_fps = fingerprints_for(train["smiles_canonical"].tolist())
    test_fps = fingerprints_for(test["smiles_canonical"].tolist())

    similarities = []
    for test_fp in test_fps:
        if test_fp is None or not train_fps:
            continue
        sims = DataStructs.BulkTanimotoSimilarity(test_fp, train_fps)
        similarities.append(max(sims) if sims else 0.0)

    n = len(similarities)
    mean = (sum(similarities) / n) if n else 0.0
    n_above = sum(1 for s in similarities if s > 0.8)
    fraction_above_0_8 = (n_above / n) if n else 0.0
    pct = round(fraction_above_0_8 * 100, 1)

    message = (
        f"{pct}% of test molecules have a training neighbor more similar than 0.8 "
        f"(mean nearest-neighbor similarity = {mean:.2f})."
    )

    return {
        "similarities": similarities,
        "mean": mean,
        "fraction_above_0_8": fraction_above_0_8,
        "message": message,
    }
