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
from sklearn.metrics import roc_auc_score, r2_score

from backend.featurize import fingerprints_for


def label_metric(all_labels: list[float]) -> str:
    """The single source of truth for which metric the baseline reports.

    Must stay identical to adapt.detect_label_type: 'AUROC' iff the labels (across the
    WHOLE dataset, not just the test split) are exactly {0,1}; otherwise 'R2'. Computing
    this over all labels — not just the test split — keeps the verdict stable even when a
    test split happens to hold a single class, and guarantees report.py's threshold bands
    always match the metric that was actually used.
    """
    uniq = set(all_labels)
    if uniq.issubset({0.0, 1.0}) and len(uniq) == 2:
        return "AUROC"
    return "R2"


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

    # Decide the metric from the label type, using the SAME rule as adapt.detect_label_type
    # (computed over the whole dataset so a single-class test split can't flip it):
    #   binary (exactly {0,1}) -> AUROC  (chance = 0.50)
    #   everything else        -> R^2    (chance = 0.00; copied neighbor's value vs truth)
    numeric_labels = [float(x) for x in test_labels]
    metric_name = label_metric([float(x) for x in train_labels] + numeric_labels)

    if metric_name == "AUROC":
        y_true = [int(x) for x in numeric_labels]
        if len(set(y_true)) < 2:
            # AUROC is undefined when the test split holds a single class. Report NaN
            # rather than crash; the verdict logic treats NaN as "no signal" (every
            # comparison is False), so this can never produce a spurious LEAKING flag.
            score = float("nan")
            message = (
                "The test split contains only one class, so a memorization AUROC is "
                "undefined — this check is inconclusive for this split."
            )
            return {"metric_name": metric_name, "score": score, "message": message}
        # Weight each copied label by how confident the lookup was (its NN similarity),
        # so the ROC curve reflects "similar neighbor -> trust the copied label more".
        soft = [
            (sim if pred == 1 else 1 - sim)
            for pred, sim in zip(predictions, nn_scores)
        ]
        score = float(roc_auc_score(y_true, soft))
    else:
        # NN-copy regression: predict each test value by its nearest neighbor's value,
        # score with R^2. High R^2 = the test values are recoverable by memorization.
        score = float(r2_score(numeric_labels, [float(p) for p in predictions]))

    chance = {"AUROC": "0.50", "R2": "0.00"}[metric_name]
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
