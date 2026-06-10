# LEARN.md — What to learn BEFORE you start building

You are a high schooler with a chemistry background. That background is a real
advantage here: you already understand molecules, SMILES, and why two structures
can be "almost the same." The stuff you're missing is mostly *programming plumbing*,
not science. Don't try to learn everything — learn exactly this list and stop.

The golden rule: **learn just enough to build, then learn the rest by building.**
Do NOT spend three weeks on tutorials. Spend ~3–4 short days, then start Day 1.

---

## Tier 0 — Absolute must-haves (don't write a line of project code without these)

### 1. Python basics (≈1–2 days if new)
You need to be comfortable with:
- variables, `print()`, strings, numbers, booleans
- lists `[...]` and dictionaries `{...}`
- `for` loops and `if` statements
- writing and calling a `def function():`
- importing libraries (`import pandas as pd`)
- reading a file / a CSV

What you do NOT need yet: classes/OOP, decorators, async, type theory.

Resource: the first ~10 chapters of *Automate the Boring Stuff* (free online),
or Python's official tutorial sections 3–5. Stop when loops + functions + dicts feel okay.

### 2. The command line / terminal (≈1 hour)
You need to be able to:
- open a terminal in a folder
- run `python something.py`
- run `pip install <thing>`
- create and activate a **virtual environment** (venv) — this keeps the project's
  libraries separate so you don't break your computer's Python.

On Windows (PowerShell), the commands you'll use 90% of the time:
```powershell
python -m venv .venv            # make a virtual environment
.\.venv\Scripts\Activate.ps1    # turn it on (you'll see (.venv) appear)
pip install -r requirements.txt # install the project's libraries
```

### 3. pandas — just the basics (≈half a day)
A dataset is a table. pandas is how Python reads tables.
- `df = pd.read_csv("file.csv")` — load a table
- `df["smiles"]` — grab one column
- `df.shape`, `df.head()` — see size and first rows
- filtering rows: `df[df["split"] == "train"]`

That's genuinely most of what you need.

---

## Tier 1 — The science/cheminformatics part (you'll learn this DURING Day 1)

### 4. RDKit (the chemistry library) — concepts you already half-know
You know what a SMILES string is. RDKit turns that text into a molecule object you
can compute on. The four things you'll actually use:

| Concept | What it means (you already get the chemistry) | RDKit call (rough) |
|---|---|---|
| Parse a SMILES | text → molecule object | `Chem.MolFromSmiles(s)` |
| Canonical SMILES | one *standard* spelling of a molecule (catches duplicates written 2 ways) | `Chem.MolToSmiles(mol)` |
| Fingerprint (ECFP) | a molecule as a bit-vector "barcode" of its substructures | `AllChem.GetMorganFingerprintAsBitVect` |
| Tanimoto similarity | how much two barcodes overlap, 0→1 (1 = identical) | `DataStructs.TanimotoSimilarity` |
| Murcko scaffold | the molecule's "core ring skeleton" with side-chains stripped | `MurckoScaffold.GetScaffoldForMol` |

You don't need to master RDKit. You need these 5 calls. The code scaffold already
shows you where each one goes.

### 5. The ONE machine-learning idea you must hold (conceptual, ≈1 hour of reading)
You do **not** need to learn deep learning or build neural nets. You need exactly this:
- **Train/test split**: you train a model on part of the data (train) and check it on
  unseen data (test). If test isn't truly unseen → the score is a lie → that's *leakage*.
- **A "baseline"**: a deliberately dumb predictor. Your key one is **nearest-neighbor
  lookup**: to predict a test molecule's label, just copy the label of the most-similar
  training molecule. If that dumb trick scores high, the split is gameable = leaking.
- **A metric**: a single number for "how good are the predictions" (e.g. AUROC for
  yes/no labels — closer to 1.0 = better). You'll use `sklearn.metrics`, you won't
  derive the math.

That's it. That's the entire ML knowledge required for v1. Resist learning more
right now — it's a rabbit hole and you don't need it to ship.

---

## Tier 2 — The web app part (you'll learn this on Day 3–4, not before)

### 6. What an "API" and a backend are (≈1 hour conceptually)
- Your chemistry code runs in **Python** (because RDKit is Python). A browser can't run
  Python. So you need a tiny **backend**: a Python program that *waits* for the webpage
  to send it a file, runs the checks, and sends back the results.
- **FastAPI** is the library that does this with very little code. You'll learn ~3 things:
  define an endpoint, accept an uploaded file, return JSON.

### 7. The tiniest bit of front-end (≈half a day)
- **HTML** = the page's content (an upload button, a results area).
- **JavaScript `fetch()`** = how the page sends the file to your Python backend and
  shows what comes back.
- You do NOT need React, frameworks, or fancy CSS for v1. Plain HTML + one JS file.

### 8. Git & GitHub (≈1 hour) — for shipping at the end
- `git init`, `git add .`, `git commit -m "message"`, push to GitHub.
- This is how you "show it to everyone." Learn it on Day 7, not before.

---

## What you should deliberately NOT learn yet (anti-scope list)
- ❌ Deep learning / PyTorch / neural networks
- ❌ React / Vue / any front-end framework
- ❌ Docker (only needed if/when you deploy publicly — a Day 8+ concern)
- ❌ Protein/FASTA handling (that's v2 — v1 is small molecules / SMILES only)
- ❌ Databases (the tool is stateless — file in, report out)
- ❌ Advanced statistics

Every one of these is a way to *not ship*. Skip them on purpose.

---

## Honest self-check before Day 1
You're ready to start when you can, without looking things up:
- [ ] write a Python function that takes a list and returns something
- [ ] read a CSV with pandas and print one column
- [ ] make + activate a venv and `pip install pandas`
- [ ] explain, in one sentence, why a leaky train/test split inflates a score

If those four are true, **stop learning and open ROADMAP.md.**
