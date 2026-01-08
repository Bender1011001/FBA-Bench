import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent
DATA_PATH = ROOT_DIR / "top_models_benchmark.json"
LEADERBOARD_PATH = ROOT_DIR / "artifacts" / "leaderboard.json"
OUTPUT_PATH = ROOT_DIR / "docs" / "index.html"

def generate_html(data):
    # Adapt to different input formats
    summary = data.get("summary", {})
    if "rankings" in data and "verified_models_count" in summary:
         # New LeaderboardManager format
         rankings = data["rankings"]
         is_financial = True # LeaderboardManager tracks scores/profit
    elif "model_rankings" in summary:
        rankings = summary["model_rankings"]
        is_financial = False # Qualitative
    else:
        # Default/Legacy format (top-level rankings key)
        rankings = data.get("rankings", [])
        is_financial = False
        
    if not rankings:
        print("Warning: No rankings found in data.")
        return
        
    generated_at = data.get("benchmark_info", {}).get("timestamp") or data.get("generated_at") or data.get("last_updated")
    last_updated = "Unknown"
    if generated_at:
        try:
             last_updated = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%B %d, %Y")
        except:
             last_updated = str(generated_at)
    
    rows_html = ""
    for idx, entry in enumerate(rankings):
        rank = idx + 1
        rank_class = f"rank-{rank}" if rank <= 3 else ""
        
        # Determine attributes based on benchmark type
        model_name = entry.get('model') or entry.get('bot_name', 'Unknown')
        verified = entry.get('verified', False)
        
        verified_badge = ""
        if verified:
            verified_badge = """
            <span style="display:inline-flex; align-items:center; background:rgba(251, 191, 36, 0.15); color:#fbbf24; border:1px solid rgba(251, 191, 36, 0.3); padding:2px 8px; border-radius:12px; font-size:0.7em; margin-left:8px; font-weight:700;">
                \u2713 VERIFIED
            </span>
            """
        
        # Check for financial metrics vs qualitative metrics
        if 'score' in entry: # LeaderboardManager uses 'score'
             metric_1_label = f"${entry['score']:,.2f}"
             metric_1_sub = "Net Profit"
             metric_2_label = f"{entry.get('consistency', 0)*100:.0f}%"
             metric_2_sub = "Consistency"
             tier = entry.get('tier', 'Standard')
        elif 'net_profit' in entry:
            # Financial Benchmark (Legacy)
            metric_1_label = f"${entry['net_profit']:,.2f}"
            metric_1_sub = f"ROI: {entry.get('roi', 0)}%"
            metric_2_label = f"${entry.get('revenue', 0):,.2f}"
            metric_2_sub = f"Margin: {entry.get('margin', 0)}%"
            tier = entry.get('tier', 'Standard')
        else:
            # Qualitative/Reasoning Benchmark
            success_rate = entry.get('success_rate', 0) * 100
            quality = entry.get('quality_score', 0)
            
            metric_1_label = f"{success_rate:.0f}%"
            metric_1_sub = "Success Rate"
            metric_2_label = f"{entry.get('avg_response_time', 0):.2f}s"
            metric_2_sub = "Avg Time"
            tier = "Qualitative"

        tier_class = f"badge-{tier.lower()}"
        
        rows_html += f"""
        <tr>
            <td><span class="rank-badge {rank_class}">{rank}</span></td>
            <td>
                <div style="font-weight: 600; display:flex; align-items:center;">
                    {model_name}
                    {verified_badge}
                </div>
            </td>
            <td>
                <div style="font-weight: 700; color: var(--accent); font-size: 1.1rem;">{metric_1_label}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">{metric_1_sub}</div>
            </td>
            <td>
                <div>{metric_2_label}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">{metric_2_sub}</div>
            </td>
            <td><span class="badge {tier_class}">{tier}</span></td>
            <td>{entry.get('total_tokens', entry.get('runs_completed', 0))} {('runs' if 'score' in entry else 'toks')}</td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FBA-Bench | The Standard for AI Business Agents</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        /* Feature Grid Styling */
        .features {{
            padding: 4rem 2rem;
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
        }}
        .feature-card {{
            padding: 2rem;
            text-align: left;
            transition: transform 0.3s;
        }}
        .feature-card:hover {{ transform: translateY(-5px); }}
        .feature-card h3 {{ color: var(--accent); margin-top: 0; }}
        
        footer {{
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
            font-size: 0.875rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}
    </style>
</head>
<body>
    <div class="hero">
        <h1 class="gradient-text">FBA-Bench</h1>
        <p>The first comprehensive, decentralized benchmark for AI Agents in realistic business simulations. Reproducible, verifiable, and open.</p>
        <div style="margin-top: 1rem;">
            <a href="https://github.com/admin/fba" class="cta-button">View on GitHub</a>
            <a href="#leaderboard" style="margin-left: 1rem; color: var(--text-main); text-decoration: none; font-weight: 600;">View Rankings \u2193</a>
        </div>
    </div>

    <div id="leaderboard" class="leaderboard-preview glass">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2rem;">
            <div>
                <h2 style="margin: 0; font-size: 2rem;">Global Leaderboard</h2>
                <p style="margin: 0.5rem 0 0; color: var(--text-muted);">OpenRouter Flagship & Free Models</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em;">Last Updated</div>
                <div style="font-weight: 600;">{last_updated}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Agent Model</th>
                    <th>Net Profit ($)</th>
                    <th>Revenue / Margin</th>
                    <th>Tier</th>
                    <th>Speed</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div style="margin-top: 2rem; padding: 1.5rem; background: rgba(0, 210, 255, 0.05); border-radius: 12px; border: 1px solid rgba(0, 210, 255, 0.1);">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.5rem;">\U0001F4A1</span>
                <div>
                    <strong style="color: var(--accent);">Benchmark Summary:</strong> 
                    Currently <strong>{data['summary'].get('most_profitable') or data['summary'].get('best_performing_model', 'Unknown')}</strong> leads with 
                    <strong>{f"{max(entry.get('roi', 0) for entry in rankings)}% ROI" if any('roi' in e for e in rankings) else f"{max(entry.get('success_rate', 0)*100 for entry in rankings):.0f}% Success Rate"}</strong>.
                </div>
            </div>
        </div>
    </div>

    <div class="features">
        <div class="feature-card glass">
            <h3>\U0001F3AF Business-First</h3>
            <p>Unlike general knowledge tests, FBA-Bench focuses on real-world business reasoning: pricing strategy, logistics optimization, and marketing planning.</p>
        </div>
        <div class="feature-card glass">
            <h3>\U0001F50D Deterministic</h3>
            <p>Our Golden Master policy ensures every run is verifiable. Use our core library to reproduce any result on the leaderboard locally.</p>
        </div>
        <div class="feature-card glass">
            <h3>\u26a1 OpenRouter Integration</h3>
            <p>Direct integration with OpenRouter allows testing across 100+ models instantly with a single API key.</p>
        </div>
    </div>

    <footer>
        <p>&copy; 2025 FBA-Bench Project. Built for the era of Agentic AI.</p>
        <p style="margin-top: 0.5rem;"><a href="https://github.com/admin/fba" style="color: var(--primary); text-decoration: none;">GitHub</a> \u2022 <a href="https://twitter.com/FBA_Bench" style="color: var(--primary); text-decoration: none;">Twitter</a> \u2022 <a href="#" style="color: var(--primary); text-decoration: none;">Documentation</a></p>
    </footer>
</body>
</html>
"""
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

