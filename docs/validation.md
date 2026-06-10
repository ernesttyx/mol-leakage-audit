# Validation — proof the auditor itself is correct

**This document is the credibility.** Anyone can write code that prints a scary "LEAKING"
label. The question a skeptic asks is: *does it flag leakage when leakage is really there,
and stay quiet when it isn't?* We answer it by running the tool on inputs whose status is
already known and showing the verdicts agree.

**Reproduce everything here with:** `python -m scripts.validate`
(downloads MoleculeNet BACE once into `data/validation/`, then audits 4 inputs).

## The validation principle
- **Known-LEAKY input → tool must flag it.** (True positive.)
- **Known-CLEAN input → tool must stay quiet.** (True negative — proves it's not just a
  scary-label generator.)

## The controlled same-data experiment (the strong test)

Real public dataset: **MoleculeNet BACE** — 1,513 molecules, binary label (BACE-1
inhibitor yes/no). We split the *same molecules* two ways and audit each:

- **Random split** — molecular random splits are *known* to leak: analog series scatter
  across train/test, so a memorization baseline scores high. (Sheridan 2013; Wu et al.
  *MoleculeNet* 2018; the same effect the LIT-PCBA audit, arXiv:2507.21404, quantified.)
- **Scaffold split** — same molecules, re-split so no Murcko scaffold spans the boundary.

Only the split changes, so any difference in the verdict is caused by the split alone.

## Results (run 2026-06-10, seed 42)

Verdicts use the **conservative logic** (LEAKING requires *constructive* evidence —
exact duplicates or a high dumb-baseline; high similarity alone is SUSPECT, not LEAKING):

| dataset | expected | verdict | dup_% | nn>0.8_% | scaf_% | baseline |
|---|---|---|---|---|---|---|
| toy_leaky (hand-made) | LEAKING | **LEAKING** | 100.0 | 100.0 | 100.0 | 1.000 |
| toy_clean (hand-made) | CLEAN | **CLEAN** | 0.0 | 0.0 | 33.3 | 0.500 |
| BACE random split | LEAKING/SUSPECT | **SUSPECT** | 0.0 | 53.1 | 45.0 | 0.778 |
| BACE scaffold split | CLEANER | **SUSPECT** | 0.0 | 30.5 | 0.0 | 0.776 |

## What this shows

1. **True positive (flags real leakage).** The hand-made leaky set is caught outright
   (100% duplicates → LEAKING). The BACE *random* split is correctly raised as **SUSPECT**:
   53% of test molecules have a >0.8 Tanimoto twin in train and the memorization baseline
   is 0.78 — clear evidence the split is gameable, surfaced without overclaiming. (It is
   SUSPECT rather than LEAKING because the constructive baseline, 0.78, sits below the 0.85
   "this is demonstrably memorized" bar — see the tradeoff note below.)
2. **True negative (stays quiet when clean).** The hand-made disjoint set returns CLEAN
   (0% duplicates, 0% near-neighbors, chance-level 0.50 baseline). The tool is not just a
   scary-label generator.
3. **Same-data proof.** Switching BACE from random → scaffold split, *with no other
   change*, drops near-neighbor leakage 53.1% → 30.5% and exact-scaffold sharing
   45.0% → 0.0%. The split alone moved the measured leakage, exactly as theory predicts.

## The false-positive guard (why the verdict logic is conservative)

A separate test (`tests/test_checks.py::test_true_negative_random_labels_not_called_leaking`)
takes real, mutually-similar molecules but assigns **random labels**. Similarity is high
(53% > 0.8) yet nothing actually leaks, because the labels carry no signal. The dumb
baseline correctly stays at chance (≈0.50). The verdict must therefore **not** be LEAKING —
and under the conservative logic it is SUSPECT, not LEAKING. High similarity alone is *not*
proof of leakage; only a constructive flag (duplicate or a baseline that actually scores
high) earns LEAKING.

**The tradeoff this buys (stated honestly).** Making LEAKING require constructive evidence
removes similarity-driven false positives, but it raises the bar: a genuinely-but-moderately
leaky split like BACE-random (baseline 0.78) now reads SUSPECT rather than LEAKING. That is
acceptable because (a) SUSPECT still surfaces the problem, and (b) the raw numbers
(53% near-neighbors, 0.78 baseline) are always shown, so the user sees the evidence
regardless of the one-word label. We prefer to under-*label* moderate cases as SUSPECT than
to over-*label* mere similarity as LEAKING.

## The honest caveat (stated, not hidden)

On BACE the **dumb-baseline barely moved** (0.778 → 0.776) even though similarity dropped
sharply. That is a *real finding, not a tool bug*: scaffold splitting removes shared
scaffolds but still leaves 30% of test molecules with a highly-similar (>0.8 Tanimoto)
training neighbor, because scaffold identity ≠ overall similarity. BACE is a single-target
analog-rich set, so memorization-by-analogy survives a scaffold split. Two honest
consequences:

- The tool's signals are **mutually consistent** (residual similarity → residual
  memorizability) — a good sign for its internal validity.
- **Scaffold split is a partial fix, not a cure** for analog-heavy sets. This is the known
  motivation for stronger splitters (cluster / DataSAIL), which is exactly the next
  roadmap item. The `Fix my split` button uses scaffold split as the no-dependency
  fallback and is honest about reporting when the baseline does *not* drop.

The softer checks (similarity thresholds) are context-dependent: high train↔test similarity
is only *harmful* if real-world inputs will be more novel than the test set. We report the
measured numbers and let the user judge against their deployment setting. The dumb-baseline
needs no such caveat — it's a constructive demonstration, not an inference.

## Success criterion — met

The tool (a) flags the known-leaky inputs — LEAKING for the hard case, SUSPECT for the
moderate one — (b) stays CLEAN on the known-clean input, (c) does **not** call mere
similarity-with-random-labels LEAKING (no false positive), and (d) shows leakage signals
measurably drop under a better split of identical data. The two inconvenient numbers
(baseline flat on BACE scaffold; BACE-random landing at SUSPECT not LEAKING) are reported
honestly with correct explanations rather than hidden or papered over.
