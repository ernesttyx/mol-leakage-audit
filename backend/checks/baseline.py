"""
Check 4 — THE DUMB BASELINE.  ★ This is the heart of the whole project. ★

Every other check *measures similarity and infers* leakage. This one *proves* it by
construction. We build a deliberately brain-dead predictor:

    To predict a TEST molecule's label, find its nearest TRAINING neighbor (Tanimoto)
    and just COPY that neighbor's label. No learning. No parameters. A lookup table.

Then we score this dumb predictor with a normal metric (AUROC for yes/no labels).

Interpretation:
  - If the dumb lookup scores HIGH  -> the test set is gameable by pure memorization
                                       -> any "real" model's high score is suspect -> LEAKING.
  - If the dumb lookup scores LOW   -> memorization doesn't work here -> the split is
                                       making the model actually generalize -> healthier.

This is NOT a heuristic that can false-positive: the baseline really achieves that score.
You're not predicting leakage, you're demonstrating it. (This is exactly the
"trivial memorization-based baseline" the published LIT-PCBA audit used.)

Fill in on Day 2.
"""

import pandas as pd
from rdkit import DataStructs
from sklearn.metrics import roc_auc_score, accuracy_score, r2_score

from backend.featurize import fingerprints_for


def dumb_baseline(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """
    Returns a dict like:
        {
          "metric_name": "AUROC" or "accuracy",
          "score": <float>,                 # how well pure memorization does
          "message": "<plain-English summary>",
        }
    """
    train_fps = fingerprints_for(train["smiles_canonical"].tolist())
    test_fps = fingerprints_for(test["smiles_canonical"].tolist())
    train_labels = train["label"].tolist()
    test_labels = list(test["label"])

    predictions = []          # the copied nearest-neighbor label (hard prediction)
    nn_scores = []            # similarity of the nearest neighbor (soft score for AUROC)
    for test_fp in test_fps:
        if test_fp is None or not train_fps:
            predictions.append(train_labels[0] if train_labels else 0)
            nn_scores.append(0.0)
            continue
        sims = DataStructs.BulkTanimotoSimilarity(test_fp, train_fps)
        nearest_index = max(range(len(sims)), key=sims.__getitem__)
        predictions.append(train_labels[nearest_index])
        nn_scores.append(sims[nearest_index])

    # Decide the metric from the label type.
    #   binary (0/1)     -> AUROC  (chance = 0.50)
    #   continuous (reg) -> R^2    (chance = 0.00; the copied neighbor's value vs the truth)
    #   anything else    -> accuracy (fallback)
    numeric_labels = [float(x) for x in test_labels]
    unique_labels = set(numeric_labels)
    is_binary = unique_labels.issubset({0.0, 1.0}) and len(unique_labels) == 2
    is_continuous = len(unique_labels) > 10  # many distinct numeric values -> regression

    if is_binary:
        # Weight each copied label by how confident the lookup was (its NN similarity),
        # so the ROC curve reflects "similar neighbor -> trust the copied label more".
        soft = [
            (sim if pred == 1 else 1 - sim)
            for pred, sim in zip(predictions, nn_scores)
        ]
        score = float(roc_auc_score([int(x) for x in numeric_labels], soft))
        metric_name = "AUROC"
    elif is_continuous:
        # NN-copy regression: predict each test value by its nearest neighbor's value,
        # score with R^2. High R^2 = the test values are recoverable by memorization.
        score = float(r2_score(numeric_labels, [float(p) for p in predictions]))
        metric_name = "R2"
    else:
        score = float(accuracy_score(test_labels, predictions))
        metric_name = "accuracy"

    chance = {"AUROC": "0.50", "R2": "0.00", "accuracy": "baseline-rate"}[metric_name]
    message = (
        f"A no-learning nearest-neighbor lookup scores {score:.2f} {metric_name} on your "
        f"test set (chance = {chance}). If a real model barely beats this, its score is "
        f"mostly memorization."
    )

    return {
        "metric_name": metric_name,
        "score": score,
        "message": message,
    }