def generate_docs_page():
    docs_dir = ROOT_DIR / "docs"
    output_path = docs_dir / "docs.html"
    
    # Key docs we want to highlight
    key_docs = [
        {"title": "API Documentation", "file": "API.md", "desc": "Detailed endpoint specifications and response models."},
        {"title": "Architecture Overview", "file": "architecture.md", "desc": "Deep dive into the modular agent and scenario systems."},
        {"title": "Golden Master Policy", "file": "quality/golden_master.md", "desc": "How we ensure deterministic and verifiable benchmarks."},
        {"title": "Getting Started", "file": "getting-started.md", "desc": "Step-by-step guide to running your first simulation."},
        {"title": "Deployment Guide", "file": "deployment.md", "desc": "Production setup for enterprise-scale benchmarking."},
        {"title": "User Guide", "file": "user-guide.md", "desc": "Comprehensive manual for using FBA-Bench features."}
    ]
    
    cards_html = ""
    for doc in key_docs:
        # Link to GitHub because we aren't rendering MD to HTML yet
        github_url = f"https://github.com/admin/fba/blob/main/docs/{doc['file']}"
        cards_html += f"""
        <div class="feature-card glass">
            <h3>{doc['title']}</h3>
            <p>{doc['desc']}</p>
            <a href="{github_url}" style="color: var(--accent); text-decoration: none; font-size: 0.875rem; font-weight: 600;">Read Document \u2192</a>
        </div>
        """
        
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documentation | FBA-Bench</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        .docs-grid {{
            padding: 4rem 2rem;
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 2rem;
        }}
        header {{
            text-align: center;
            padding: 6rem 2rem 2rem;
            background: linear-gradient(180deg, rgba(110, 72, 170, 0.1), transparent);
        }}
    </style>
</head>
<body>
    <header>
        <a href="index.html" style="color: var(--text-muted); text-decoration: none; font-size: 0.875rem;">\u2190 Back to Leaderboard</a>
        <h1 class="gradient-text" style="font-size: 3rem; margin: 1rem 0;">Documentation</h1>
        <p style="color: var(--text-muted); max-width: 600px; margin: 0 auto;">Everything you need to build, test, and deploy AI business agents.</p>
    </header>

    <div class="docs-grid">
        {cards_html}
    </div>

    <footer>
        <p>&copy; 2025 FBA-Bench Project. Built for the era of Agentic AI.</p>
    </footer>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    if LEADERBOARD_PATH.exists():
        with open(LEADERBOARD_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loading data from {LEADERBOARD_PATH}")
        generate_html(data)
        generate_docs_page()
        print(f"\u2705 Generated GitHub Pages at docs/index.html and docs/docs.html using {LEADERBOARD_PATH.name}")
    elif DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loading data from {DATA_PATH}")
        generate_html(data)
        generate_docs_page()
        print(f"\u2705 Generated GitHub Pages at docs/index.html and docs/docs.html using {DATA_PATH.name}")
    else:
        print(f"\u274c Error: Neither openrouter_benchmark_results.json nor leaderboard.json found.")
