"""
featurize.py — Step 3: turn SMILES into fingerprints RDKit can compare.

A "fingerprint" is a molecule's barcode: a long vector of bits where each bit means
"this molecule contains substructure X". Two molecules are similar if their barcodes
overlap a lot (that overlap is the Tanimoto similarity, computed in similarity.py).

We use ECFP / Morgan fingerprints — the cheminformatics standard.

You'll fill this in on Day 2.
"""

from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator


def fingerprint(smiles: str, radius: int = 2, n_bits: int = 2048):
    """
    Return the ECFP/Morgan fingerprint (a bit vector) for one canonical SMILES.

    radius=2 means ECFP4 (the common default). n_bits is the barcode length.
    Uses the modern MorganGenerator API (GetMorganFingerprintAsBitVect is deprecated
    in recent RDKit and prints a warning).
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    return gen.GetFingerprint(mol)


def fingerprints_for(smiles_list: list[str]) -> list:
    """Compute fingerprints for a whole list of SMILES (keeps order)."""
    return [fingerprint(s) for s in smiles_list]
