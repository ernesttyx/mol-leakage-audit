// app.js — Day 4. Sends the uploaded CSV to the Python backend and renders the report.
// This is the entire front-end logic. No framework needed for v1.

// Relative URL: the page is now served BY the same FastAPI app, so "/audit" just works
// whether you're on localhost:8000 or a deployed host. No CORS, no hardcoded port.
const API = "/audit";

document.getElementById("runBtn").addEventListener("click", runAudit);
document.getElementById("fixBtn").addEventListener("click", fixSplit);

async function runAudit() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) {
    alert("Pick a CSV first.");
    return;
  }

  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  btn.textContent = "Auditing…";
  try {
    const form = new FormData();
    form.append("file", fileInput.files[0]);

    const res = await fetch(API, { method: "POST", body: form });
    const report = await res.json();

    if (report.error) {
      alert(report.error);
      return;
    }
    render(report);
  } catch (err) {
    alert(
      "Couldn't reach the backend. Is it running?\n" +
        "Start it with:  uvicorn backend.app:app --reload\n\n" +
        err
    );
  } finally {
    btn.disabled = false;
    btn.textContent = "Run audit";
  }
}

async function fixSplit() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) {
    alert("Pick a CSV first.");
    return;
  }

  const btn = document.getElementById("fixBtn");
  btn.disabled = true;
  btn.textContent = "Fixing…";
  try {
    const form = new FormData();
    form.append("file", fileInput.files[0]);

    const res = await fetch("/fix", { method: "POST", body: form });
    const result = await res.json();

    if (result.error) {
      alert(result.error);
      return;
    }
    renderFix(result);
  } catch (err) {
    alert(
      "Couldn't reach the backend. Is it running?\n" +
        "Start it with:  uvicorn backend.app:app --reload\n\n" +
        err
    );
  } finally {
    btn.disabled = false;
    btn.textContent = "Fix my split";
  }
}

function renderFix(result) {
  document.getElementById("fixResult").hidden = false;

  const before = result.before.score;
  const after = result.after.score;
  const metric = result.after.metric_name;

  document.getElementById("fixScores").innerHTML = `
    <div class="fix-card before">
      <div class="fix-big">${before.toFixed(2)}</div>
      <div class="fix-label">your split (${metric})</div>
    </div>
    <div class="fix-arrow">→</div>
    <div class="fix-card after ${result.improved ? "good" : ""}">
      <div class="fix-big">${after.toFixed(2)}</div>
      <div class="fix-label">scaffold split (${metric})</div>
    </div>`;

  drawCollapseChart(before, after, metric);

  document.getElementById("fixMsg").textContent = result.improved
    ? `The dumb baseline dropped from ${before.toFixed(2)} to ${after.toFixed(2)} ` +
      `(new split: ${result.n_train} train / ${result.n_test} test). That drop is the proof ` +
      `the corrected split is harder to game by pure memorization.`
    : `The baseline did NOT drop (${before.toFixed(2)} → ${after.toFixed(2)}). Either your ` +
      `original split was already reasonable, or this dataset is too small/analog-heavy for a ` +
      `scaffold split to help. Download and inspect before trusting it.`;

  // Wire up the download link with the corrected CSV as an in-browser blob.
  const blob = new Blob([result.csv], { type: "text/csv" });
  document.getElementById("downloadLink").href = URL.createObjectURL(blob);
}

// --- the collapse bar chart -------------------------------------------------
// Two bars — the dumb baseline on YOUR split vs on a clean scaffold split — drawn
// against two reference lines: CHANCE (what a no-signal split should score) and the
// LEAKING threshold. The whole leakage argument in one picture: a tall "your split"
// bar above the leaking line that COLLAPSES toward chance once the split is fixed.
function drawCollapseChart(before, after, metric) {
  const isR2 = metric === "R2";
  // Axis + reference lines per metric. AUROC: chance 0.5, leaking 0.85. R2: chance 0, leaking 0.70.
  const axisMin = isR2 ? 0 : 0.5;     // floor of the plot (clamp negatives/below-chance here)
  const axisMax = 1;                  // both metrics top out at 1.0
  const chance = isR2 ? 0 : 0.5;
  const leaking = isR2 ? 0.7 : 0.85;

  const span = axisMax - axisMin;
  const toPct = (v) => Math.max(0, Math.min(100, ((v - axisMin) / span) * 100));

  const bar = (score, label, cls) => {
    const h = toPct(score);
    const hot = score >= leaking; // above the leaking line = red
    return `
      <div class="cc-col">
        <div class="cc-track">
          <div class="cc-bar ${cls} ${hot ? "hot" : ""}" style="height:${h}%">
            <span class="cc-val">${score.toFixed(2)}</span>
          </div>
        </div>
        <div class="cc-xlabel">${label}</div>
      </div>`;
  };

  document.getElementById("collapseChart").innerHTML = `
    <div class="chart-title">Memorization baseline (${metric}) — your split vs a clean scaffold split</div>
    <div class="cc-plot">
      <div class="cc-line cc-leaking" style="bottom:${toPct(leaking)}%"><span>leaking ≥ ${leaking}</span></div>
      <div class="cc-line cc-chance"  style="bottom:${toPct(chance)}%"><span>chance ${chance.toFixed(2)}</span></div>
      ${bar(before, "your split", "before")}
      ${bar(after, "scaffold split", "after")}
    </div>`;
}

