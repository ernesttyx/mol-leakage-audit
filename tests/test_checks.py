"""
test_checks.py — tiny tests on hand-made datasets where YOU know the answer.

Why this matters: this is how you prove (to yourself and to skeptics) that the auditor
is correct. If you put an identical molecule in train and test, the duplicate check MUST
flag it. If it doesn't, your code is wrong — better to find out here than in public.

Run with:  pytest    (from the audit/ folder, venv active)

Two groups of tests live here:
  1. Per-check unit tests on tiny hand-made inputs (the originals).
  2. Pipeline-correctness "sanity" tests (oracle / metamorphic / cross-check) that prove
     the WHOLE pipeline behaves as the math demands — these re-prove on every run that
     there's no bug, and they pin the false-positive fix in report.py.
"""

import random

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from backend.parse import canonical_smiles, load_dataset, split_frames
from backend.checks.duplicates import check_duplicates
from backend.checks.scaffold import check_scaffold_overlap, scaffold_split
from backend.checks.similarity import nearest_neighbor_similarities
from backend.checks.baseline import dumb_baseline
from backend.report import audit


def _df(rows):
    """Helper: build a clean DataFrame from (smiles, label, split) tuples."""
    df = pd.DataFrame(rows, columns=["smiles", "label", "split"])
    df["smiles_canonical"] = df["smiles"].apply(canonical_smiles)
    return df


def test_canonical_smiles_normalizes_same_molecule():
    # CCO and OCC are both ethanol -> must canonicalize to the SAME string.
    assert canonical_smiles("CCO") == canonical_smiles("OCC")


def test_duplicate_is_flagged():
    # Ethanol is in BOTH train and test -> must be reported as leaked.
    df = _df([
        ("CCO", 1, "train"),
        ("CCO", 1, "test"),    # <- the leak
        ("c1ccccc1", 0, "test"),
    ])
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    result = check_duplicates(train, test)
    assert result["n_leaked"] >= 1


def test_no_duplicate_when_disjoint():
    df = _df([
        ("CCO", 1, "train"),
        ("c1ccccc1", 0, "test"),   # different molecule -> no leak
    ])
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    result = check_duplicates(train, test)
    assert result["n_leaked"] == 0

def test_scaffold_overlap_flags_shared_core():
    # Both train and test are benzene derivatives -> same scaffold -> overlap.
    df = _df([
        ("c1ccccc1C", 0, "train"),    # toluene
        ("c1ccccc1CC", 0, "test"),    # ethylbenzene — same benzene scaffold
    ])
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    result = check_scaffold_overlap(train, test)
    assert result["n_shared"] >= 1
    assert result["fraction_shared"] > 0


def test_dumb_baseline_high_when_test_copies_train():
    # Test molecules are near-identical to a train molecule with the SAME label
    # -> a copy-the-neighbor lookup should score perfectly.
    df = _df([
        ("c1ccccc1", 1, "train"),
        ("CCCCCC", 0, "train"),
        ("c1ccccc1C", 1, "test"),     # like benzene (label 1)
        ("CCCCCCC", 0, "test"),       # like hexane (label 0)
    ])
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]
    result = dumb_baseline(train, test)
    assert result["score"] >= 0.9   # memorization wins -> leaky split


def test_end_to_end_clean_vs_leaky_examples():
    # The shipped toy files must produce the verdicts they're named for.
    clean = audit(load_dataset("data/examples/toy_clean.csv"))
    leaky = audit(load_dataset("data/examples/toy_leaky.csv"))
    assert leaky["verdict"] == "LEAKING"
    assert clean["verdict"] in ("CLEAN", "SUSPECT")   # at minimum, not LEAKING
    assert clean["verdict"] != "LEAKING"


