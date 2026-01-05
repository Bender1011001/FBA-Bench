#!/usr/bin/env python3
"""FBA-Bench Performance Index Generator.

This script generates a complete static website for the FBA-Bench Performance Index,
transforming benchmark data into a public-facing platform.

Features:
    - Generates the main Performance Index page
    - Creates provider-specific leaderboard pages
    - Generates embeddable widgets
    - Outputs SEO-friendly static HTML
    - Supports multiple themes and configurations

Usage:
    python generate_performance_index.py
    python generate_performance_index.py --output-dir ./public
    python generate_performance_index.py --benchmark-file results.json
"""

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "leaderboard" / "templates"
DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_OUTPUT_DIR = DOCS_DIR  # Output to docs for GitHub Pages


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ModelPerformance:
    """Represents a model's performance metrics."""
    
    rank: int
    model_name: str
    provider: str
    tier: Literal["flagship", "standard", "free", "experimental"]
    quality_score: float
    success_rate: float
    avg_response_time: float
    total_tokens: int
    total_runs: int
    last_updated: str
    badge: Literal["gold", "silver", "bronze", "rising", "stable"] = "stable"
    
    # Optional financial metrics
    avg_profit: Optional[float] = None
    avg_roi: Optional[float] = None


@dataclass
class LeaderboardSummary:
    """Summary statistics for the leaderboard."""
    
    total_models: int = 0
    total_runs: int = 0
    total_providers: int = 0
    avg_quality: float = 0.0
    avg_success_rate: float = 0.0
    total_tokens: int = 0
    top_performer: str = "N/A"


@dataclass
class PerformanceIndex:
    """Complete performance index data."""
    
    generated_at: str
    benchmark_version: str
    summary: LeaderboardSummary
    rankings: List[ModelPerformance] = field(default_factory=list)


# ============================================================================
# Data Loading & Transformation
# ============================================================================

def extract_provider(model_id: str) -> str:
    """Extract provider name from model ID."""
    if "/" in model_id:
        return model_id.split("/")[0].title()
    
    model_lower = model_id.lower()
    providers = {
        "gpt": "OpenAI",
        "openai": "OpenAI",
        "claude": "Anthropic",
        "anthropic": "Anthropic",
        "gemini": "Google",
        "google": "Google",
        "llama": "Meta",
        "meta": "Meta",
        "grok": "xAI",
        "x-ai": "xAI",
        "deepseek": "DeepSeek",
        "mistral": "Mistral",
        "qwen": "Alibaba",
    }
    
    for key, name in providers.items():
        if key in model_lower:
            return name
    
    return "Unknown"


def determine_tier(model_id: str) -> Literal["flagship", "standard", "free", "experimental"]:
    """Determine model tier based on model ID."""
    model_lower = model_id.lower()
    
    flagship = ["gpt-4", "gpt-5", "claude-3.5", "claude-opus", "gemini-pro", "grok-4"]
    free = ["free", "mini", "tiny", "small", "lite"]
    experimental = ["preview", "beta", "experimental", "dev"]
    
    if any(ind in model_lower for ind in flagship):
        return "flagship"
    if any(ind in model_lower for ind in free):
        return "free"
    if any(ind in model_lower for ind in experimental):
        return "experimental"
    
    return "standard"


def calculate_badge(rank: int, quality_score: float) -> str:
    """Calculate achievement badge."""
    if rank == 1:
        return "gold"
    elif rank == 2:
        return "silver"
    elif rank == 3:
        return "bronze"
    elif quality_score >= 0.9:
        return "rising"
    return "stable"


def load_benchmark_data(filepath: Optional[Path] = None) -> Dict[str, Any]:
    """Load benchmark data from file or find the best available."""
    
    # Priority order for benchmark files
    search_paths = [
        filepath,
        PROJECT_ROOT / "openrouter_benchmark_results.json",
        PROJECT_ROOT / "top_models_benchmark.json",
        PROJECT_ROOT / "free_models_benchmark.json",
        PROJECT_ROOT / "artifacts" / "leaderboard.json",
    ]
    
    for path in search_paths:
        if path and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"✓ Loaded benchmark data from: {path}")
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {path}: {e}")
    
    logger.warning("No benchmark data found, using empty dataset")
    return {"model_results": [], "benchmark_info": {}}


