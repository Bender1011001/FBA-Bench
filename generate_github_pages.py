#!/usr/bin/env python3
"""
Static site generator for GitHub Pages (docs/).

This repo previously generated a fully static leaderboard table by embedding rows into HTML.
For live benchmark runs we instead serve a dynamic page that fetches:
- docs/api/leaderboard.json
- docs/api/live.json

Those JSON files are updated locally by tools/watch_and_build.py (and can be committed to
publish on GitHub Pages).

For CI/GitHub Pages builds, we prefer checked-in artifacts under public_results/ so the
site can ship with non-empty snapshots without running expensive benchmarks in CI.
"""

from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


ROOT_DIR = Path(__file__).parent
DOCS_DIR = ROOT_DIR / "docs"
DOCS_API_DIR = DOCS_DIR / "api"
INDEX_PATH = DOCS_DIR / "index.html"
DOCS_HTML_PATH = DOCS_DIR / "docs" / "index.html"
CONTACT_PATH = DOCS_DIR / "contact.html"

DEFAULT_SITE_URL = "https://fbabench.com"


def _get_contact_fallback_email() -> str:
    # Deprecated: we intentionally do not embed real emails in the static site.
    # Keep this for backward compatibility if older content still references it.
    return "contact@fbabench.com"


def _site_url() -> str:
    # Used for canonical URLs and sitemap. Override for staging/dev via env var.
    return os.environ.get("FBA_BENCH_SITE_URL", DEFAULT_SITE_URL).rstrip("/")


def _json_escape(s: str) -> str:
    # Minimal JSON string escape for safe embedding in JSON-LD.
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _seo_tags(*, title: str, description: str, canonical_path: str, theme_color: str, icon_href: str) -> str:
    base = _site_url()
    canonical_url = f"{base}{canonical_path}"
    json_ld = (
        '{'
        '"@context":"https://schema.org",'
        '"@type":"WebSite",'
        f'"name":"{_json_escape("FBA-Bench")}",'
        f'"url":"{_json_escape(base + "/")}"'
        "}"
    )

    # Keep the set small but complete: canonical + OG + Twitter + JSON-LD.
    return f"""
    <meta name="description" content="{description}" />
    <meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1" />
    <meta name="theme-color" content="{theme_color}" />
    <link rel="canonical" href="{canonical_url}" />
    <link rel="icon" href="{icon_href}" type="image/svg+xml" />
    <meta property="og:site_name" content="FBA-Bench" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{description}" />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="{canonical_url}" />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="{title}" />
    <meta name="twitter:description" content="{description}" />
    <script type="application/ld+json">{json_ld}</script>""".rstrip()


