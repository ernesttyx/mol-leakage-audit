> # ⚠️ STATUS: VISION / ROADMAP — **NOT IMPLEMENTED**
> This document is a *design specification for a future, much larger tool* (protein
> sequences, ESM-2 embeddings, homology/Foldseek, pretraining-contamination, 13 checks,
> a DataSAIL-falsification protocol). **None of it is implemented in this repository.**
>
> **What v1 (this repo) actually ships** is a small-molecule (SMILES) leakage *smoke
> detector* with **4 checks** — exact duplicates, nearest-neighbour Tanimoto similarity,
> Bemis–Murcko scaffold overlap, and a dumb-baseline constructive proof. See the
> [README](../README.md) for what the code really does, and
> [`RECONCILE_v1_to_spec.md`](RECONCILE_v1_to_spec.md) for how the two relate.
>
> Read on only if you want the long-term vision.

---

# Bio-Data Leakage Audit Tool — Complete Pipeline Specification

> A reproducible, evidence-grounded auditor for detecting data leakage in biological ML datasets.
> Every finding is produced by a deterministic computation and points at exact records.
> The LLM narrator, if used, can only paraphrase findings that already exist — it has no path to invent one.

---

## Table of Contents

1. [Motivation & Research Context](#1-motivation--research-context)
2. [Core Design Principle — No Hallucination Guarantee](#2-core-design-principle--no-hallucination-guarantee)
3. [The Two Senses of "Data Leakage"](#3-the-two-senses-of-data-leakage)
4. [Industry Prior Art & The Genuine Gap](#4-industry-prior-art--the-genuine-gap)
5. [The Circular Agreement Problem](#5-the-circular-agreement-problem)
6. [DataSAIL Failure Modes — Where Splitters Are Wrong](#6-datasail-failure-modes--where-splitters-are-wrong)
7. [The Audit Manifest](#7-the-audit-manifest)
8. [Stage 0 — Ingestion](#8-stage-0--ingestion)
9. [Stage 1 — Normalize & Index](#9-stage-1--normalize--index)
10. [Stage 2 — The Audit Core (13 Checks, 4 Layers)](#10-stage-2--the-audit-core-13-checks-4-layers)
    - [Layer A — Duplicate Checks](#layer-a--duplicate-checks)
    - [Layer B — Homology & Structural Similarity](#layer-b--homology--structural-similarity)
    - [Layer C — Embedding Space (Novel)](#layer-c--embedding-space-novel)
    - [Layer D — Statistical & ML Leakage](#layer-d--statistical--ml-leakage)
11. [Stage 3 — Severity Quantification](#11-stage-3--severity-quantification)
12. [Stage 4 — Evidence Store](#12-stage-4--evidence-store)
13. [Stage 5 — Report & Narrator](#13-stage-5--report--narrator)
14. [Tech Stack](#14-tech-stack)
15. [Deployment Architecture](#15-deployment-architecture)
16. [Empirical Falsification Protocol](#16-empirical-falsification-protocol)

---

## 1. Motivation & Research Context

Data leakage is the dominant reason ML models in biology report performance that collapses when deployed in the real world. Kapoor & Narayanan (2023, *Patterns*) surveyed the literature and found leakage affecting at least 294 papers across 17 scientific fields, describing it as "a widespread failure mode in machine-learning-based science" and classifying it into eight distinct types ranging from textbook errors to open research problems.

In biological ML the problem is structurally worse than in other domains, because biological sequences have deep evolutionary relationships that naive random splitting does not respect. Two protein sequences can share 25% identity but be nearly identical in fold, binding site geometry, and ESM-2 embedding space — a standard train/test split looks clean by every conventional metric while the model exploits hidden similarity. PPI prediction papers have been shown to drop from state-of-the-art accuracy to near-random performance when sequence similarity between train and test is controlled, demonstrating that previously reported results were entirely attributable to leakage.

This tool is built for the case where a researcher, lab, or journal reviewer wants to audit an *existing* split they had no control over — a collaborator's dataset, a public benchmark, or a paper under review — and produce a forensic, reproducible report that either clears the split or attaches evidence to specific findings.

---

## 2. Core Design Principle — No Hallucination Guarantee

The fundamental architectural decision: **every finding must be the output of a deterministic computation that points at the exact records that triggered it.** No finding exists without evidence attached.

The failure mode this prevents is asking an LLM "is there leakage in this dataset?" — the model will pattern-match and confabulate. The fix is not better prompting; it is structural:

```
Deterministic audit core  →  Evidence store  →  LLM narrator (read-only)
```

The LLM narrator sits strictly downstream of the evidence store. It receives only the findings JSON and is constrained to rephrase verified findings into plain English. It has no path to write a new finding. If the narrator is removed entirely, the audit result is byte-for-byte identical — the LLM changes the prose, never the truth claims.

Three properties that make this auditor-grade rather than developer-grade:

1. **Determinism.** Same input + same seed → same findings, always. No stochastic verdicts.
2. **Falsifiability.** Every finding ships with the exact record IDs and a `repro_command` that regenerates it. A skeptical reviewer can rerun and confirm or refute.
3. **Scope honesty.** The tool reports "no leakage of *these specific types* detected," never "this dataset is clean." Leakage types are open-ended; overclaiming would itself be a form of hallucination.

---

## 3. The Two Senses of "Data Leakage"

This tool addresses **ML data leakage** — information from outside the training set contaminating model development so that reported performance is inflated and collapses in deployment. This is categorically different from **privacy leakage** (sensitive identity or genotype escaping a released dataset via membership-inference or re-identification). The two require completely different tools. This specification covers ML data leakage only.

---

## 4. Industry Prior Art & The Genuine Gap

### General-purpose leakage and data-validation tools

| Tool | What it does | What it misses |
|---|---|---|
| **Deepchecks** | 62 checks for tabular/CV/NLP data including train/test index leakage, feature leakage, drift | Homology; embedding-space proximity; pretraining contamination |
| **Cleanlab / Datalab** | Label error detection; near-duplicate flagging via model embeddings | Bio-specific similarity; structural similarity; pocket similarity |
| **leakr** (R, 2025) | Train/test contamination, temporal leakage, duplication in R workflows | All bio-specific checks |
| **LeakageDetector** | Static analysis of ML *code* for leakage-inducing patterns | Data-level checks |

None of these understand sequence homology. They would pass a randomly-split protein dataset as clean while it is catastrophically contaminated.

### Bio-specific splitters and partitioners

| Tool | What it does | What it misses |
|---|---|---|
| **DataSAIL** (*Nature Comms*, 2025) | Splits biomolecular data minimising sequence-identity leakage | Post-hoc auditing; embedding-space checks; pretraining contamination; statistical/ML checks |
| **SpanSeq** | Similarity-based sequence partitioner for genes/proteins/genomes | Post-hoc auditing; all non-sequence checks |
| **ProtParts** | Web server for clustering and partitioning protein datasets | Post-hoc auditing |
| **CD-HIT / MMseqs2** | Sequence clustering primitives | Not an auditor; no severity quantification; no evidence objects |

The key distinction: bio tools *fix* splits (you give them data; they hand back partitions). This tool *audits* splits (you give it an existing split; it hands back evidence). The two postures require different outputs.

### The genuine gap

No existing tool combines:
- Bio-aware homology checking (sequence + structure + pocket)
- Embedding-space leakage detection (the axis splitters are blind to)
- Pretraining contamination check against ESM-2's corpus
- Multi-modal leakage (protein + ligand)
- Standard ML checks (target, preprocessing, group, temporal, batch)
- Reproducible, evidence-grounded findings with severity quantification
- Post-hoc auditing posture (works on any existing split)

---

## 5. The Circular Agreement Problem

**The concern:** if this tool uses the same math as DataSAIL (sequence identity clustering via MMseqs2), it will rubber-stamp whatever DataSAIL already certified. Two instruments calibrated identically will always agree.

**Why this is not fatal — and why the tool can prove DataSAIL wrong:**

The mistake is treating leakage as a property of the dataset. It is not. Leakage is a property of the *relationship between the dataset and the model*. The similarity metric that governs leakage is whatever the model is actually computing internally:

| Model type | Relevant similarity metric |
|---|---|
| k-mer / n-gram model | k-mer Jaccard overlap |
| Raw sequence (CNN) | Local subsequence matches |
| ESM-2 embedding model | Cosine distance in ESM-2 embedding space |
| GNN on contact map | Topological overlap in the protein graph |
| Binding affinity predictor | Binding site geometry similarity |

DataSAIL assumes sequence identity is the relevant metric. For raw sequence models it is a reasonable approximation. For any embedding-based model, it is **a certificate from the wrong jurisdiction.**

The danger quadrant — the core insight — is the set of train/test pairs where:

```
seq_identity(train, test) < threshold    [DataSAIL passes]
AND
cosine_sim(ESM2(train), ESM2(test)) > threshold    [model exploits proximity]
```

Every finding in this quadrant is direct evidence that DataSAIL's split was insufficient for the declared model architecture. The evidence object contains both numbers side by side.

---

## 6. DataSAIL Failure Modes — Where Splitters Are Wrong

### Failure 1: Embedding-space leakage

Two proteins at 25% sequence identity can sit very close in ESM-2 embedding space because ESM-2 has encoded structural, functional, and evolutionary information beyond raw sequence identity. DataSAIL clusters by sequence identity and has no visibility into ESM-2's representation. This is measurable and publishable.

### Failure 2: Pretraining contamination

ESM-2 was pretrained on ~250 million UniRef50 sequences. DataSAIL clusters *your downstream dataset* — it does not check whether test sequences appear in ESM-2's pretraining corpus. If they do, ESM-2 produces systematically higher-quality embeddings for those test sequences regardless of the downstream split, inflating performance. No current splitter or auditor checks this axis.

### Failure 3: Local pocket vs. global sequence similarity

DataSAIL measures global sequence identity. For a binding affinity prediction task, the model exploits *binding site geometry*, not full-chain similarity. Two globally dissimilar sequences can have nearly identical binding pockets. A DataSAIL-clean split can be heavily contaminated at the pocket level, which the model will exploit for exactly the task it is benchmarked on.

### Failure 4: Convergent evolution over-flagging (the reverse error)

High TM-score does not always imply homology. Proteins can arrive at the same fold through convergent evolution with no shared ancestry. Naively flagging all high-TM-score pairs as leakage would *over-flag* — treating unrelated proteins as a leakage risk when they are not. Proper E-value filtering (Foldseek E-value < 1e-5) distinguishes true structural homologs from convergent analogues.

### Failure 5: Threshold universality

The 30% sequence identity threshold was derived from studies on globular proteins. It does not apply uniformly to:
- Short peptides (10–50 AA): 25% identity peptides can be functionally near-identical
- Intrinsically disordered proteins: sequence identity is a poor proxy for functional similarity
- Membrane proteins: topology constraints mean structural similarity persists at lower sequence identity
- RNA sequences: different similarity regime entirely

The manifest's `seq_id_threshold` field exists to let users declare the appropriate threshold for their biological domain rather than inherit a one-size threshold.

### Failure 6: Multi-modal blindness

DataSAIL handles one data type per run. Real protein-ligand datasets (PDBbind, BindingDB) have two axes: protein sequence and ligand structure. A DataSAIL protein-space-clean split can have 40% of test ligands within Tanimoto 0.6 of training ligands. The model will exploit ligand-side similarity just as easily as protein-side similarity, and DataSAIL will never see it.

### Failure 7: No statistical or ML checks

DataSAIL has no concept of target leakage, preprocessing-before-split, group identity leakage, temporal ordering violations, or batch-label correlation. These are the most common failure modes in clinical and multi-lab genomics datasets and require a completely different class of computation.

---

## 7. The Audit Manifest

The manifest is a JSON file submitted alongside the dataset. It is the user's declaration of scientific intent. Every check is parameterized by the manifest rather than guessing from the data. Anything inside the data files is data, never configuration.

```json
{
  "dataset_type": "protein_sequence",
  // protein_sequence | protein_structure | protein_ligand | tabular

  "split_column":  "split",
  // column name holding train / val / test labels

  "target_column": "label",
  // the column you are predicting

  "id_column":     "seq_id",
  // unique record identifier — used in all finding objects

  "sequence_column":       "sequence",
  // for FASTA / tabular sequence data

  "structure_path":        null,
  // path to folder of .pdb files; enables B2, B3 (with binding_site_residues)

  "ligand_column":         null,
  // SMILES column; enables B4; null = B4 skipped cleanly with a note

  "binding_site_residues": null,
  // list of 1-indexed residue positions for B3 pocket embedding check
  // e.g. [21, 28, 29, 63, 66] — your WhiB7 hotspot residues

  "group_column":          "organism_id",
  // optional: declares entity grouping for D3 check

  "time_column":           null,
  // optional: timestamp column; enables D4 check

  "batch_column":          "batch_id",
  // optional: batch or collection site column; enables D5 check

  "model_arch":            "esm2",
  // raw_sequence | esm2 | structure
  // critical: determines which similarity metric C1 uses

  "seq_id_threshold":      0.30,
  // B1 clustering threshold — lower for short peptides (e.g. 0.50)
  // higher for highly diverged families (e.g. 0.20)

  "emb_sim_threshold":     0.90,
  // C1 cosine similarity cutoff in embedding space

  "tm_score_threshold":    0.50,
  // B2 structural similarity cutoff

  "tanimoto_threshold":    0.60
  // B4 ligand Tanimoto cutoff
}
```

**Why `model_arch` is the most important field.** The relevant similarity metric for leakage is whatever the model is internally computing. `model_arch: "esm2"` tells the auditor to run C1 with ESM-2 cosine distances. `model_arch: "raw_sequence"` would use k-mer Jaccard instead. A dataset split clean under one architecture may not be clean under another.

**Skipped checks are reported explicitly.** If `ligand_column` is null, B4 appears in the report as `SKIPPED (no ligand_column declared)`, not silently omitted. A reader knows the check was available and deliberately not applicable, rather than wondering if it was run.

---

## 8. Stage 0 — Ingestion

**Accepted dataset formats:**
- CSV or TSV (tabular features, sequence column, label column)
- FASTA (sequence ID and sequence; label must be in a companion CSV by ID)
- ZIP of `.pdb` files (for structure-level checks; companion CSV maps PDB IDs to labels)
- `.sdf` or SMILES CSV for ligand-only or protein-ligand datasets

**Split assignment:**
- Preferred: a `split` column inside the dataset file with values `train`, `val`, `test`
- Alternate: a separate two-column CSV mapping `id → split` submitted alongside the dataset

**Input validation (all deterministic):**
- Schema check: declared columns exist and have the right types
- Split completeness: every record has a split assignment; no record is in two splits
- Minimum sizes: warn if any split has fewer than 50 records (severity estimates become unreliable)
- No empty sequences, no null labels
- Manifest hash: SHA-256 of the manifest JSON bytes, stored in every subsequent finding object

---

## 9. Stage 1 — Normalize & Index

**Canonicalization.** Every sequence is lowercased and whitespace-stripped before hashing. Every numerical feature is stored as float64. Column names are sorted alphabetically before hashing so column order does not affect the record hash.

**SHA-256 hashing.** Every record receives a hash of its canonicalized content (sequence + label + all declared feature columns). This hash is the record's identity for A1 (exact duplicate detection) and for the `train_record_id` / `test_record_id` fields in all finding objects.

**Index construction (once, reused by all checks):**

| Index | Used by | Construction |
|---|---|---|
| FAISS flat IP index of training ESM-2 embeddings | C1 | Run ESM-2 on all training sequences; normalize vectors; build index |
| MinHash LSH index of training k-mer sets | A2 | k=3 shingles, 128 permutations, datasketch library |
| MMseqs2 sequence database of training sequences | B1, C2 | `mmseqs createdb` on training FASTA |
| Foldseek structural database of training PDBs | B2 | `foldseek createdb` on training PDB folder |

**Seeding.** `random.seed(42)`, `numpy.random.seed(42)`, `torch.manual_seed(42)` set once at pipeline entry. No check introduces additional randomness.

**Reproducibility hash.** After Stage 1, compute `repro_hash = SHA256(input_hash + code_version + "42")`. This hash is stored in every finding and in the report header. A reviewer can verify they are looking at the same run.

---

## 10. Stage 2 — The Audit Core (13 Checks, 4 Layers)

Each check emits zero or more finding objects. A check that finds nothing emits a `PASS` result with `contamination_frac: 0`. A check that cannot run (missing manifest field) emits `SKIPPED` with reason. No check modifies the dataset or the split.

---

### Layer A — Duplicate Checks

#### A1: Exact Duplicate

**What it catches.** The identical record appearing in both the training set and the test set. Trivial but devastatingly common in assembled benchmarks where multiple sources are merged without deduplication.

**Method.**
1. Build a dictionary mapping SHA-256 hash → list of record IDs for all training records.
2. For every test record, compute its hash and look it up.
3. Any match is an exact duplicate finding.

**Severity.** CRITICAL at any contamination fraction > 0. There is no threshold — an exact duplicate is a binary violation.

**Evidence object fields.**
- `train_record_id`, `test_record_id`: the matching pair
- `hash`: the colliding SHA-256 value
- `contamination_frac`: collisions / |test|

---

#### A2: Near-Duplicate

**What it catches.** Sequences differing by a small number of point mutations — common in variant datasets, single-residue mutagenesis studies, and SNP panels. Standard sequence identity clustering at 30% would not catch two sequences at 95% identity if the threshold is set to 30%.

**Method.**
1. Build MinHash LSH index (k=3 character shingles, 128 permutations) over all training sequences using `datasketch`.
2. For every test sequence, query for approximate nearest neighbours with Jaccard similarity above `near_dup_threshold` (default 0.85).
3. Flag all returned pairs as near-duplicate findings.

**Severity.** HIGH at contamination fraction > 5%, MEDIUM at > 1%.

**Why this is bio-specific.** For genomics or protein variant datasets, near-identical sequences are the research subject — the whole point is to study what small mutations do. That same property means a naive random split will routinely place near-identical variants in both splits.

---

### Layer B — Homology & Structural Similarity

#### B1: Sequence Identity Clustering

**What it catches.** Homologous sequences across the train/test boundary — the core leakage mode in protein and genomics ML, and the axis that DataSAIL targets.

**Method.**
1. Run `mmseqs easy-cluster` on the union of train and test sequences at `seq_id_threshold` (default 0.30) with coverage 0.80.
2. For each resulting cluster, check whether it contains at least one training sequence and at least one test sequence.
3. Every such straddle-cluster is a B1 finding. Each member test sequence is a contaminated record.

**Severity.** CRITICAL if any pair exceeds 0.90 identity; HIGH if 0.50–0.90; MEDIUM if threshold–0.50.

**Critical framing.** B1 is explicitly labelled the baseline check. If DataSAIL was used upstream, B1 will agree with it on this axis — and that is expected and correct. B1's value is that it attaches reproducible evidence to the DataSAIL claim (or refutes it if DataSAIL was misconfigured), and it is the denominator against which C1 findings are compared (the danger quadrant requires B1 passing while C1 fails).

---

#### B2: Structural Similarity

**What it catches.** Proteins with low sequence identity but the same three-dimensional fold — the convergent evolution and remote homology cases that sequence clustering completely misses.

**Method.**
1. Run Foldseek `easy-search` between test PDB structures and training PDB structures.
2. Filter results to TM-score > `tm_score_threshold` (default 0.50) AND sequence identity below `seq_id_threshold` (i.e., would have been missed by B1).
3. Apply E-value filter < 1e-5 to distinguish true structural homologs from coincidental structural repeats (convergent evolution false positives).
4. Flag surviving pairs as B2 findings.

**Severity.** HIGH.

**The convergent evolution problem.** High TM-score does not always imply homology. The E-value filter is the guard: if Foldseek assigns E-value > 1e-5 to a high-TM-score match, the match is classified as potential analogy rather than leakage, and the finding is annotated `possible_convergence: true` rather than flagged as a confirmed violation. This prevents the auditor from over-flagging unrelated proteins as a leakage risk.

**Requires** `structure_path` in manifest. If not provided: `SKIPPED (no structure_path declared)`.

---

#### B3: Binding Pocket Similarity

**What it catches.** Globally dissimilar proteins whose binding sites are nearly identical — directly relevant to binding affinity and drug discovery tasks where the model is predicting pocket-level properties, not whole-chain properties.

**Method.**
1. Load ESM-2 and compute per-residue embeddings for all sequences.
2. For each sequence, extract embeddings at the residue positions declared in `binding_site_residues` and compute their mean — the pocket embedding vector.
3. Build a FAISS index of training pocket embeddings.
4. For each test sequence, query for nearest training neighbours by pocket cosine similarity.
5. Flag pairs with pocket cosine similarity > 0.92 AND global sequence identity below B1 threshold.

**Severity.** HIGH, specifically for binding affinity or pocket-property prediction tasks.

**Why B3 and C1 are different.** C1 uses the full-chain ESM-2 embedding — it captures global sequence/structure/function similarity as ESM-2 sees it. B3 uses only the declared binding site residues — it captures local pocket similarity independent of what the rest of the chain looks like. A long protein can pass C1 (globally dissimilar) and fail B3 (pockets nearly identical), which is exactly the leakage mode relevant to a pocket-centric model.

**Requires** `structure_path` and `binding_site_residues` in manifest.

---

#### B4: Multi-Modal Ligand Similarity

**What it catches.** In protein-ligand binding datasets, a protein-space-clean split can leak heavily through the ligand axis. A model predicting binding affinity will exploit both protein-side and ligand-side information; DataSAIL's protein clustering protects only one axis.

**Method.**
1. For every SMILES in the dataset, compute Morgan fingerprint (radius 2, 2048 bits) using RDKit.
2. Compute Tanimoto coefficient between all train-test ligand pairs.
3. Flag pairs with Tanimoto > `tanimoto_threshold` (default 0.60) as B4 findings.
4. Additionally, run Bemis-Murcko scaffold extraction on all SMILES and flag train-test pairs sharing the same scaffold — even molecules with different substituents but identical cores are flagged.

**Severity.** HIGH.

**Requires** `ligand_column` in manifest.

---

### Layer C — Embedding Space (Novel)

#### C1: Embedding Proximity (Danger Quadrant)

**What it catches.** The central finding this tool exists to produce: test sequences that passed sequence identity filtering (DataSAIL would certify them) but sit close to training sequences in ESM-2 embedding space (the model will exploit that proximity). These are the cases where DataSAIL's certificate is wrong for the declared model architecture.

**Method.**
1. Run ESM-2 on all sequences (`esm2_t12_35M_UR50S` for speed; `esm2_t33_650M_UR50D` for high-accuracy runs; controlled by manifest `model_arch`).
2. L2-normalize all embedding vectors.
3. Build FAISS flat inner-product index over training embeddings.
4. For every test sequence, retrieve its nearest training neighbour and record: `(seq_identity, embedding_cosine)`.
5. Flag all test sequences in the danger quadrant: `seq_identity < seq_id_threshold` AND `embedding_cosine > emb_sim_threshold`.
6. Compute inflation estimate (see Stage 3).

**Severity.** HIGH; accompanied by quantified inflation estimate.

**The danger quadrant visualised:**

```
                    ← LOW seq. identity      HIGH →
HIGH embed. sim.  │  DataSAIL flags (B1)  │  DANGER ZONE (C1) ← model exploits
──────────────────┼──────────────────────┼─────────────────────
LOW embed. sim.   │  both agree: safe    │  fine (structures diverged)
```

Every C1 finding has `seq_identity < threshold` and `embedding_cosine > threshold` — the numerical proof in one evidence object that DataSAIL passed it while the model will exploit it.

---

#### C2: Pretraining Contamination

**What it catches.** ESM-2 was pretrained on approximately 250 million protein sequences from UniRef50. A test sequence that appears in the pretraining corpus will receive higher-quality embeddings from ESM-2 than a truly novel sequence, regardless of the downstream split. This is a source of inflation that no existing tool — including DataSAIL — checks.

**Method.**
1. Maintain a local MMseqs2 database of UniRef50 (cached on first download, ~40 GB compressed).
2. Run `mmseqs easy-search` of all test sequences against the UniRef50 database at ≥ 80% identity and ≥ 90% coverage.
3. Any test sequence with a UniRef50 hit above these thresholds is flagged as a pretraining-contaminated record.

**Severity.** HIGH. C2 findings do not mean the sequence is incorrectly in the test set — they mean the inflation of ESM-2's performance on this sequence should be attributed partly to pretraining familiarity, not only to the downstream model's learning.

**Computational note.** C2 is the most expensive check. It is opt-in via a manifest flag `run_pretraining_check: true` (default false). The UniRef50 database is downloaded once and cached in a Modal volume. Subsequent runs are fast.

---

### Layer D — Statistical & ML Leakage

#### D1: Target Leakage

**What it catches.** A feature that encodes the outcome or a collection artifact correlated with the label — a patient accession ID that correlates with positive class because all positives came from one lab's upload, a redundant column that is a direct transformation of the label, or a metadata field collected post-outcome.

**Method.**
1. For every non-target, non-ID column in the training set, compute:
   - Single-feature ROC-AUC against the target (for classification)
   - Mutual information score (sklearn `mutual_info_classif` or `mutual_info_regression`)
2. Flag any feature with AUC > 0.95 or normalized MI > 0.80.

**Severity.** CRITICAL. A feature with near-perfect predictive power on its own is almost certainly encoding the answer.

**Evidence.** Feature name, AUC value, MI score, a sample of the (feature value, label) pairs that expose the correlation.

---

#### D2: Preprocessing Leakage

**What it catches.** Scaling, normalization, or imputation that was fitted on the full dataset — including the test set — before splitting. If a researcher Z-scored an expression matrix globally and then split it, the test set's statistical moments will exactly match the global dataset's moments, which is impossible for a legitimate independent split.

**Method.**
1. For every numerical feature, compute (mean, std, 5th percentile, 50th percentile, 95th percentile) over the test split and over the whole dataset.
2. If any feature's test-split stats match the global stats to within float64 arithmetic precision (relative tolerance 1e-10), flag as preprocessing leakage.

**Severity.** HIGH. This is a near-exact numerical match, not a threshold — there is no ambiguity.

**Why this works.** Legitimate independent splits will always show statistical divergence from the global distribution, because they are subsets. If the test set's moments are identical to the global moments, the test set was used to fit the scaler before splitting.

---

#### D3: Group / Identity Leakage

**What it catches.** The same patient, organism, experimental subject, or biological replicate appearing in both the training set and the test set. Even if the individual records differ, the model memorizes entity-level features (a patient's baseline expression profile, an organism's phylogenetic signature) and exploits them.

**Method.**
1. Extract the set of unique values in `group_column` for training records.
2. Extract the set of unique values in `group_column` for test records.
3. Report the intersection size and the specific overlapping group IDs.

**Severity.** HIGH if any overlap exists.

**Requires** `group_column` in manifest.

---

#### D4: Temporal Leakage

**What it catches.** Any test sample whose timestamp predates training samples — future data in training, past data in test, or an incorrectly ordered time-series split.

**Method.**
1. Parse `time_column` as timestamps.
2. Verify: `max(train_timestamps) < min(test_timestamps)`.
3. Also scan for temporal gaps in the training data that might indicate cherry-picked time windows.
4. Flag any test record with `timestamp < max(train_timestamps)`.

**Severity.** HIGH.

**Requires** `time_column` in manifest.

---

#### D5: Batch / Confound Leakage

**What it catches.** Labels that are perfectly or strongly correlated with batch ID or collection site — the model learns the batch signature instead of the biological signal and reports high accuracy that evaporates on a new batch.

**Method.**
1. Compute Cramér's V between `batch_column` and `target_column` using the training set.
2. Also check cross-tabulation: if all positive samples come from one batch and all negatives from another, the Cramér's V will be near 1 but the cross-tab tells the story directly.

**Severity thresholds:**

| Cramér's V | Severity |
|---|---|
| > 0.70 | CRITICAL — batch almost determines label |
| 0.40 – 0.70 | HIGH |
| 0.20 – 0.40 | MEDIUM |
| < 0.20 | PASS |

**Requires** `batch_column` in manifest.

---

## 11. Stage 3 — Severity Quantification

Each finding object carries three quantitative fields beyond the binary flag:

### `contamination_frac`

The fraction of test records affected by this specific finding.

```
contamination_frac = |affected_test_records| / |test_set|
```

For A1: number of exact duplicates in test / test size.
For B1: number of test records in a straddle-cluster / test size.
For C1: number of test records in the danger quadrant / test size.

### `severity` tier

Determined per-check by thresholds documented in each check above (CRITICAL / HIGH / MEDIUM / LOW). The report-level severity is the maximum severity across all findings.

### `inflation_estimate` (C1-specific)

The novel quantification for embedding-space leakage:

1. For every test record, compute `d_min(t)` = minimum cosine distance to any training record.
2. Partition the test set into quartiles by `d_min`.
3. Compute mean model prediction confidence (or mean ESM-2 embedding similarity to label prototype if no trained model is provided) per quartile.
4. Fit a linear regression: `confidence ~ 1 / d_min`.
5. Report Pearson r and the regression slope as the inflation proxy.

A strong negative correlation (r < -0.5) between distance and confidence is the measurable signature of embedding-space leakage. The slope quantifies how much confidence inflates per unit of embedding proximity.

---

## 12. Stage 4 — Evidence Store

Every finding is a structured JSON object. The evidence store is the append-only collection of all findings from a single audit run.

```json
{
  "finding_id":         "uuid-v4",
  "check_id":           "C1",
  "severity":           "HIGH",

  "metric":             "embedding_cosine",
  "threshold":          0.90,
  "measured_value":     0.96,

  "train_record_id":    "seq_0042",
  "test_record_id":     "seq_1193",

  "evidence": {
    "seq_identity":     0.22,
    "embedding_cosine": 0.96,
    "tm_score":         null,
    "pocket_cosine":    null
  },

  "contamination_frac": 0.14,
  "inflation_estimate": 0.08,

  "repro_command": "python audit.py --check C1 --train seq_0042 --test seq_1193 --seed 42",
  "input_hash":    "sha256:a3f7c2...",
  "code_version":  "1.2.3"
}
```

**What makes a finding reviewer-grade:**

- `repro_command` can be pasted into a terminal to regenerate exactly this finding. A false positive can be investigated; a hallucinated finding cannot, because there is nothing to point at.
- `input_hash` is SHA-256 of the concatenated dataset + manifest bytes. A reviewer can verify the auditor ran on exactly the inputs they believe.
- `code_version` pins the auditor binary so the exact algorithm is identifiable.
- For C1 findings, `evidence.seq_identity` and `evidence.embedding_cosine` together constitute the falsification proof: the former shows DataSAIL would pass the pair; the latter shows the model exploits the proximity.

---

## 13. Stage 5 — Report & Narrator

### Structured JSON report

Generated deterministically from the evidence store. Same evidence store → same report, always.

```json
{
  "run_id":           "uuid-v4",
  "timestamp":        "2026-06-10T12:00:00Z",
  "input_hash":       "sha256:a3f7c2...",
  "code_version":     "1.2.3",
  "manifest_summary": { ... },

  "summary": {
    "total_findings":          23,
    "max_severity":            "HIGH",
    "overall_contamination_frac": 0.18,
    "checks_passed":           ["A1", "D4"],
    "checks_failed":           ["B1", "C1", "D5"],
    "checks_skipped":          ["B2 (no structure_path)", "B3 (no binding_site_residues)", "B4 (no ligand_column)"]
  },

  "findings": [ ... ]
}
```

### HTML / PDF report

Rendered from the structured JSON. Organized by severity tier. Includes per-check result tables, the danger-quadrant scatter plot for C1, and a contamination fraction bar per check.

### LLM narrator (optional, read-only)

A single `claude-haiku-4-5` call. System prompt:

```
You are a scientific writing assistant. You will be given a JSON object
containing data leakage audit findings for a biological ML dataset.
Write a plain-English summary of the findings for a researcher audience.
Do not introduce any claim that is not present in the JSON.
Do not assess the overall quality of the dataset beyond what the findings state.
Do not speculate about causes of findings not described in the evidence fields.
```

The narrator receives only the findings JSON. It has no access to the dataset, no internet access, and no path to write a finding. Its output is a prose paragraph for the report's executive summary section. Removing the narrator does not change any finding in the report.

### Scope honesty

Every report includes this statement verbatim in the summary section:

> *This report detects leakage of the specific types implemented in checks A1, A2, B1–B4, C1–C2, and D1–D5. A PASS result on all implemented checks does not certify the dataset as free of all possible leakage. Leakage is an open-ended problem space. Skipped checks are listed with reasons.*

---

## 14. Tech Stack

### Frontend

| Component | Technology |
|---|---|
| UI framework | Next.js + Tailwind CSS |
| Upload interface | Multi-file drag-and-drop; manifest builder form |
| Job status | Supabase Realtime subscription on job table |
| Report viewer | Dynamic report renderer from findings JSON |
| Evidence explorer | Drill-down table: click a finding to see record IDs, metrics, repro command |
| Auth | Supabase Auth (email or GitHub OAuth) |

### Backend API

| Component | Technology |
|---|---|
| API layer | FastAPI (Python) |
| Input validation | Pydantic models for manifest schema |
| Job queueing | Supabase Postgres table: `(id, status, input_path, manifest, result_path, created_at)` |
| File storage | Supabase Storage buckets: `datasets/` and `results/` |
| Webhook trigger | Supabase database webhook → Modal function on `INSERT` to jobs table |

### Worker (Python, Docker, GPU optional)

| Check | Library / Tool | Notes |
|---|---|---|
| A1 | `hashlib` (stdlib) | SHA-256, no dependencies |
| A2 | `datasketch` | MinHash LSH, CPU-fast |
| B1 | MMseqs2 | CLI binary, pre-installed in Docker image |
| B2 | Foldseek | CLI binary; needs PDB files |
| B3 | `fair-esm` (Meta) | ESM-2 pocket embeddings |
| B4 | RDKit | Morgan fingerprints; Bemis-Murcko scaffolds |
| C1 | `fair-esm` + `faiss-gpu` | ESM-2 full-chain; FAISS nearest-neighbour |
| C2 | MMseqs2 + UniRef50 cache | Expensive; opt-in flag |
| D1 | `scikit-learn` | `mutual_info_classif`, `roc_auc_score` |
| D2 | `numpy` | Distribution fingerprint comparison |
| D3 | Python `set` | Set intersection on group column |
| D4 | `pandas` | Timestamp parsing and ordering check |
| D5 | `scipy.stats` | Cramér's V from contingency table |

**ESM-2 model selection by manifest `model_arch`:**

| `model_arch` value | ESM-2 model | Hardware | Speed |
|---|---|---|---|
| `esm2` (quick) | `esm2_t12_35M_UR50S` | CPU | ~5 min / 1k seqs |
| `esm2` (full) | `esm2_t33_650M_UR50D` | GPU (A10G) | ~3 min / 1k seqs |
| `raw_sequence` | MinHash only | CPU | Very fast |
| `structure` | Foldseek only | CPU | Requires PDBs |

---

## 15. Deployment Architecture

### Pattern: async job queue

The compute-heavy checks (ESM-2, MMseqs2, Foldseek) cannot run in a request/response cycle. The architecture is upload → enqueue → worker runs → result written back → frontend polls.

```
User browser
  │
  │  POST /upload (multipart: dataset + manifest)
  ▼
Next.js API route
  │  1. Validate manifest
  │  2. Upload files to Supabase Storage (datasets/<job_id>/)
  │  3. INSERT job row: {id, status: "queued", input_path, manifest}
  ▼
Supabase DB
  │  database webhook fires on INSERT
  ▼
Modal.com function (Python worker)
  │  1. Download files from Supabase Storage
  │  2. Run all applicable checks (Stage 1 → Stage 2 → Stage 3 → Stage 4)
  │  3. Write findings JSON + HTML report to Supabase Storage (results/<job_id>/)
  │  4. UPDATE job row: {status: "done", result_path}
  ▼
Frontend (polling via Supabase Realtime)
  │  Status: queued → running → done
  ▼
Report viewer
```

### Tiered execution

| Tier | Checks included | Typical runtime | Hardware |
|---|---|---|---|
| Quick audit | A1, A2, B1, D1–D5 | 2–5 min | CPU |
| Standard audit | + B2, B3, B4, C1 | 10–20 min | GPU optional |
| Full audit | + C2 (pretraining) | 30–60 min | GPU recommended |

Users select tier at submission. The quick audit is suitable for initial screening; the full audit is for a dataset being submitted to a journal or benchmark.

### Infrastructure costs (approximate, Modal.com)

- CPU worker (A2, B1, D1–D5): ~$0.03 per run
- GPU worker with ESM-2 (C1, B3): ~$0.30–0.80 per run depending on dataset size
- C2 (UniRef50 search): ~$0.50–1.50 per run; cached after first UniRef50 download
- UniRef50 Modal volume: ~$4/month storage

---

## 16. Empirical Falsification Protocol

This is the experimental protocol that proves DataSAIL is sometimes wrong for a specific training regime. It is publishable methodology, not just a tool feature.

**Given:** any dataset that was split with DataSAIL (or any sequence identity-based splitter).

**Step 1.** Run C1 on the existing split. Identify the danger-quadrant test sequences: `seq_identity < threshold` (DataSAIL passed) and `embedding_cosine > threshold` (model exploits proximity).

**Step 2.** Train a model using ESM-2 embeddings on the DataSAIL split. Record per-sample test predictions and confidences.

**Step 3.** Partition the test set into two groups:
- Near: test sequences in the danger quadrant (high embedding similarity to training)
- Far: all other test sequences

**Step 4.** Compare mean performance (accuracy, AUC, or domain-appropriate metric) between Near and Far groups.

**Expected result if DataSAIL's split was insufficient:** the Near group performs significantly better than the Far group. This is the measurable leakage signal — the model is exploiting embedding proximity that DataSAIL's sequence identity clustering could not see.

**Null hypothesis to reject:** Near performance ≈ Far performance (the split is adequate for this model architecture).

**What this proves:** not that DataSAIL is wrong in general, but that its validity certificate is conditional on the similarity metric matching what the model computes. For raw sequence models, sequence identity is a reasonable proxy. For embedding-based models, it is insufficient — and the gap is quantifiable.

---

*All checks are deterministic and reproducible. All findings point at specific records. The LLM narrator, if used, reads evidence only — it has no path to invent a claim. A PASS result on all implemented checks is scoped to those checks only, not a general certificate of dataset cleanliness.*