const VERDICT_STYLE = {
  CLEAN: { icon: "✅", cls: "clean" },
  SUSPECT: { icon: "⚠️", cls: "suspect" },
  LEAKING: { icon: "❌", cls: "leaking" },
};

function render(report) {
  document.getElementById("results").hidden = false;

  // --- verdict chip ---------------------------------------------------------
  const v = VERDICT_STYLE[report.verdict] || VERDICT_STYLE.SUSPECT;
  const verdictEl = document.getElementById("verdict");
  verdictEl.textContent = `${v.icon} ${report.verdict}`;
  verdictEl.className = `verdict ${v.cls}`;

  // --- adapter notes (what the tool did to your file) -----------------------
  renderNotes(report.notes);

  // --- summary --------------------------------------------------------------
  document.getElementById("summary").textContent = report.summary;

  // --- one card per check ---------------------------------------------------
  const c = report.checks;
  const cards = [
    { title: "Exact duplicates", big: pct(c.duplicates.fraction_leaked), msg: c.duplicates.message },
    { title: "Near-neighbor (>0.8)", big: pct(c.similarity.fraction_above_0_8), msg: c.similarity.message },
    { title: "Shared scaffolds", big: pct(c.scaffold.fraction_shared), msg: c.scaffold.message },
    { title: `Dumb baseline (${c.baseline.metric_name})`, big: c.baseline.score.toFixed(2), msg: c.baseline.message },
  ];
  document.getElementById("checks").innerHTML = cards
    .map(
      (k) => `
      <div class="check-card">
        <div class="check-big">${k.big}</div>
        <div class="check-title">${k.title}</div>
        <div class="check-msg">${k.msg}</div>
      </div>`
    )
    .join("");

  // --- similarity histogram (10 bins, 0.0 .. 1.0) ---------------------------
  drawHistogram(c.similarity.similarities || []);
}

function renderNotes(notes) {
  const el = document.getElementById("notes");
  if (!el) return;
  if (!notes) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const createdSplit = String(notes.split_source || "").startsWith("NO split");
  el.className = "notes" + (createdSplit ? " warn" : "");
  el.innerHTML =
    `<strong>What the tool read from your file:</strong> ` +
    `SMILES column <code>${notes.smiles_col}</code>, label <code>${notes.label_col}</code> ` +
    `(${notes.label_type}). Kept ${notes.n_kept} rows ` +
    `(${notes.n_train} train / ${notes.n_test} test). ` +
    (createdSplit
      ? `⚠️ <strong>${notes.split_source}</strong>`
      : `Split: ${notes.split_source}.`);
}

function pct(fraction) {
  return `${Math.round(fraction * 1000) / 10}%`;
}

function drawHistogram(values) {
  const bins = new Array(10).fill(0);
  for (const s of values) {
    let i = Math.floor(s * 10);
    if (i > 9) i = 9; // a similarity of exactly 1.0 lands in the last bin
    if (i < 0) i = 0;
    bins[i] += 1;
  }
  const max = Math.max(1, ...bins);
  const chart = document.getElementById("chart");
  chart.innerHTML =
    `<div class="chart-title">Test→train nearest-neighbor similarity (a wall near 1.0 = leaking)</div>` +
    `<div class="bars">` +
    bins
      .map((count, i) => {
        const height = Math.round((count / max) * 100);
        const lo = (i / 10).toFixed(1);
        return `<div class="bar" title="${lo}–${(i / 10 + 0.1).toFixed(1)}: ${count}">
                  <div class="bar-fill" style="height:${height}%"></div>
                  <div class="bar-label">${lo}</div>
                </div>`;
      })
      .join("") +
    `</div>`;
}
