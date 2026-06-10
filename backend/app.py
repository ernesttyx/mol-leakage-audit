"""
app.py — the tiny FastAPI backend AND web-app server.

Run the whole thing with ONE command:
    uvicorn backend.app:app --reload
Then open ONE url in your browser:
    http://localhost:8000

That page (served from frontend/) lets you drop in a CSV and see the verdict.
The same server also exposes:
    POST /audit   — the JSON API the page calls
    GET  /health  — a liveness probe
    GET  /docs    — FastAPI's auto-generated API tester
"""

import io
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.parse import split_frames
from backend.adapt import prepare
from backend.report import audit
from backend.checks.scaffold import scaffold_split
from backend.checks.baseline import dumb_baseline

app = FastAPI(title="audit — molecular dataset leakage smoke detector")

# CORS stays permissive so the /docs tester and any external page still work.
# It is no longer REQUIRED (the page is now same-origin), but it's harmless for local use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "message": "audit backend is running"}


def _read_and_prepare(contents: bytes, smiles_col, label_col, split_col, make_split):
    """Shared: bytes -> standardized df + adapter notes. Column args may be '' (=auto)."""
    df = pd.read_csv(io.BytesIO(contents))
    clean, notes = prepare(
        df,
        smiles_col=smiles_col or None,
        label_col=label_col or None,
        split_col=split_col or None,
        make_split_method=make_split or "random",
    )
    return clean, notes


@app.post("/audit")
async def run_audit(
    file: UploadFile = File(...),
    smiles_col: str = "",   # blank = auto-detect (handles 'mol', etc.)
    label_col: str = "",    # blank = auto-detect (handles 'Class', 'p_np', ...)
    split_col: str = "",    # blank = auto-detect; if none exists, one is created
    make_split: str = "random",
):
    """Accept an uploaded CSV (ANY common molecular format), run the leakage audit.

    The adapter auto-detects columns, handles regression labels, and CREATES a split
    if the file has none — reporting every such decision in `report['notes']`.
    """
    try:
        contents = await file.read()
        cleaned, notes = _read_and_prepare(contents, smiles_col, label_col, split_col, make_split)
        if cleaned.empty:
            return {"error": "No usable rows after parsing — check your SMILES and columns."}
        report = audit(cleaned)
        report["notes"] = notes  # transparency: what the adapter did
        return report
    except Exception as exc:  # noqa: BLE001 — surface a friendly message to the UI
        return {"error": f"Could not audit this CSV: {exc}"}


@app.post("/fix")
async def fix_split(
    file: UploadFile = File(...),
    smiles_col: str = "",   # blank = auto-detect
    label_col: str = "",
    split_col: str = "",
):
    """
    The 'and here's the cure' endpoint.

    Re-split the dataset by scaffold (whole scaffold groups go entirely to train OR
    test, never both), then prove the fix worked by running the dumb baseline BEFORE
    and AFTER. A leaky split scores high; the honest split should score lower. That
    drop IS the proof. Returns both scores plus the corrected CSV to download.
    """
    try:
        contents = await file.read()
        cleaned, _notes = _read_and_prepare(contents, smiles_col, label_col, split_col, "random")
        if cleaned.empty:
            return {"error": "No usable rows after parsing — check your SMILES and columns."}

        # BEFORE: dumb baseline on the user's original split.
        train_before, test_before = split_frames(cleaned)
        before = dumb_baseline(train_before, test_before)

        # AFTER: re-split by scaffold, then re-run the same dumb baseline.
        fixed = scaffold_split(cleaned)
        train_after, test_after = split_frames(fixed)
        after = dumb_baseline(train_after, test_after)

        # Build a downloadable CSV of the corrected split (smiles/label/split).
        download = fixed.rename(columns={"smiles_canonical": "smiles"})[
            ["smiles", "label", "split"]
        ]
        csv_text = download.to_csv(index=False)

        return {
            "before": {"metric_name": before["metric_name"], "score": before["score"]},
            "after": {"metric_name": after["metric_name"], "score": after["score"]},
            "improved": after["score"] < before["score"],
            "n_train": int(len(train_after)),
            "n_test": int(len(test_after)),
            "csv": csv_text,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Could not fix this split: {exc}"}


# --- serve the web page -------------------------------------------------------
# Mount the frontend folder at the site root. This MUST come AFTER the routes above,
# so /audit and /health win; everything else (/, /app.js, /style.css) is served as a
# static file. html=True makes "/" return index.html automatically.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
