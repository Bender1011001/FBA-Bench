#!/usr/bin/env python3
"""
Static site generator for GitHub Pages (docs/).

This repo previously generated a fully static leaderboard table by embedding rows into HTML.
For live benchmark runs we instead serve a dynamic page that fetches:
- docs/api/leaderboard.json
- docs/api/live.json

Those JSON files are updated locally by tools/watch_and_build.py (and can be committed to
publish on GitHub Pages).
"""

from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).parent
DOCS_DIR = ROOT_DIR / "docs"
INDEX_PATH = DOCS_DIR / "index.html"
DOCS_HTML_PATH = DOCS_DIR / "docs.html"


def write_index_html() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>FBA-Bench | Live Leaderboard</title>
    <meta name="description" content="Live benchmark leaderboard for AI business agents under recession conditions." />
    <link rel="stylesheet" href="style.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div class="bg-grid" aria-hidden="true"></div>

    <header class="wrap header">
      <div class="brand">
        <div class="logo">FBA</div>
        <div class="brand-text">
          <div class="title">FBA-Bench</div>
          <div class="sub">Live leaderboard for AI business agents</div>
        </div>
      </div>

      <div class="right">
        <div id="liveBadge" class="badge badge-live hidden">LIVE BENCHMARK RUNNING</div>
        <div class="meta">
          <div class="meta-k">Last updated</div>
          <div id="lastUpdated" class="meta-v">Loading...</div>
        </div>
      </div>
    </header>

    <main class="wrap">
      <section class="hero">
        <h1>GPT-5.2 vs DeepSeek R1: The Bankruptcy Test</h1>
        <p class="hook">
          We are not testing if they can write poetry. We are testing if they can survive a six-month recession.
          <span id="statusLine">Status: awaiting data.</span>
        </p>
        <div class="chips">
          <a class="chip" href="api/leaderboard.json" target="_blank" rel="noreferrer">leaderboard.json</a>
          <a class="chip" href="api/live.json" target="_blank" rel="noreferrer">live.json</a>
          <a class="chip" href="docs.html">docs</a>
          <a class="chip" href="https://github.com/Bender1011001/FBA-Bench-Enterprise" target="_blank" rel="noreferrer">github</a>
        </div>
      </section>

      <section class="cards">
        <div class="card">
          <div class="card-k">Run</div>
          <div id="runId" class="card-v">--</div>
        </div>
        <div class="card">
          <div class="card-k">Tier</div>
          <div id="tier" class="card-v">--</div>
        </div>
        <div class="card">
          <div class="card-k">Avg quality</div>
          <div id="avgQuality" class="card-v">--</div>
        </div>
        <div class="card">
          <div class="card-k">Avg success</div>
          <div id="avgSuccess" class="card-v">--</div>
        </div>
        <div class="card">
          <div class="card-k">Tokens</div>
          <div id="totalTokens" class="card-v">--</div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-h">
          <div class="panel-title">Global Leaderboard</div>
          <div id="panelNote" class="panel-note">Class of 2026 models, Tier-2 prompts.</div>
        </div>

        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Model</th>
                <th>Provider</th>
                <th>Quality</th>
                <th>Success</th>
                <th>Avg RT</th>
                <th>Tokens</th>
              </tr>
            </thead>
            <tbody id="rows">
              <tr><td colspan="7" class="muted">Loading...</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="footer">
        <div>FBA-Bench Enterprise. Built for the era of agentic AI.</div>
        <div class="muted">If the leaderboard looks stale, the publisher is not running or results are not deployed.</div>
      </footer>
    </main>

    <script>
      async function fetchJson(url) {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(url + " " + res.status);
        return await res.json();
      }

      function fmtPct(x) {
        if (typeof x !== "number") return "--";
        return Math.round(x * 100) + "%";
      }

      function fmtNum(x) {
        if (typeof x !== "number") return "--";
        return x.toLocaleString(undefined, { maximumFractionDigits: 3 });
      }

      function fmtSec(x) {
        if (typeof x !== "number") return "--";
        return x.toFixed(2) + "s";
      }

      function qualityClass(q) {
        if (typeof q !== "number") return "q-neutral";
        if (q >= 0.90) return "q-good";
        if (q >= 0.80) return "q-warn";
        return "q-bad";
      }

      function render(lb, live) {
        const rankings = (lb && lb.rankings) ? lb.rankings : [];

        document.getElementById("lastUpdated").textContent = (lb && lb.generated_at) ? lb.generated_at : "Unknown";
        document.getElementById("runId").textContent = (lb && lb.active_run && lb.active_run.run_id) ? lb.active_run.run_id : "--";
        document.getElementById("tier").textContent = (lb && lb.active_run && lb.active_run.tier) ? lb.active_run.tier : "--";
        document.getElementById("avgQuality").textContent = (lb && lb.summary) ? fmtNum(lb.summary.avg_quality_score) : "--";
        document.getElementById("avgSuccess").textContent = (lb && lb.summary) ? fmtPct(lb.summary.avg_success_rate) : "--";
        document.getElementById("totalTokens").textContent = (lb && lb.summary) ? fmtNum(lb.summary.total_tokens) : "--";

        const active = !!(live && live.active);
        const badge = document.getElementById("liveBadge");
        if (active) badge.classList.remove("hidden");
        else badge.classList.add("hidden");

        const statusLine = document.getElementById("statusLine");
        if (live && typeof live.status === "string") {
          statusLine.textContent = "Current Status: " + live.status + " (" + (live.completed || 0) + "/" + (live.total || 0) + ")";
        } else {
          statusLine.textContent = "Status: awaiting data.";
        }

        const rows = document.getElementById("rows");
        if (!rankings.length) {
          rows.innerHTML = '<tr><td colspan="7" class="muted">No data yet.</td></tr>';
          return;
        }

        rows.innerHTML = rankings.map(r => {
          const q = (typeof r.quality_score === "number") ? r.quality_score : 0;
          const sr = (typeof r.success_rate === "number") ? r.success_rate : 0;
          return `
            <tr>
              <td><span class="rank">${r.rank}</span></td>
              <td class="mono">${(r.model_slug || r.model_name || "unknown")}</td>
              <td>${(r.provider || "unknown")}</td>
              <td><span class="pill ${qualityClass(q)}">${fmtNum(q)}</span></td>
              <td><span class="pill ${sr >= 1.0 ? "q-good" : sr >= 0.8 ? "q-warn" : "q-bad"}">${fmtPct(sr)}</span></td>
              <td>${fmtSec(r.avg_response_time)}</td>
              <td class="mono">${fmtNum(r.total_tokens)}</td>
            </tr>
          `;
        }).join("");
      }

      async function tick() {
        try {
          const [lb, live] = await Promise.all([
            fetchJson("api/leaderboard.json"),
            fetchJson("api/live.json").catch(() => null),
          ]);
          render(lb, live);
        } catch (e) {
          const rows = document.getElementById("rows");
          rows.innerHTML = '<tr><td colspan="7" class="muted">Failed to load leaderboard.json</td></tr>';
        }
      }

      tick();
      setInterval(tick, 10000);
    </script>
  </body>
</html>
"""

    INDEX_PATH.write_text(html, encoding="utf-8")


def write_docs_html() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>FBA-Bench | Docs</title>
    <link rel="stylesheet" href="style.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div class="bg-grid" aria-hidden="true"></div>
    <main class="wrap">
      <section class="hero">
        <h1>Docs</h1>
        <p class="hook">Operator notes and technical documentation.</p>
        <div class="chips">
          <a class="chip" href="index.html">leaderboard</a>
          <a class="chip" href="API.md">api.md</a>
          <a class="chip" href="architecture.md">architecture.md</a>
          <a class="chip" href="deployment.md">deployment.md</a>
          <a class="chip" href="README.md">docs/readme.md</a>
        </div>
      </section>
    </main>
  </body>
</html>
"""
    DOCS_HTML_PATH.write_text(html, encoding="utf-8")


def main() -> int:
    write_index_html()
    write_docs_html()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
