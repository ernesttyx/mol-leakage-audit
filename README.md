# audit — a leakage smoke detector for molecular ML datasets

> **Is your train/test split lying to you?** Paste a dataset, get a verdict — plus a
> *constructive proof* (a dumb baseline that games the split) and an optional fixed split.

This is a **diagnostic**, not a curated-dataset service. Every existing tool helps experts
*make* good splits (DataSAIL, splito, scaffold-split). Almost nobody packages the earlier
question for non-experts: **"is the split I already have leaking?"** That's the gap this fills.

## What it does (the pipeline)
```
INPUT  →  PARSE/STANDARDIZE  →  FEATURIZE  →  4 LEAKAGE CHECKS  →  (optional) RE-SPLIT  →  REPORT
(SMILES+      (RDKit canonical   (ECFP        1 near-duplicates    (DataSAIL /            (verdict +
 split)        SMILES)            fingerprints) 2 NN similarity      scaffold split)        proof +
                                               3 scaffold overlap                          chart)
                                               4 dumb-baseline ★
```
★ = the killer check: predict each test label by copying its nearest *training* neighbor's
label. If a no-brain lookup scores high, the split is gameable — that's not a guess, it's a
*demonstration*. (This exact baseline is what the published LIT-PCBA audit used.)

## What it is NOT (honesty section — read before judging)
- **A smoke detector, not a certificate.** It can *prove leakage present*. It cannot
  *prove leakage absent* — "clean" means "these checks didn't find it."
- **Not novel algorithms.** It stands on RDKit (fingerprints, scaffolds), the standard
  Tanimoto/scaffold-split methods, and DataSAIL for the optional fix. The value is the
  **verdict + the proof + the one-click accessibility + neutrality**, not new math.
- **Small molecules / SMILES only (v1).** Protein/FASTA support is v2.

## Why free + open-source + local is the *right* form factor (not a weakness)
Labs won't upload proprietary data to a SaaS — which is exactly why no SaaS competitor
exists. This runs **on your machine like a linter**; your data never leaves. Reputation gets
built by auditing *public* datasets in the open; private use needs no data-sharing at all.

## Project layout
```
audit/
├── README.md            ← you are here
├── LEARN.md             ← what to learn first (start here if you're new)
├── ROADMAP.md           ← the 7-day build plan
├── requirements.txt
├── backend/
│   ├── parse.py         ← read CSV, canonicalize SMILES, drop bad rows
│   ├── featurize.py     ← SMILES → ECFP fingerprints
│   ├── report.py        ← run all checks → one report + verdict
│   ├── app.py           ← FastAPI endpoint (/audit)
│   └── checks/
│       ├── duplicates.py  ← molecules in both train & test
│       ├── similarity.py  ← test→train nearest-neighbor Tanimoto
│       ├── scaffold.py    ← shared Murcko scaffolds
│       └── baseline.py    ← ★ dumb-baseline constructive proof
├── frontend/            ← plain HTML + JS upload page
├── data/
│   ├── examples/        ← tiny sample datasets to play with
│   └── validation/      ← known-leaky / known-clean sets for the validation table
├── tests/               ← tests on hand-made datasets with known answers
└── docs/
    └── validation.md    ← proof the auditor itself is correct
```

## Quickstart
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app:app --reload      # ONE command...
```
Then open **http://localhost:8000** — that's the whole web app. The FastAPI server
serves the page *and* the API from the same place, so there's no second step and no
CORS to fight. Drop in a CSV (columns `smiles`, `label`, `split`), get a verdict, and
click **Fix my split** to get a scaffold-re-split CSV with a before/after proof.

Other URLs on the same server: `/docs` (interactive API tester), `/health` (liveness).

## Credits / standing on shoulders
RDKit · [DataSAIL](https://github.com/kalininalab/DataSAIL) · Polaris · Pat Walters
(Practical Cheminformatics) · the LIT-PCBA audit (arXiv:2507.21404). This tool packages
their ideas into an accessible front door — it does not claim to replace them.

## License
MIT (add a LICENSE file on Day 7).