def test_scaffold_split_produces_disjoint_scaffolds():
    # After re-splitting, no scaffold should appear in both train and test.
    from backend.checks.scaffold import scaffold_of
    df = _df([
        ("c1ccccc1C", 1, "train"),
        ("c1ccccc1CC", 1, "train"),
        ("CCCCCC", 0, "test"),
        ("CCCCCCC", 0, "test"),
    ])
    fixed = scaffold_split(df, test_frac=0.5)
    train_sc = {scaffold_of(s) for s in fixed[fixed["split"] == "train"]["smiles_canonical"]}
    test_sc = {scaffold_of(s) for s in fixed[fixed["split"] == "test"]["smiles_canonical"]}
    assert train_sc.isdisjoint(test_sc)


# ---------------------------------------------------------------------------
# Pipeline-correctness sanity tests (oracle / metamorphic / cross-check).
# These prove the WHOLE pipeline is bug-free, not just the individual checks.
# ---------------------------------------------------------------------------

_DIVERSE = [
    "c1ccccc1", "Cc1ccccc1", "Oc1ccccc1", "Nc1ccccc1", "c1ccncc1", "c1ccoc1", "c1ccsc1",
    "C1CCCCC1", "CCO", "CC(=O)O", "CC(=O)C", "CC#N", "c1ccc2ccccc2c1", "c1ccc2[nH]ccc2c1",
    "c1cnc[nH]1", "C1CCNCC1", "C1COCCN1", "O=Cc1ccccc1", "COc1ccccc1", "C=Cc1ccccc1",
    "Clc1ccccc1", "OC(=O)c1ccccc1", "O=[N+]([O-])c1ccccc1", "CC(C)Cc1ccccc1",
]


def _diverse_molecules():
    """Chemically varied molecules with DISTINCT fingerprints (unlike linear alkanes,
    which Morgan FPs can't tell apart) — needed where nearest-neighbor must find ITSELF."""
    return [s for s in _DIVERSE if Chem.MolFromSmiles(s) is not None]


def _many_molecules():
    """~60 valid molecules — enough for a stable (near-chance) AUROC on random labels.
    Linear alkanes are fine here: degenerate fingerprints don't matter when there is no
    label signal to recover anyway."""
    smis = (
        ["C" * n for n in range(2, 26)]          # alkanes
        + ["C" * n + "O" for n in range(1, 21)]  # alcohols
        + ["C" * n + "N" for n in range(1, 21)]  # amines
    )
    return [s for s in smis if Chem.MolFromSmiles(s) is not None]


def test_oracle_train_equals_test_is_maximally_leaking():
    # UPPER BOUND: test is an exact copy of train. There is no stronger leak possible,
    # so the pipeline MUST call it LEAKING with 100% duplicates and a ~perfect baseline.
    smis = _diverse_molecules()
    rows = [(s, i % 2, "train") for i, s in enumerate(smis)]
    rows += [(s, i % 2, "test") for i, s in enumerate(smis)]  # exact copy
    df = _df(rows)
    report = audit(df)
    assert report["verdict"] == "LEAKING"
    assert report["checks"]["duplicates"]["fraction_leaked"] == 1.0
    assert report["checks"]["baseline"]["score"] >= 0.95