def write_seo_files() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    base = _site_url()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    robots = f"""User-agent: *
Allow: /

Sitemap: {base}/sitemap.xml
"""
    (DOCS_DIR / "robots.txt").write_text(robots, encoding="utf-8")

    # Include only real HTML entry points.
    url_entries: list[tuple[str, str, str]] = [
        ("/", "daily", "1.0"),
        ("/docs/", "weekly", "0.6"),
        ("/sim-theater.html", "hourly", "0.5"),
        ("/contact.html", "monthly", "0.3"),
    ]
    if not (DOCS_DIR / "sim-theater.html").exists():
        url_entries = [e for e in url_entries if e[0] != "/sim-theater.html"]

    urls_xml = "\n".join(
        f"""  <url>
    <loc>{base}{path}</loc>
    <lastmod>{now}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{prio}</priority>
  </url>"""
        for path, freq, prio in url_entries
    )
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls_xml}
</urlset>
"""
    (DOCS_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_index_html() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    seo = _seo_tags(
        title="FBA-Bench | Live Leaderboard",
        description="Live benchmark leaderboard for AI business agents under recession conditions.",
        canonical_path="/",
        theme_color="#0a0a0a",
        icon_href="favicon.svg",
    )

    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>FBA-Bench | Live Leaderboard</title>
""" + seo + """
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
        <h1 id="heroTitle">FBA-Bench Leaderboard</h1>
        <p class="hook">
          <span id="heroHook">Loading benchmark mode...</span>
          <span id="statusLine">Status: awaiting data.</span>
        </p>
        <div class="chips">
          <a class="chip" href="?mode=agentic">agentic</a>
          <a class="chip" href="?mode=prompt">prompt</a>
          <a class="chip" href="api/leaderboard.json" target="_blank" rel="noreferrer">leaderboard.json</a>
          <a class="chip" href="api/live.json" target="_blank" rel="noreferrer">live.json</a>
          <a class="chip" href="docs/">docs</a>
          <a class="chip" href="docs/#sponsorship.md">sponsor</a>
          <a class="chip" href="contact.html">message me</a>
          <a class="chip" href="https://github.com/Bender1011001/FBA-Bench-Enterprise" target="_blank" rel="noreferrer">github</a>
        </div>
      </section>

      <section class="support">
        <div class="support-content">
          <h2>Support the Research</h2>
          <p>
            The benchmark is expensive to run (tokens + infra). If you want the leaderboard updated more often or want a
            specific model evaluated, consider sponsoring compute credits or a run.
          </p>
          <div class="crypto-grid">
            <div class="crypto-card">
              <div class="crypto-label">Monero (XMR)</div>
              <code class="crypto-addr">83YhKW5PzCSdkeT6fQ6g5kZ7159AoXDqjCS835rcdPkuh4AEd52t79vDR9kff7A6tT46uzAzYZku8dcarqvJH1v5SQ6emDv</code>
            </div>
            <div class="crypto-card">
              <div class="crypto-label">Bitcoin (BTC)</div>
              <code class="crypto-addr">bc1qg607xtepk96tgn94lewgfe68gn0r3m4x6nz7n5</code>
            </div>
            <div class="crypto-card">
              <div class="crypto-label">Ethereum (ETH / ERC-20)</div>
              <code class="crypto-addr">0x8db7b843417D4744b8d81395aCDe817cE0f4A32B</code>
            </div>
            <div class="crypto-card">
              <div class="crypto-label">Litecoin (LTC)</div>
              <code class="crypto-addr">ltc1q63j9d7l73t6k5e6etwyxfgd4kghf6ssj6cuv5e</code>
            </div>
          </div>
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
          <div class="card-k" id="metricK1">Avg profit</div>
          <div id="metricV1" class="card-v">--</div>
        </div>
        <div class="card">
          <div class="card-k" id="metricK2">Avg ROI</div>
          <div id="metricV2" class="card-v">--</div>
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
                <th id="colK1">Net Profit</th>
                <th id="colK2">ROI</th>
                <th id="colK3">Calls</th>
                <th id="colK4">Avg Call</th>
                <th>Tokens</th>
              </tr>
            </thead>
            <tbody id="rows">
              <tr><td colspan="8" class="muted">Loading...</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <footer class="footer">
        <div class="footer-links">
          <a href="docs/#terms.md">Terms</a>
          <a href="docs/#privacy.md">Privacy</a>
          <a href="docs/#disclaimer.md">Disclaimer</a>
          <a href="docs/#sponsorship.md">Sponsor</a>
          <a href="contact.html">Message me</a>
        </div>
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
        return x.toFixed(1) + "%";
      }

      function fmtPctFraction(x) {
        if (typeof x !== "number") return "--";
        return (x * 100).toFixed(1) + "%";
      }

      function fmtNum(x) {
        if (typeof x !== "number") return "--";
        return x.toLocaleString(undefined, { maximumFractionDigits: 3 });
      }

      function fmtSec(x) {
        if (typeof x !== "number") return "--";
        return x.toFixed(2) + "s";
      }

      function fmtMoney(x) {
        if (typeof x !== "number") return "--";
        const sign = x >= 0 ? "+" : "-";
        const abs = Math.abs(x);
        return sign + "$" + abs.toLocaleString(undefined, { maximumFractionDigits: 2 });
      }

      function profitClass(x) {
        if (typeof x !== "number") return "q-neutral";
        if (x > 0.01) return "q-good";
        if (x < -0.01) return "q-bad";
        return "q-warn";
      }

      function applyModeUI(mode) {
        const heroTitle = document.getElementById("heroTitle");
        const heroHook = document.getElementById("heroHook");
        const panelNote = document.getElementById("panelNote");
        const colK1 = document.getElementById("colK1");
        const colK2 = document.getElementById("colK2");
        const colK3 = document.getElementById("colK3");
        const colK4 = document.getElementById("colK4");

        if (mode === "prompt") {
          if (heroTitle) heroTitle.textContent = "Tier-2 Prompt Battery (Fast)";
          if (heroHook) heroHook.textContent = "Scoring structured decision quality and format reliability. No tools. No memory. No scaffolding.";
          if (panelNote) panelNote.textContent = "Tier-2 prompt suite (cheap + reproducible).";
          if (colK1) colK1.textContent = "Quality";
          if (colK2) colK2.textContent = "Success";
          if (colK3) colK3.textContent = "Avg RT";
          if (colK4) colK4.textContent = "Errors";
        } else {
          if (heroTitle) heroTitle.textContent = "The Bankruptcy Test (Agentic)";
          if (heroHook) heroHook.textContent = "Long-horizon e-commerce sim under shocks: can the model stay solvent across months of decisions?";
          if (panelNote) panelNote.textContent = "Tick-based simulation, scored by profit and survival under compounding consequences.";
          if (colK1) colK1.textContent = "Net Profit";
          if (colK2) colK2.textContent = "ROI";
          if (colK3) colK3.textContent = "Calls";
          if (colK4) colK4.textContent = "Avg Call";
        }
      }

      function render(lb, live) {
        const rankings = (lb && lb.rankings) ? lb.rankings : [];
        const mode = (lb && typeof lb.metric_mode === "string") ? lb.metric_mode : "agentic";

        applyModeUI(mode);

        document.getElementById("lastUpdated").textContent = (lb && lb.generated_at) ? lb.generated_at : "Unknown";
        document.getElementById("runId").textContent = (lb && lb.active_run && lb.active_run.run_id) ? lb.active_run.run_id : "--";
        document.getElementById("tier").textContent = (lb && lb.active_run && lb.active_run.tier) ? lb.active_run.tier : "--";
        document.getElementById("totalTokens").textContent = (lb && lb.summary) ? fmtNum(lb.summary.total_tokens) : "--";

        // Metric cards (switch labels by benchmark mode).
        const k1 = document.getElementById("metricK1");
        const v1 = document.getElementById("metricV1");
        const k2 = document.getElementById("metricK2");
        const v2 = document.getElementById("metricV2");

        if (mode === "prompt") {
          k1.textContent = "Avg quality";
          k2.textContent = "Avg success";
          v1.textContent = (lb && lb.summary && typeof lb.summary.avg_quality_score === "number")
            ? fmtNum(lb.summary.avg_quality_score)
            : "--";
          v2.textContent = (lb && lb.summary && typeof lb.summary.avg_success_rate === "number")
            ? fmtPctFraction(lb.summary.avg_success_rate)
            : "--";
        } else {
          k1.textContent = "Avg profit";
          k2.textContent = "Avg ROI";
          v1.textContent = (lb && lb.summary && typeof lb.summary.avg_total_profit === "number")
            ? fmtMoney(lb.summary.avg_total_profit)
            : "--";
          v2.textContent = (lb && lb.summary && typeof lb.summary.avg_roi_pct === "number")
            ? fmtPct(lb.summary.avg_roi_pct)
            : "--";
        }

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
          rows.innerHTML = '<tr><td colspan="8" class="muted">No data yet.</td></tr>';
          return;
        }

        rows.innerHTML = rankings.map(r => {
          if (mode === "prompt") {
            const q = (typeof r.quality_score === "number") ? r.quality_score : 0;
            const sr = (typeof r.success_rate === "number") ? r.success_rate : 0;
            const rt = (typeof r.avg_response_time === "number") ? r.avg_response_time : null;
            const ec = (typeof r.error_count === "number") ? r.error_count : ((r.success === false) ? 1 : 0);
            return `
              <tr>
                <td><span class="rank">${r.rank}</span></td>
                <td class="mono">${(r.model_slug || r.model_name || "unknown")}</td>
                <td>${(r.provider || "unknown")}</td>
                <td><span class="pill ${profitClass(q - 0.85)}">${fmtNum(q)}</span></td>
                <td><span class="pill ${sr >= 1.0 ? "q-good" : sr >= 0.8 ? "q-warn" : "q-bad"}">${fmtPctFraction(sr)}</span></td>
                <td class="mono">${fmtSec(rt)}</td>
                <td><span class="pill ${ec > 0 ? "q-bad" : "q-good"}">${fmtNum(ec)}</span></td>
                <td class="mono">${fmtNum(r.total_tokens)}</td>
              </tr>
            `;
          }

          const p = (typeof r.total_profit === "number") ? r.total_profit : null;
          const roi = (typeof r.roi_pct === "number") ? r.roi_pct : null;
          const calls = (typeof r.llm_calls === "number") ? r.llm_calls : null;
          const avgCall = (typeof r.avg_call_seconds === "number") ? r.avg_call_seconds : null;
          const tokens = (typeof r.total_tokens === "number") ? r.total_tokens : null;
          return `
            <tr>
              <td><span class="rank">${r.rank}</span></td>
              <td class="mono">${(r.model_slug || r.model_name || "unknown")}</td>
              <td>${(r.provider || "unknown")}</td>
              <td><span class="pill ${profitClass(p)}">${fmtMoney(p)}</span></td>
              <td><span class="pill ${profitClass(roi)}">${roi === null ? "--" : fmtPct(roi)}</span></td>
              <td class="mono">${calls === null ? "--" : fmtNum(calls)}</td>
              <td>${fmtSec(avgCall)}</td>
              <td class="mono">${fmtNum(tokens)}</td>
            </tr>
          `;
        }).join("");
      }

      function leaderboardPath() {
        const qs = new URLSearchParams(window.location.search);
        const m = (qs.get("mode") || "").toLowerCase();
        if (m === "prompt") return "api/leaderboard_prompt.json";
        if (m === "agentic") return "api/leaderboard_agentic.json";
        return "api/leaderboard.json";
      }

      async function tick() {
        try {
          const lbPath = leaderboardPath();
          const [lb, live] = await Promise.all([
            fetchJson(lbPath).catch(() => fetchJson("api/leaderboard.json")),
            fetchJson("api/live.json").catch(() => null),
          ]);
          render(lb, live);
        } catch (e) {
          const rows = document.getElementById("rows");
          rows.innerHTML = '<tr><td colspan="8" class="muted">Failed to load leaderboard.json</td></tr>';
        }
      }

      tick();
      setInterval(tick, 10000);
    </script>
  </body>
</html>
"""

    INDEX_PATH.write_text(html, encoding="utf-8")


