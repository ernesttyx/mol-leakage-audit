# ROADMAP — status, not a calendar

**Project:** a leakage *audit* tool for molecular ML datasets.
**You give it** a dataset with a train/test split → **it tells you** whether the split
is trustworthy, *proves* leakage with a dumb-baseline, and optionally hands back a fixed split.

**Scope discipline (still the #1 rule):** v1 is **SMILES / small molecules only**. No
proteins, no deep learning. If you're tempted to add something, write it in
`docs/IDEAS_v2.md` and move on. The protein expansion has its own scoped doc
(`docs/SPEC_v2_protein_local.md`) — local only, deliberately deferred.

---

## ✅ Done (the spine is built and verified)

- **Parse / standardize** — `backend/parse.py`: read CSV, RDKit-canonicalize SMILES,
  drop + count unparseable rows, split into train/test.
- **Featurize** — `backend/featurize.py`: SMILES → ECFP/Morgan fingerprints.
- **The 4 checks** — `backend/checks/`:
  1. `duplicates.py` — same molecule in train AND test
  2. `similarity.py` — each test molecule's nearest train neighbor (Tanimoto)
  3. `scaffold.py` — % of test scaffolds already seen in train
  4. `baseline.py` ★ — copy nearest train label, score it (the constructive proof)
- **Report + verdict** — `backend/report.py`: runs all 4, returns CLEAN / SUSPECT / LEAKING.
- **Web app (one command, one URL)** — `backend/app.py` serves both the API and the
  page. `uvicorn backend.app:app --reload` → open **http://localhost:8000**. No separate
  file-open step, no CORS dance.
- **The fix** — `POST /fix` + the **Fix my split** button: scaffold re-split, runs the
  dumb baseline *before vs after*, and lets you download the corrected CSV. The score
  drop is the proof the fix worked.
- **Tests** — `tests/test_checks.py`, hand-made datasets with known answers. All passing.

---

## 🔜 Left to do (in priority order)

1. **Validation table** — `docs/validation.md`: run the tool on datasets with KNOWN
   status (LIT-PCBA = known leaky; a proper scaffold split = known clean) and show it
   agrees with the published audits. **This table is the credibility.** Highest priority.
2. **DataSAIL as the real fix** — right now `/fix` uses the built-in scaffold split.
   Optionally swap in DataSAIL (`pip install datasail`) for a stronger re-split, keeping
   scaffold split as the no-dependency fallback. Credit it openly.
3. **Polish** — make the verdict chip + similarity histogram read well to a non-expert;
   tighten the honest-limits language in the UI.
4. **Ship** — `git init`, commit, push public, MIT license, a screenshot, a short honest
   write-up (the leakage-invalidated-papers problem, what it does, the validation table,
   the limits). Optional: deploy to a free host (HuggingFace Spaces handles RDKit well);
   if deploy is painful, "clone + run locally" is the privacy-friendly model anyway.

---

## If you have to cut, protect the spine

The spine is **parse → 4 checks → dumb baseline → readable report**. That's the product
and it's already done. Cut from the *top* of the "left to do" list inward, never the spine:
deploy first, then DataSAIL (scaffold fallback already ships), then polish. **Never cut**
the validation table — a diagnosis-only local tool *with* a validation table is already a
real, shippable, respectable project.

---

## The one sentence to keep on your wall

> Build the **smoke detector** (the 4 checks + dumb-baseline proof), validate it against
> **known-leaky and known-clean** datasets, and **be honest** about what it can't do.
