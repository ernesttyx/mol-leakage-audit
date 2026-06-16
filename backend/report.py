"""
report.py — Step 6: run all 4 checks and combine them into ONE report + a verdict.

This is the function the API and the command line both call. Keep the verdict logic
simple and HONEST — remember the tool is a smoke detector, not a certificate.

Fill in on Day 3.
"""

import pandas as pd

from backend.parse import split_frames
from backend.checks.duplicates import check_duplicates
from backend.checks.scaffold import check_scaffold_overlap
from backend.checks.similarity import nearest_neighbor_similarities
from backend.checks.baseline import dumb_baseline


# All tunable thresholds live HERE so they're easy to find + adjust on Day 6.
THRESHOLDS = {
    "dup_leaking": 0.05,        # >5% exact duplicates -> leaking
    "sim_leaking": 0.50,        # >50% of test mols have a >0.8 train twin -> suspect
    "scaffold_suspect": 0.50,   # >50% shared scaffolds -> at least suspect
    # Baseline thresholds depend on the metric (AUROC chance=0.5, R2 chance=0.0).
    "baseline_leaking": 0.85,   # AUROC: memorization scores this high -> leaking
    "baseline_clean": 0.65,     # AUROC: memorization near chance -> healthy
    "r2_leaking": 0.70,         # R2: neighbor-copy explains most variance -> leaking
    "r2_clean": 0.40,           # R2: little recoverable by memorization -> healthy
}

# Below this many records in either split, the fraction-based thresholds above are
# statistically shaky (one duplicate in a 10-row test set is already 10%). We still
# report the verdict, but flag it as low-confidence so a tiny demo CSV can't be read
# as a hard claim. (Matches the spec's "warn if a split < 50 records".)
MIN_RELIABLE_SPLIT = 50


def _baseline_bands(metric_name: str) -> tuple[float, float]:
    """(leaking_above, clean_below) for the baseline score, per metric."""
    if metric_name == "R2":
        return THRESHOLDS["r2_leaking"], THRESHOLDS["r2_clean"]
    return THRESHOLDS["baseline_leaking"], THRESHOLDS["baseline_clean"]


def audit(df: pd.DataFrame) -> dict:
    """
    Run the full audit on a cleaned DataFrame (output of parse.load_dataset).

    Returns a dict like:
        {
          "verdict": "CLEAN" | "SUSPECT" | "LEAKING",
          "checks": {
              "duplicates": {...},
              "scaffold":   {...},
              "similarity": {...},
              "baseline":   {...},
          },
          "summary": "<one honest paragraph>",
        }
    """
    train, test = split_frames(df)

    checks = {
        "duplicates": check_duplicates(train, test),
        "scaffold": check_scaffold_overlap(train, test),
        "similarity": nearest_neighbor_similarities(train, test),
        "baseline": dumb_baseline(train, test),
    }

    dup_frac = checks["duplicates"]["fraction_leaked"]
    sim_frac = checks["similarity"]["fraction_above_0_8"]
    scaf_frac = checks["scaffold"]["fraction_shared"]
    base_score = checks["baseline"]["score"]
    base_leaking_above, base_clean_below = _baseline_bands(checks["baseline"]["metric_name"])

    # --- verdict ---------------------------------------------------------------
    # LEAKING is reserved for CONSTRUCTIVE evidence only — a flag that *demonstrates*
    # the label can be recovered by memorization, not merely that molecules look alike:
    #   * exact duplicates  (the same molecule, with its label, sits in both splits)
    #   * dumb baseline      (a no-learning lookup actually achieves a high score)
    # High train↔test SIMILARITY alone does NOT prove leakage: if the labels carry no
    # signal, similar molecules can't leak anything (the dumb baseline correctly stays
    # at chance). Similarity/scaffold are therefore demoted to SUSPECT-level CONTEXT,
    # never enough on their own to scream LEAKING. (This closes the false positive where
    # similar molecules + random labels were wrongly called LEAKING.)
    leaking = (
        dup_frac > THRESHOLDS["dup_leaking"]
        or base_score > base_leaking_above
    )
    # Anything short of a constructive flag, but with similarity/scaffold/baseline
    # elevated, is SUSPECT — worth a human look, not a verdict.
    suspect = (
        sim_frac > THRESHOLDS["sim_leaking"]
        or scaf_frac > THRESHOLDS["scaffold_suspect"]
        or base_score > base_clean_below
    )
    # CLEAN requires ALL signals quiet, including the constructive ones.
    clean = (
        dup_frac == 0.0
        and not suspect
    )

    if leaking:
        verdict = "LEAKING"
    elif clean:
        verdict = "CLEAN"
    else:
        verdict = "SUSPECT"

    # --- reliability guard -----------------------------------------------------
    # Small splits make the fraction thresholds noisy; say so instead of pretending
    # the verdict is as solid as it is on thousands of rows.
    n_train, n_test = int(len(train)), int(len(test))
    low_confidence = n_train < MIN_RELIABLE_SPLIT or n_test < MIN_RELIABLE_SPLIT
    reliability_note = (
        f"LOW CONFIDENCE: only {n_train} train / {n_test} test rows "
        f"(< {MIN_RELIABLE_SPLIT}); treat this verdict as indicative, not definitive. "
        if low_confidence else ""
    )

    # --- honest summary --------------------------------------------------------
    summary = (
        f"{reliability_note}"
        f"Verdict: {verdict}. "
        f"{checks['duplicates']['message']} "
        f"{checks['similarity']['message']} "
        f"{checks['scaffold']['message']} "
        f"{checks['baseline']['message']} "
        "Note: this tool is a smoke detector — it can demonstrate that leakage is "
        "PRESENT, but a CLEAN result never proves leakage is absent. The duplicate and "
        "baseline checks are constructive (they show real memorization); the similarity "
        "and scaffold numbers are context-dependent and only harmful if your real-world "
        "inputs will be more novel than this test set."
    )

    return {
        "verdict": verdict,
        "checks": checks,
        "summary": summary,
        "low_confidence": bool(low_confidence),
        "n_train": n_train,
        "n_test": n_test,
    }