def transform_benchmark_data(data: Dict[str, Any]) -> PerformanceIndex:
    """Transform raw benchmark data into PerformanceIndex format."""
    model_results = data.get("model_results", [])
    benchmark_info = data.get("benchmark_info", {})
    
    rankings: List[ModelPerformance] = []
    providers_seen = set()
    
    for result in model_results:
        model_name = result.get("model", "Unknown Model")
        summary = result.get("summary", {})
        prompts = result.get("prompts", [])
        
        # Extract metrics
        quality_scores = [p.get("quality_score", 0) for p in prompts if p.get("quality_score")]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        
        provider = extract_provider(model_name)
        providers_seen.add(provider)
        
        # Clean model name
        display_name = model_name.split("/")[-1] if "/" in model_name else model_name
        
        performance = ModelPerformance(
            rank=0,  # Will be assigned after sorting
            model_name=display_name,
            provider=provider,
            tier=determine_tier(model_name),
            quality_score=round(avg_quality, 3),
            success_rate=round(summary.get("success_rate", 1.0), 3),
            avg_response_time=round(summary.get("average_response_time", 0.0), 2),
            total_tokens=summary.get("total_tokens", 0),
            total_runs=summary.get("total_prompts", 1),
            last_updated=result.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
        rankings.append(performance)
    
    # Sort by quality score (primary) and success rate (secondary)
    rankings.sort(key=lambda x: (x.quality_score, x.success_rate), reverse=True)
    
    # Assign ranks and badges
    for idx, r in enumerate(rankings):
        r.rank = idx + 1
        r.badge = calculate_badge(r.rank, r.quality_score)
    
    # Calculate summary
    summary = LeaderboardSummary(
        total_models=len(rankings),
        total_runs=sum(r.total_runs for r in rankings),
        total_providers=len(providers_seen),
        avg_quality=round(sum(r.quality_score for r in rankings) / len(rankings), 3) if rankings else 0,
        avg_success_rate=round(sum(r.success_rate for r in rankings) / len(rankings), 3) if rankings else 0,
        total_tokens=sum(r.total_tokens for r in rankings),
        top_performer=rankings[0].model_name if rankings else "N/A",
    )
    
    return PerformanceIndex(
        generated_at=datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC"),
        benchmark_version=benchmark_info.get("version", "2.0.0"),
        summary=summary,
        rankings=rankings,
    )


# ============================================================================
# Static Site Generation
# ============================================================================

class PerformanceIndexGenerator:
    """Generates the static Performance Index website."""
    
    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        templates_dir: Path = TEMPLATES_DIR,
    ):
        self.output_dir = output_dir
        self.templates_dir = templates_dir
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        
    def generate(self, data: PerformanceIndex) -> None:
        """Generate the complete static site."""
        logger.info("🚀 Generating Performance Index...")
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate main index page
        self._generate_index_page(data)
        
        # Generate individual provider pages
        self._generate_provider_pages(data)
        
        # Generate widget HTML
        self._generate_widget(data)
        
        # Generate JSON API response
        self._generate_json_api(data)
        
        # Copy static assets
        self._copy_static_assets()
        
        logger.info(f"✅ Performance Index generated at: {self.output_dir}")
        
    def _generate_index_page(self, data: PerformanceIndex) -> None:
        """Generate the main index.html page."""
        try:
            template = self.env.get_template("performance_index.html")
            
            html_content = template.render(
                generated_at=data.generated_at,
                benchmark_version=data.benchmark_version,
                summary=data.summary,
                rankings=data.rankings,
            )
            
            output_path = self.output_dir / "index.html"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            logger.info(f"  → Generated: {output_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to generate index page: {e}")
            # Fall back to basic template
            self._generate_fallback_index(data)
    
    def _generate_fallback_index(self, data: PerformanceIndex) -> None:
        """Generate a basic index page if template fails."""
        rows_html = ""
        for r in data.rankings:
            rank_class = f"rank-{r.rank}" if r.rank <= 3 else ""
            rows_html += f"""
            <tr>
                <td><span class="rank-badge {rank_class}">{r.rank}</span></td>
                <td>
                    <div class="model-name">{r.model_name}</div>
                    <div class="model-provider">{r.provider}</div>
                </td>
                <td><span class="tier-badge tier-{r.tier}">{r.tier}</span></td>
                <td class="score-cell">{r.quality_score:.1%}</td>
                <td>{r.success_rate:.0%}</td>
                <td>{r.avg_response_time:.1f}s</td>
                <td>{r.total_tokens:,}</td>
            </tr>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FBA-Bench Performance Index</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>FBA-Bench Performance Index</h1>
        <p>Generated: {data.generated_at}</p>
        
        <div class="stats">
            <div class="stat">
                <span class="value">{data.summary.total_models}</span>
                <span class="label">Models</span>
            </div>
            <div class="stat">
                <span class="value">{data.summary.total_runs}</span>
                <span class="label">Benchmark Runs</span>
            </div>
            <div class="stat">
                <span class="value">{data.summary.avg_quality:.1%}</span>
                <span class="label">Avg Quality</span>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Model</th>
                    <th>Tier</th>
                    <th>Quality</th>
                    <th>Success</th>
                    <th>Response</th>
                    <th>Tokens</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>"""
        
        output_path = self.output_dir / "index.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        logger.info(f"  → Generated (fallback): {output_path.name}")
    
    def _generate_provider_pages(self, data: PerformanceIndex) -> None:
        """Generate individual pages for each provider."""
        providers_dir = self.output_dir / "providers"
        providers_dir.mkdir(exist_ok=True)
        
        # Group by provider
        by_provider: Dict[str, List[ModelPerformance]] = {}
        for r in data.rankings:
            by_provider.setdefault(r.provider, []).append(r)
        
        for provider, models in by_provider.items():
            # Sort models within provider by quality score
            models.sort(key=lambda x: (x.quality_score, x.success_rate), reverse=True)
            
            # Generate provider-specific JSON
            provider_slug = provider.lower().replace(" ", "-")
            provider_data = {
                "provider": provider,
                "models": [
                    {
                        "provider_rank": idx + 1,
                        "global_rank": m.rank,
                        "model_name": m.model_name,
                        "quality_score": m.quality_score,
                        "success_rate": m.success_rate,
                        "total_runs": m.total_runs,
                    }
                    for idx, m in enumerate(models)
                ],
                "generated_at": data.generated_at,
            }
            
            output_path = providers_dir / f"{provider_slug}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(provider_data, f, indent=2)
        
        logger.info(f"  → Generated: {len(by_provider)} provider pages")
    
    def _generate_widget(self, data: PerformanceIndex) -> None:
        """Generate embeddable widget HTML."""
        top_5 = data.rankings[:5]
        
        rows_html = ""
        for r in top_5:
            rows_html += f"""
            <tr>
                <td><span class="rank">{r.rank}</span></td>
                <td class="model">{r.model_name}</td>
                <td class="score">{r.quality_score:.0%}</td>
            </tr>"""
        
        widget_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FBA-Bench Widget</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0d1117;
            color: #f0f6fc;
            padding: 16px;
        }}
        .header {{ text-align: center; margin-bottom: 16px; }}
        .header h3 {{
            font-size: 14px;
            background: linear-gradient(90deg, #00d2ff, #6e48aa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .rank {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 12px;
            background: #21262d;
        }}
        tr:nth-child(1) .rank {{ background: linear-gradient(135deg, #ffd700, #ffa500); color: #000; }}
        tr:nth-child(2) .rank {{ background: linear-gradient(135deg, #c0c0c0, #a0a0a0); color: #000; }}
        tr:nth-child(3) .rank {{ background: linear-gradient(135deg, #cd7f32, #8b4513); }}
        .model {{ font-weight: 600; }}
        .score {{ color: #00d2ff; font-weight: 700; text-align: right; }}
        .footer {{
            text-align: center;
            margin-top: 12px;
            font-size: 11px;
            opacity: 0.5;
        }}
        .footer a {{ color: #00d2ff; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="header">
        <h3>FBA-Bench Top 5</h3>
    </div>
    <table>
        {rows_html}
    </table>
    <div class="footer">
        <a href="https://fba-bench.io" target="_blank">fba-bench.io</a>
    </div>
</body>
</html>"""
        
        output_path = self.output_dir / "widget.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(widget_html)
        
        logger.info(f"  → Generated: widget.html")
    
    def _generate_json_api(self, data: PerformanceIndex) -> None:
        """Generate JSON API response for programmatic access."""
        api_dir = self.output_dir / "api"
        api_dir.mkdir(exist_ok=True)
        
        # Full leaderboard
        leaderboard_data = {
            "generated_at": data.generated_at,
            "benchmark_version": data.benchmark_version,
            "total_models": data.summary.total_models,
            "summary": {
                "avg_quality_score": data.summary.avg_quality,
                "avg_success_rate": data.summary.avg_success_rate,
                "total_tokens": data.summary.total_tokens,
                "total_runs": data.summary.total_runs,
                "top_performer": data.summary.top_performer,
            },
            "rankings": [
                {
                    "rank": r.rank,
                    "model_name": r.model_name,
                    "provider": r.provider,
                    "tier": r.tier,
                    "quality_score": r.quality_score,
                    "success_rate": r.success_rate,
                    "avg_response_time": r.avg_response_time,
                    "total_tokens": r.total_tokens,
                    "total_runs": r.total_runs,
                    "badge": r.badge,
                }
                for r in data.rankings
            ],
        }
        
        with open(api_dir / "leaderboard.json", "w", encoding="utf-8") as f:
            json.dump(leaderboard_data, f, indent=2)
        
        # Top 10 quick access
        top_10 = leaderboard_data.copy()
        top_10["rankings"] = leaderboard_data["rankings"][:10]
        
        with open(api_dir / "top10.json", "w", encoding="utf-8") as f:
            json.dump(top_10, f, indent=2)
        
        logger.info(f"  → Generated: api/leaderboard.json, api/top10.json")
    
    def _copy_static_assets(self) -> None:
        """Copy static assets (CSS, images) to output directory."""
        # Copy style.css if it exists and is different from destination
        style_src = DOCS_DIR / "style.css"
        style_dst = self.output_dir / "style.css"
        if style_src.exists() and style_src.resolve() != style_dst.resolve():
            shutil.copy(style_src, style_dst)
            logger.info(f"  → Copied: style.css")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Main entry point for the Performance Index generator."""
    parser = argparse.ArgumentParser(
        description="Generate the FBA-Bench Performance Index static site",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--benchmark-file",
        type=Path,
        help="Path to benchmark results JSON file",
    )
    
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for generated files (default: {DEFAULT_OUTPUT_DIR})",
    )
    
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=TEMPLATES_DIR,
        help=f"Templates directory (default: {TEMPLATES_DIR})",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load benchmark data
    raw_data = load_benchmark_data(args.benchmark_file)
    
    if not raw_data.get("model_results"):
        logger.warning("No model results found in benchmark data")
    
    # Transform to PerformanceIndex format
    performance_index = transform_benchmark_data(raw_data)
    
    logger.info(f"📊 Loaded {performance_index.summary.total_models} models from {performance_index.summary.total_providers} providers")
    
    # Generate static site
    generator = PerformanceIndexGenerator(
        output_dir=args.output_dir,
        templates_dir=args.templates_dir,
    )
    
    generator.generate(performance_index)
    
    # Summary
    print()
    print("=" * 60)
    print("  FBA-Bench Performance Index Generated Successfully!")
    print("=" * 60)
    print(f"  📁 Output: {args.output_dir}")
    print(f"  🏆 Top Performer: {performance_index.summary.top_performer}")
    print(f"  📊 Models: {performance_index.summary.total_models}")
    print(f"  🔬 Benchmark Runs: {performance_index.summary.total_runs}")
    print("=" * 60)
    print()
    print("To preview locally:")
    print(f"  cd {args.output_dir} && python -m http.server 8080")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