def test_true_negative_random_labels_not_called_leaking():
    # THE FALSE-POSITIVE GUARD. Real, mutually-similar molecules but RANDOM labels:
    # similarity is high, yet the labels carry no signal -> nothing actually leaks.
    # The dumb baseline must stay near chance, and the verdict must NOT be LEAKING.
    rng = random.Random(0)
    smis = _many_molecules()
    rows = [(s, rng.randint(0, 1), "train") for s in smis]
    # carve out ~20% as test (random split)
    n_test = max(2, len(rows) // 5)
    for k in range(n_test):
        s, lbl, _ = rows[k]
        rows[k] = (s, lbl, "test")
    df = _df(rows)
    report = audit(df)
    assert report["verdict"] != "LEAKING"           # <- the fix: similarity alone can't scream LEAKING
    assert report["checks"]["baseline"]["score"] < 0.75  # near chance, not memorizable


def test_permutation_invariance():
    # Shuffling the row order cannot change leakage — it's a set property.
    smis = _many_molecules()
    rows = [(s, i % 2, "train" if i % 5 else "test") for i, s in enumerate(smis)]
    df = _df(rows)
    shuffled = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
    assert audit(df)["verdict"] == audit(shuffled)["verdict"]


def test_similarity_matches_independent_recompute():
    # CROSS-CHECK: recompute each test molecule's nearest-neighbor Tanimoto with a
    # fresh, independent fingerprint call and confirm the pipeline's numbers match.
    smis = _many_molecules()
    rows = [(s, i % 2, "test" if i % 4 == 0 else "train") for i, s in enumerate(smis)]
    df = _df(rows)
    train, test = split_frames(df)
    pipe = nearest_neighbor_similarities(train, test)["similarities"]

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fp = lambda s: gen.GetFingerprint(Chem.MolFromSmiles(s))
    train_fps = [fp(s) for s in train["smiles_canonical"]]
    indep = []
    for s in test["smiles_canonical"]:
        sims = DataStructs.BulkTanimotoSimilarity(fp(s), train_fps)
        indep.append(max(sims))

    assert len(pipe) == len(indep)
    for a, b in zip(pipe, indep):
        assert abs(a - b) < 1e-9


# ---------------------------------------------------------------------------
# Adapter tests — real files don't look like the toy files.
# ---------------------------------------------------------------------------

from backend.adapt import prepare, detect_label_type, normalize_split


def test_adapter_creates_split_when_missing():
    # A file with NO split column must get one created, and the adapter must SAY so.
    raw = pd.DataFrame({
        "smiles": _diverse_molecules(),
        "p_np": [i % 2 for i in range(len(_diverse_molecules()))],
    })
    clean, notes = prepare(raw)  # no split_col, no label_col -> all auto
    assert set(clean["split"].unique()) <= {"train", "test"}
    assert notes["n_test"] > 0 and notes["n_train"] > 0
    assert notes["split_source"].startswith("NO split")   # honest about creating it
    assert notes["label_col"] == "p_np"


def test_adapter_detects_nonstandard_smiles_column():
    # SMILES under a column called 'mol' (like BACE) must be found automatically.
    raw = pd.DataFrame({"mol": ["c1ccccc1", "CCO", "CC(=O)O"], "Class": [1, 0, 1]})
    clean, notes = prepare(raw, make_split_method="random")
    assert notes["smiles_col"] == "mol"
    assert notes["label_col"] == "Class"


def test_adapter_normalizes_train_valid_test():
    # 'Valid' must fold into train; 'Test' stays test.
    s = normalize_split(pd.Series(["Train", "Valid", "Test", "validation"]))
    assert list(s) == ["train", "train", "test", "train"]


def test_adapter_detects_label_type():
    assert detect_label_type(pd.Series([0, 1, 1, 0])) == "binary"
    assert detect_label_type(pd.Series([-0.77, -3.3, -2.06, 1.58, 0.4, 2.2,
                                        -5.1, 0.9, -1.2, 3.3, -0.1])) == "continuous"


def test_adapter_drops_missing_labels():
    raw = pd.DataFrame({
        "smiles": ["c1ccccc1", "CCO", "CC(=O)O", "CCN"],
        "label": [1, None, 0, 1],   # one NaN label -> must be dropped
    })
    clean, notes = prepare(raw, make_split_method="random")
    assert notes["dropped_missing_label"] == 1
    assert len(clean) == 3


def test_adapter_regression_label_runs_end_to_end():
    # Continuous labels must flow through to an R2 baseline (not crash on AUROC).
    import numpy as np
    rng = np.random.default_rng(0)
    smis = _many_molecules()
    raw = pd.DataFrame({"smiles": smis, "solubility": rng.normal(size=len(smis))})
    clean, notes = prepare(raw, make_split_method="random")
    assert notes["label_type"] == "continuous"
    report = audit(clean)
    assert report["checks"]["baseline"]["metric_name"] == "R2"
