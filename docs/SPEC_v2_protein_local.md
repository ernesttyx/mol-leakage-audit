# Spec v2 — protein leakage checks, **local only**

> Trimmed version of `VISION_bio_pipeline.md`. Same core ideas (manifest,
> evidence store, no-hallucination guarantee, danger quadrant) — but **everything
> that requires a cloud, a GPU farm, a 40 GB database, or a SaaS upload is removed.**
> Goal: a single `pip install` + CLI that runs on Ernest's laptop, like the v1 linter.

## Design principles kept from the big spec (unchanged)

1. **No-hallucination guarantee.** Every finding is a deterministic computation that
   points at exact record IDs. The optional LLM narrator is read-only and downstream.
2. **Manifest-driven.** All config in one JSON; data files contain only data.
3. **Evidence objects.** Every finding ships `repro_command` + `input_hash` + metrics.
4. **Scope honesty.** "No leakage *of these types*" — never "clean."

## What is CUT vs. the big spec (and why)

| Cut from big spec | Why it's cut for local v2 |
|---|---|
| Supabase / Modal / Next.js SaaS (Stage 14–15) | Contradicts the "local linter, data never leaves" pitch. Replaced by a CLI. |
| C2 pretraining contamination (UniRef50, ~40 GB) | Too heavy for a laptop; opt-in cloud-only feature for far-future. |
| `faiss-gpu`, A10G GPU tiers | Use **CPU** ESM-2 (`esm2_t12_35M`) + `faiss-cpu`. Slower, but local. |
| HTML/PDF report renderer, evidence explorer UI | v2 emits JSON + a plain-text/Markdown report. UI is later. |
| B2 Foldseek / B3 pocket (structure) | Optional, only if user supplies PDBs. Default = sequence-only. |

## v2 check set (local-runnable)

| ID | Check | Tool (all local, CPU) | Default |
|---|---|---|---|
| A1 | Exact duplicate (record hash) | `hashlib` | on |
| A2 | Near-duplicate | `datasketch` MinHash LSH | on |
| B1 | Sequence-identity clustering | **MMseqs2** CLI (local binary) | on |
| C1 | **Embedding danger quadrant** ★ | `fair-esm` CPU + `faiss-cpu` | on |
| D3 | Group / identity overlap | Python `set` | if `group_column` |
| D4 | Temporal ordering | `pandas` | if `time_column` |
| D5 | Batch / confound (Cramér's V) | `scipy.stats` | if `batch_column` |
| B2 | Structural (Foldseek) | Foldseek CLI | only if `structure_path` |
| B3 | Pocket embedding | `fair-esm` CPU | only if `binding_site_residues` |

**Deferred (need cloud / too heavy):** C2 (UniRef50), GPU tiers, D1/D2 (tabular-only,
belong with v1's small-molecule path, not the protein path).

## ★ C1 is the reason v2 exists

The single novel finding: a test sequence that **passes** sequence-identity filtering
(B1 / DataSAIL would certify it) but sits **close in ESM-2 embedding space** (the model
exploits it). Evidence object carries both numbers side by side:

```
seq_identity(train,test) < 0.30   AND   cosine(ESM2(train), ESM2(test)) > 0.90
```

This is the protein analogue of v1's dumb-baseline proof, and v1's baseline (X1) is how
you *validate* it (§16 falsification: Near group should outperform Far group).

## Local manifest (subset of the big spec's)

```json
{
  "dataset_type":   "protein_sequence",
  "id_column":      "seq_id",
  "sequence_column":"sequence",
  "split_column":   "split",
  "target_column":  "label",
  "model_arch":     "esm2",
  "seq_id_threshold": 0.30,
  "emb_sim_threshold":0.90,
  "group_column":   null,
  "time_column":    null,
  "batch_column":   null,
  "structure_path": null,
  "binding_site_residues": null
}
```

## Runtime expectation (laptop, CPU)

- A1/A2/B1/D3–D5: seconds to ~1 min on a few thousand sequences.
- C1 with `esm2_t12_35M_UR50S` on CPU: ~5 min / 1k sequences (the big spec's own number).
- Keep datasets ≤ a few thousand sequences for v2; note larger sizes for a later GPU mode.

## Install footprint

```
pip install fair-esm faiss-cpu datasketch scipy pandas
# + MMseqs2 binary (conda or prebuilt) ; Foldseek only if structure checks wanted
```

No accounts, no uploads, no Docker required for the default sequence-only path.

## Out of scope for v2 (explicit, to kill scope creep)

SaaS, auth, job queue, GPU, UniRef50, HTML report, multi-user. Those live in a
hypothetical v3 "hosted mode" and must never block the local CLI shipping first.
