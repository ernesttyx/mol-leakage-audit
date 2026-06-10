# Reconciliation — current v1 (SMILES) ↔ the bio spec's evidence format

> Purpose: stop the two documents from contradicting each other by wrapping the
> **existing, working 4 checks** in the spec's *manifest + evidence-object* shape —
> **without adding any new infrastructure** (no ESM-2, no MMseqs2, no Modal, no SaaS).
> This is the cheap bridge: same code, spec-grade output.

---

## 1. How the current 4 checks map onto the spec's check IDs

| Current check (`backend/checks/`) | Spec ID | Notes / gaps to close |
|---|---|---|
| `duplicates.py` — canonical-SMILES set overlap | **A1** Exact Duplicate | Spec hashes the *whole record* (SMILES+label) via SHA-256. v1 hashes the SMILES string only. Easy upgrade: hash `smiles_canonical + label`. |
| `similarity.py` — test→train NN Tanimoto, frac > 0.8 | **B4** (ligand Tanimoto half) | Spec cutoff is 0.60 Morgan-r2/2048; v1 uses 0.80. Keep v1's 0.80 but record the threshold in the evidence object so it's explicit. |
| `scaffold.py` — Murcko overlap | **B4** (Bemis–Murcko half) | Already matches. Fold into the same B4 finding family. |
| `baseline.py` — dumb NN-label-copy → AUROC ★ | **(no spec check)** → call it **X1** | The spec only uses this as its §16 *falsification validator*. v1 makes it a first-class check. Keep it as **X1 "constructive proof"** — it is the cheapest, most honest signal you own. Do **not** drop it. |

**Decision recorded here:** v1 keeps the dumb baseline (X1) as a headline check.
The spec's C1 (ESM-2 danger quadrant) is the *protein-side* analogue and is deferred
to v2 (see `SPEC_v2_protein_local.md`). They are not rivals — X1 is exactly how you
would *validate* a future C1 finding.

---

## 2. The minimal manifest v1 should accept

Today `app.py` takes loose query params (`smiles_col`, `label_col`, `split_col`).
Promote those to a tiny JSON manifest so the input is self-describing and hashable —
this is the single most valuable idea to borrow from the spec, and it costs nothing:

```json
{
  "dataset_type":   "protein_ligand",   // v1 only honors the ligand axis
  "id_column":      "id",
  "smiles_column":  "smiles",
  "label_column":   "label",
  "split_column":   "split",
  "tanimoto_threshold": 0.80,           // B4 / similarity cutoff
  "dup_leaking_frac":   0.05,
  "baseline_leaking":   0.85
}
```

Rule borrowed from the spec: **anything in the data file is data; anything that
configures a check lives in the manifest.** Store `SHA-256(manifest bytes)` and
`SHA-256(dataset bytes)` once, reuse in every finding.

---

## 3. Wrap each check's output as a spec-style evidence object

Current checks return ad-hoc dicts (`{n_leaked, fraction_leaked, message}`).
Keep computing exactly the same numbers, but emit them in this shape so the
output is reviewer-grade and forward-compatible with v2:

```json
{
  "finding_id":     "uuid-v4",
  "check_id":       "A1",                 // A1 | B4 | X1
  "severity":       "CRITICAL",           // per-check thresholds, see §4
  "metric":         "exact_smiles_match",
  "threshold":      0.0,
  "measured_value": 0.07,
  "train_record_id":"mol_0042",
  "test_record_id": "mol_1193",
  "contamination_frac": 0.07,
  "repro_command":  "python -m backend.report --check A1 --id mol_1193",
  "input_hash":     "sha256:...",
  "manifest_hash":  "sha256:...",
  "code_version":   "0.1.0"
}
```

Checks that can't run emit `SKIPPED` with a reason (e.g. no `smiles_column`) —
never silently omit. Checks that find nothing emit `PASS` with `contamination_frac: 0`.

---

## 4. Severity tiers for the v1 checks (borrowed, simplified)

| Check | CRITICAL | HIGH | MEDIUM | PASS |
|---|---|---|---|---|
| A1 (exact dup) | any > 0 | — | — | 0 |
| B4 (Tanimoto/scaffold) | — | frac > 0.50 | frac > 0.20 | else |
| X1 (dumb baseline) | — | score > 0.85 | score > 0.65 | else |

Report-level severity = max across findings. This replaces the current flat
`CLEAN / SUSPECT / LEAKING` string with a tiered one **without changing the math**
(the existing `THRESHOLDS` in `report.py` already encode these numbers).

---

## 5. What this bridge does and does NOT do

- **Does:** make v1 output self-describing, hashable, reproducible, and shaped
  exactly like the future protein pipeline → the two docs stop contradicting.
- **Does NOT:** add proteins, ESM-2, GPUs, a database, or a web backend. Zero new
  dependencies. Still a local linter. Still SMILES-only.

This is a ~1-day refactor of `report.py` + `app.py`, not a rebuild.