def _ensure_live_json() -> None:
    """
    The static site polls docs/api/live.json. It's optional (the page catches 404),
    but keeping a placeholder avoids noisy console errors and keeps docs/_headers meaningful.
    """
    DOCS_API_DIR.mkdir(parents=True, exist_ok=True)
    live_path = DOCS_API_DIR / "live.json"
    if live_path.exists():
        return
    payload = {
        "active": False,
        "status": "idle",
        "completed": 0,
        "total": 0,
        "run_id": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    live_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_empty_leaderboard(*, tier: str = "T2") -> None:
    DOCS_API_DIR.mkdir(parents=True, exist_ok=True)
    now_human = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    lb = {
        "generated_at": now_human,
        "benchmark_version": "2026.02-live",
        "metric_mode": "agentic",
        "active_run": {"active": False, "run_id": None, "tier": tier},
        "total_models": 0,
        "summary": {
            "avg_quality_score": None,
            "avg_success_rate": None,
            "avg_total_profit": None,
            "avg_roi_pct": None,
            "total_profit_sum": None,
            "total_llm_calls": None,
            "total_tokens": 0,
            "total_runs": 0,
            "top_performer": None,
        },
        "rankings": [],
    }
    (DOCS_API_DIR / "leaderboard.json").write_text(json.dumps(lb, indent=2), encoding="utf-8")
    (DOCS_API_DIR / "top10.json").write_text(
        json.dumps({"generated_at": now_human, "rankings": []}, indent=2),
        encoding="utf-8",
    )


def write_api_snapshots() -> None:
    """
    Generate JSON snapshots consumed by the static docs site.

    GitHub Pages workflow runs this script directly (without Poetry), so keep it stdlib-only.
    """
    _ensure_live_json()

    def _detect_tier(root: Path) -> Optional[str]:
        for candidate in ("t2", "t1", "t0"):
            if (root / candidate / "summary.json").exists():
                return candidate.upper()
        return None

    def _run_build(*, tier: str, results_root: Path, out_lb: Path, out_top10: Path) -> bool:
        build_script = ROOT_DIR / "tools" / "build_live_leaderboard.py"
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(build_script),
                    "--tier",
                    tier,
                    "--results-root",
                    str(results_root),
                    "--output-leaderboard",
                    str(out_lb),
                    "--output-top10",
                    str(out_top10),
                    "--live-json",
                    str(DOCS_API_DIR / "live.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return False
        return proc.returncode == 0

    def _copy(src: Path, dst: Path) -> None:
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    DOCS_API_DIR.mkdir(parents=True, exist_ok=True)

    # Build two snapshots when available: agentic and prompt.
    agentic_root = ROOT_DIR / "public_results" / "agentic" / "openrouter_tier_runs"
    prompt_root = ROOT_DIR / "public_results" / "prompt" / "openrouter_tier_runs"

    built_agentic = False
    built_prompt = False

    agentic_tier = _detect_tier(agentic_root)
    if agentic_tier:
        built_agentic = _run_build(
            tier=agentic_tier,
            results_root=agentic_root,
            out_lb=DOCS_API_DIR / "leaderboard_agentic.json",
            out_top10=DOCS_API_DIR / "top10_agentic.json",
        )

    prompt_tier = _detect_tier(prompt_root)
    if prompt_tier:
        built_prompt = _run_build(
            tier=prompt_tier,
            results_root=prompt_root,
            out_lb=DOCS_API_DIR / "leaderboard_prompt.json",
            out_top10=DOCS_API_DIR / "top10_prompt.json",
        )

    # Default snapshot: agentic if present, else prompt, else fall back to local results/.
    if built_agentic:
        _copy(DOCS_API_DIR / "leaderboard_agentic.json", DOCS_API_DIR / "leaderboard.json")
        _copy(DOCS_API_DIR / "top10_agentic.json", DOCS_API_DIR / "top10.json")
        return

    if built_prompt:
        _copy(DOCS_API_DIR / "leaderboard_prompt.json", DOCS_API_DIR / "leaderboard.json")
        _copy(DOCS_API_DIR / "top10_prompt.json", DOCS_API_DIR / "top10.json")
        return

    # Local dev convenience: if someone is running locally, try results/openrouter_tier_runs as a fallback.
    local_root = ROOT_DIR / "results" / "openrouter_tier_runs"
    local_tier = _detect_tier(local_root)
    if local_tier:
        ok = _run_build(
            tier=local_tier,
            results_root=local_root,
            out_lb=DOCS_API_DIR / "leaderboard.json",
            out_top10=DOCS_API_DIR / "top10.json",
        )
        if ok:
            return

    # Best effort: keep any previously-generated snapshot (avoid "blanking" GH Pages on CI).
    if (DOCS_API_DIR / "leaderboard.json").exists() and (DOCS_API_DIR / "top10.json").exists():
        return

    _write_empty_leaderboard()


def write_docs_html() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "docs").mkdir(parents=True, exist_ok=True)

    # Documentation categorization
    sections = [
        {
            "title": "Core",
            "links": [
                {"name": "Getting Started", "file": "README.md"},
                {"name": "Philosophy", "file": "benchmark_philosophy.md"},
                {"name": "Architecture", "file": "architecture.md"},
            ]
        },
        {
            "title": "Operational",
            "links": [
                {"name": "Simulation Runbook", "file": "RUNBOOK_SIM_BENCHMARK_V1.md"},
                {"name": "Theater Runbook", "file": "RUNBOOK_SIM_THEATER.md"},
                {"name": "Startup Guide", "file": "STARTUP.md"},
                {"name": "Leaderboard Publisher", "file": "leaderboard_publisher.md"},
            ]
        },
        {
            "title": "Features",
            "links": [
                {"name": "Features Overview", "file": "features_overview.md"},
                {"name": "Codebase Map", "file": "codebase_map.md"},
                {"name": "Agent Runners", "file": "agent_runners.md"},
                {"name": "Simulation Services", "file": "simulation_services.md"},
                {"name": "Services Catalog", "file": "services_catalog.md"},
                {"name": "Market Dynamics", "file": "market_dynamics.md"},
                {"name": "Scenarios System", "file": "scenarios_system.md"},
                {"name": "Benchmarking System", "file": "benchmarking_system.md"},
                {"name": "Metrics Suite", "file": "metrics_suite.md"},
                {"name": "Budget Constraints", "file": "budget_constraints.md"},
                {"name": "Reproducibility", "file": "reproducibility.md"},
                {"name": "Audit & Replay", "file": "audit_and_replay.md"},
                {"name": "Plugin Framework", "file": "plugin_framework.md"},
                {"name": "Red Team Gauntlet", "file": "red_team_gauntlet.md"},
                {"name": "Long-Term Memory & Modes", "file": "cognitive_memory.md"},
                {"name": "Consumer Utility Model", "file": "consumer_utility_model.md"},
                {"name": "Observability Stack", "file": "observability_stack.md"},
                {"name": "Learning Systems", "file": "learning_systems.md"},
                {"name": "Ledger System", "file": "ledger_system.md"},
            ],
        },
        {
            "title": "Business",
            "links": [
                {"name": "Sponsorship", "file": "sponsorship.md"},
                {"name": "Leaderboard Submissions", "file": "leaderboard_submissions.md"},
            ],
        },
        {
            "title": "Technical",
            "links": [
                {"name": "API Reference", "file": "API.md"},
                {"name": "API (Routes)", "file": "api/routes_catalog.md"},
                {"name": "API (Extra)", "file": "api/extra_endpoints.md"},
                {"name": "Configuration", "file": "configuration.md"},
                {"name": "Deployment", "file": "deployment.md"},
                {"name": "Observability", "file": "observability.md"},
                {"name": "Testing", "file": "testing.md"},
                {"name": "Performance FAQ", "file": "why_it_takes_hours.md"},
            ]
        },
        {
            "title": "Press",
            "links": [
                {"name": "Promo Video Runbook", "file": "press/promo_video.md"},
                {"name": "Social Posts", "file": "press/social_posts.md"},
                {"name": "Ad Creatives", "file": "press/ad_creatives.md"},
                {"name": "Submission Kit", "file": "press/submission_kit.md"},
                {"name": "Provider Outreach", "file": "press/provider_outreach.md"},
                {"name": "Outreach Tracker", "file": "press/outreach_tracker.md"},
                {"name": "Article Draft", "file": "press/article.md"},
            ],
        },
        {
            "title": "Legal",
            "links": [
                {"name": "Terms of Service", "file": "terms.md"},
                {"name": "Privacy Policy", "file": "privacy.md"},
                {"name": "Legal Disclaimer", "file": "disclaimer.md"},
                {"name": "Message me", "href": "../contact.html"},
            ]
        }
    ]

    sidebar_html = ""

    for sec in sections:
        sidebar_html += f'<div class="doc-nav-group"><div class="doc-nav-title">{sec["title"]}</div><ul class="doc-nav-links">'
        for link in sec["links"]:
            if "href" in link:
                sidebar_html += f'<li><a href="{link["href"]}" class="doc-nav-link">{link["name"]}</a></li>'
            else:
                sidebar_html += f'<li><a href="#{link["file"]}" class="doc-nav-link" data-file="{link["file"]}">{link["name"]}</a></li>'
        sidebar_html += "</ul></div>"

    seo = _seo_tags(
        title="FBA-Bench | Documentation",
        description="Documentation for FBA-Bench Enterprise: setup, architecture, API reference, deployment, runbooks, and testing.",
        canonical_path="/docs/",
        theme_color="#0a0a0a",
        icon_href="../favicon.svg",
    )

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>FBA-Bench | Documentation</title>
{seo}
    <link rel="stylesheet" href="../style.css" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
    <!-- Markdown Rendering Dependencies -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-bash.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-json.min.js"></script>
    <style>
      /* Prism theme adjustments for our dark mode */
      pre[class*="language-"] {{ background: #0d0d0d !important; text-shadow: none !important; }}
      code[class*="language-"] {{ text-shadow: none !important; }}
    </style>
  </head>
  <body>
    <div class="bg-grid" aria-hidden="true"></div>

    <header class="wrap header">
      <div class="brand">
        <div class="logo">FBA</div>
        <div class="brand-text">
          <div class="title">FBA-Bench</div>
          <div class="sub">Documentation</div>
        </div>
      </div>
      <div class="right">
        <a href="../index.html" class="chip">Leaderboard</a>
      </div>
    </header>

    <main class="wrap doc-layout">
      <aside class="doc-sidebar">
        {sidebar_html}
        <footer class="footer" style="padding: 24px 0 0; margin-top: 32px; border-top: 1px solid var(--border);">
          <div class="footer-links" style="flex-direction: column; gap: 8px;">
            <a href="#terms.md">Terms of Service</a>
            <a href="#privacy.md">Privacy Policy</a>
            <a href="#disclaimer.md">Legal Disclaimer</a>
          </div>
          <div style="margin-top: 16px; font-size: 11px;">FBA-Bench Enterprise &copy; 2026</div>
        </footer>
      </aside>

      <section class="doc-main">
        <h1 style="position: absolute; left: -10000px; top: auto; width: 1px; height: 1px; overflow: hidden;">FBA-Bench Documentation</h1>
        <div id="docContent" class="doc-content">
          <div class="muted">Loading documentation...</div>
        </div>
      </section>
    </main>

    <script>
      const contentDiv = document.getElementById('docContent');
      const navLinks = document.querySelectorAll('.doc-nav-link');

      async function loadDoc(filename) {{
        contentDiv.innerHTML = '<div class="muted">Loading ' + filename + '...</div>';
        
        // Update active state in sidebar
        navLinks.forEach(link => {{
          if (link.getAttribute('data-file') === filename) {{
            link.classList.add('active');
          }} else {{
            link.classList.remove('active');
          }}
        }});

        try {{
          const res = await fetch('../' + filename, {{ cache: 'no-cache' }});
          if (!res.ok) throw new Error('Failed to load ' + filename);
          const md = await res.text();
          contentDiv.innerHTML = marked.parse(md);
          
          // Trigger syntax highlighting
          Prism.highlightAllUnder(contentDiv);
          
          // Reset scroll
          window.scrollTo(0, 0);
        }} catch (e) {{
          contentDiv.innerHTML = '<div class="q-bad">Error loading documentation: ' + e.message + '</div>';
        }}
      }}

      function handleRoute() {{
        const hash = window.location.hash.substring(1);
        const target = hash || 'README.md';
        loadDoc(target);
      }}

      window.addEventListener('hashchange', handleRoute);
      handleRoute(); // Initial load
    </script>
  </body>
</html>
"""
    DOCS_HTML_PATH.write_text(html, encoding="utf-8")



def write_contact_html() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    seo = _seo_tags(
        title="FBA-Bench | Message Me",
        description="Send a message to the FBA-Bench maintainer.",
        canonical_path="/contact.html",
        theme_color="#0a0a0a",
        icon_href="favicon.svg",
    )

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>FBA-Bench | Message Me</title>
{seo}
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
          <div class="sub">Message me</div>
        </div>
      </div>
      <div class="right">
        <a href="index.html" class="chip">Leaderboard</a>
        <a href="docs/" class="chip">Docs</a>
      </div>
    </header>

    <main class="wrap">
      <section class="panel">
        <h1 style="position: absolute; left: -10000px; top: auto; width: 1px; height: 1px; overflow: hidden;">Contact FBA-Bench</h1>
        <div class="panel-h">
          <div class="panel-title">Send a message</div>
          <div class="panel-note">This posts to <span class="mono">/api/v1/contact</span> when the API is available.</div>
        </div>

        <div class="contact-grid">
          <form id="contactForm" class="contact-form" autocomplete="on" novalidate>
            <label class="field">
              <div class="field-k">Your name (optional)</div>
              <input name="name" type="text" maxlength="255" placeholder="Jane Doe" />
            </label>

            <label class="field">
              <div class="field-k">Your email</div>
              <input name="email" type="email" maxlength="255" placeholder="you@example.com" required />
            </label>

            <label class="field">
              <div class="field-k">Subject (optional)</div>
              <input name="subject" type="text" maxlength="255" placeholder="Quick question about FBA-Bench" />
            </label>

            <label class="field">
              <div class="field-k">Message</div>
              <textarea name="message" rows="8" maxlength="10000" placeholder="Write your message..." required></textarea>
            </label>

            <!-- Honeypot: bots will often fill it -->
            <label class="field hp" aria-hidden="true">
              <div class="field-k">Company</div>
              <input name="company" type="text" tabindex="-1" autocomplete="off" />
            </label>

            <div class="actions">
              <button class="btn" type="submit">Send</button>
              <a class="chip" href="https://github.com/Bender1011001/FBA-Bench-Enterprise" target="_blank" rel="noreferrer">github</a>
            </div>

            <div id="contactStatus" class="muted" style="margin-top: 12px;">Ready.</div>
          </form>

          <div class="contact-side">
            <div class="card">
              <div class="card-k">Fallback</div>
              <div class="card-v">If the API is not running (e.g., GitHub Pages), this form cannot deliver. Email: support [at] fba-bench [dot] com.</div>
            </div>
            <div class="card">
              <div class="card-k">Privacy</div>
              <div class="card-v">Messages may be stored on the server to help respond.</div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <script>
      const form = document.getElementById("contactForm");
      const statusEl = document.getElementById("contactStatus");

      function setStatus(text, cls) {{
        statusEl.className = cls || "muted";
        statusEl.textContent = text;
      }}

      async function postJson(url, data) {{
        const res = await fetch(url, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(data),
        }});
        const contentType = res.headers.get("content-type") || "";
        const body = contentType.includes("application/json") ? await res.json() : await res.text();
        if (!res.ok) {{
          const msg = (body && body.detail) ? body.detail : ("HTTP " + res.status);
          throw new Error(msg);
        }}
        return body;
      }}

      form.addEventListener("submit", async (e) => {{
        e.preventDefault();
        const fd = new FormData(form);
        const payload = {{
          name: (fd.get("name") || "").toString(),
          email: (fd.get("email") || "").toString(),
          subject: (fd.get("subject") || "").toString(),
          message: (fd.get("message") || "").toString(),
          hp: (fd.get("company") || "").toString(),
          source: window.location.pathname,
        }};

        setStatus("Sending...", "muted");
        try {{
          await postJson("/api/v1/contact", payload);
          form.reset();
          setStatus("Sent.", "q-good");
        }} catch (err) {{
          setStatus("Could not send via API (" + err.message + "). Try again later.", "q-warn");
        }}
      }});
    </script>
  </body>
</html>
"""

    CONTACT_PATH.write_text(html, encoding="utf-8")


def main() -> int:
    write_seo_files()
    write_api_snapshots()
    write_index_html()
    write_docs_html()
    write_contact_html()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
