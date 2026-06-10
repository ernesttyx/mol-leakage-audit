"""
Check 3 — SCAFFOLD OVERLAP (and the scaffold-split fallback for Day 5).

A "Bemis-Murcko scaffold" is a molecule's core ring skeleton with the side-chains
stripped off. Many drug datasets are analog series: 40 molecules that are the same
scaffold with small decorations. If those scaffolds appear in BOTH train and test,
the model can win by memorizing the scaffold instead of learning chemistry.

This check measures: what fraction of TEST scaffolds already appear in TRAIN.

Fill in on Day 1 (the check) and Day 5 (the fallback splitter).
"""

import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold


def scaffold_of(smiles: str) -> str | None:
    """Return the Murcko scaffold (as canonical SMILES) for one molecule.

    Note: molecules with no ring system (e.g. CCO, ethanol) have an EMPTY scaffold.
    We return "" for those so they all group together as "acyclic" rather than each
    looking like a unique scaffold.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    core = MurckoScaffold.GetScaffoldForMol(mol)
    return Chem.MolToSmiles(core)


def check_scaffold_overlap(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """
    Returns a dict like:
        {
          "n_test_scaffolds": <int>,
          "n_shared": <int>,                 # test scaffolds also seen in train
          "fraction_shared": <float 0..1>,
          "message": "<plain-English summary>",
        }
    """
    train_scaffolds = {
        s for s in (scaffold_of(x) for x in train["smiles_canonical"]) if s is not None
    }
    test_scaffolds = {
        s for s in (scaffold_of(x) for x in test["smiles_canonical"]) if s is not None
    }
    shared = train_scaffolds & test_scaffolds

    n_test_scaffolds = len(test_scaffolds)
    n_shared = len(shared)
    fraction_shared = (n_shared / n_test_scaffolds) if n_test_scaffolds else 0.0
    pct = round(fraction_shared * 100, 1)

    message = (
        f"{n_shared} of {n_test_scaffolds} distinct test scaffolds ({pct}%) also "
        f"appear in training — the model could win by memorizing the scaffold."
    )

    return {
        "n_test_scaffolds": n_test_scaffolds,
        "n_shared": n_shared,
        "fraction_shared": fraction_shared,
        "message": message,
    }


def scaffold_split(df: pd.DataFrame, test_frac: float = 0.2) -> pd.DataFrame:
    """
    Day 5 FALLBACK fix (use if DataSAIL won't install): re-assign the 'split' column so
    that no scaffold appears in both train and test. Returns a new df with a fixed split.

    Idea: group molecules by scaffold, then send WHOLE scaffold-groups to train or test
    (never splitting a group) until ~test_frac of molecules are in test.
    """
    out = df.copy()
    out["_scaffold"] = out["smiles_canonical"].apply(scaffold_of)

    # Group rows by scaffold; each group must stay together (train OR test, never both).
    groups = list(out.groupby("_scaffold", dropna=False).groups.items())
    # Largest groups first — placing big analog series wholesale avoids overshooting.
    groups.sort(key=lambda kv: len(kv[1]), reverse=True)

    n_total = len(out)
    target_test = test_frac * n_total
    n_test = 0
    new_split = {}
    for _scaffold, idx in groups:
        # Send the whole group to test until we've filled the test quota, else train.
        if n_test < target_test:
            for i in idx:
                new_split[i] = "test"
            n_test += len(idx)
        else:
            for i in idx:
                new_split[i] = "train"

    out["split"] = out.index.map(new_split)
    return out.drop(columns="_scaffold")
