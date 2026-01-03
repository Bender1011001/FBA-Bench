import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent
DATA_PATH = ROOT_DIR / "openrouter_benchmark_results.json"
OUTPUT_PATH = ROOT_DIR / "docs" / "index.html"

def generate_html(data):
    rankings = data.get("rankings", [])
    last_updated = datetime.fromisoformat(data["generated_at"]).strftime("%B %d, %Y")
    
    rows_html = ""
    for entry in rankings:
        rank_class = f"rank-{entry['rank']}" if entry['rank'] <= 3 else ""
        tier_class = f"badge-{entry['tier'].lower()}"
        
        rows_html += f"""
        <tr>
            <td><span class="rank-badge {rank_class}">{entry['rank']}</span></td>
            <td>
                <div style="font-weight: 600;">{entry['display_name']}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">{entry['model']}</div>
            </td>
            <td>
                <div style="font-weight: 700; color: var(--accent); font-size: 1.1rem;">${entry['net_profit']:,.2f}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">ROI: {entry['roi']}%</div>
            </td>
            <td>
                <div>${entry['revenue']:,.2f}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted);">Margin: {entry['margin']}%</div>
            </td>
            <td><span class="badge {tier_class}">{entry['tier']}</span></td>
            <td>{entry['avg_response_time']}s</td>
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
                    Currently <strong>{data['summary']['most_profitable']}</strong> leads in profitability with a 
                    <strong>{max(entry['roi'] for entry in data['rankings'])}% ROI</strong>.
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
    if DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        generate_html(data)
        generate_docs_page()
        print(f"\u2705 Generated GitHub Pages at docs/index.html and docs/docs.html")
    else:
        print(f"\u274c Error: openrouter_benchmark_results.json not found.")
