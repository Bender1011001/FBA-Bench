"""Public Leaderboard API Routes.

This module provides public-facing API endpoints for the FBA-Bench Performance Index.
These endpoints are designed for external consumption and support embedding, 
widget generation, and third-party integrations.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/public", tags=["Public Leaderboard"])


# ============================================================================
# Pydantic Models for Public API
# ============================================================================

class ModelPerformance(BaseModel):
    """Represents a model's performance in the public leaderboard."""
    
    rank: int = Field(..., description="Position in the leaderboard (1-indexed)")
    model_name: str = Field(..., alias="modelName", description="Display name of the AI model")
    provider: str = Field(..., description="Model provider (e.g., OpenAI, Anthropic)")
    tier: Literal["flagship", "standard", "free", "experimental"] = Field(
        ..., description="Model tier classification"
    )
    
    # Core Business Metrics
    success_rate: float = Field(..., alias="successRate", ge=0, le=1, description="Task completion rate (0-1)")
    quality_score: float = Field(..., alias="qualityScore", ge=0, le=1, description="Average response quality (0-1)")
    avg_response_time: float = Field(..., alias="avgResponseTime", ge=0, description="Average response time in seconds")
    
    # Financial Simulation Metrics (when available)
    avg_profit: Optional[float] = Field(None, alias="avgProfit", description="Average profit in simulations")
    avg_roi: Optional[float] = Field(None, alias="avgRoi", description="Average return on investment %")
    
    # Usage & Cost
    total_tokens: int = Field(..., alias="totalTokens", ge=0, description="Total tokens consumed")
    total_runs: int = Field(..., alias="totalRuns", ge=1, description="Number of benchmark runs")
    
    # Metadata
    last_updated: str = Field(..., alias="lastUpdated", description="ISO timestamp of last update")
    badge: Literal["gold", "silver", "bronze", "rising", "stable"] = Field(
        "stable", description="Achievement badge"
    )
    
    class Config:
        populate_by_name = True


class LeaderboardResponse(BaseModel):
    """Full leaderboard response with metadata."""
    
    generated_at: str = Field(..., alias="generatedAt", description="ISO timestamp of generation")
    version: str = Field(default="1.0.0", description="API version")
    total_models: int = Field(..., alias="totalModels", description="Total models in leaderboard")
    benchmark_version: str = Field(..., alias="benchmarkVersion", description="FBA-Bench version used")
    
    # Summary Statistics
    summary: Dict[str, Any] = Field(..., description="Aggregate statistics")
    
    # The Rankings
    rankings: List[ModelPerformance] = Field(..., description="Ranked model performances")
    
    class Config:
        populate_by_name = True


class EmbedWidget(BaseModel):
    """Embed widget configuration."""
    
    html: str = Field(..., description="HTML snippet for embedding")
    width: int = Field(default=400, description="Widget width in pixels")
    height: int = Field(default=600, description="Widget height in pixels")


# ============================================================================
# Data Loading Utilities
# ============================================================================

def _load_benchmark_results() -> Dict[str, Any]:
    """Load the latest benchmark results from available sources."""
    project_root = Path(__file__).resolve().parents[5]  # Navigate to project root
    
    # Priority order for benchmark files
    benchmark_files = [
        project_root / "openrouter_benchmark_results.json",
        project_root / "top_models_benchmark.json",
        project_root / "free_models_benchmark.json",
        project_root / "artifacts" / "leaderboard.json",
    ]
    
    for filepath in benchmark_files:
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded benchmark data from {filepath}")
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {filepath}: {e}")
                continue
    
    logger.warning("No benchmark data found, returning empty results")
    return {"model_results": [], "benchmark_info": {}}


def _extract_provider(model_id: str) -> str:
    """Extract provider name from model ID."""
    if "/" in model_id:
        return model_id.split("/")[0].title()
    
    model_lower = model_id.lower()
    if "gpt" in model_lower or "openai" in model_lower:
        return "OpenAI"
    elif "claude" in model_lower or "anthropic" in model_lower:
        return "Anthropic"
    elif "gemini" in model_lower or "google" in model_lower:
        return "Google"
    elif "llama" in model_lower or "meta" in model_lower:
        return "Meta"
    elif "grok" in model_lower:
        return "xAI"
    elif "deepseek" in model_lower:
        return "DeepSeek"
    elif "mistral" in model_lower:
        return "Mistral"
    else:
        return "Unknown"


def _determine_tier(model_id: str) -> Literal["flagship", "standard", "free", "experimental"]:
    """Determine model tier based on model ID."""
    model_lower = model_id.lower()
    
    # Flagship models
    flagship_indicators = ["gpt-4", "gpt-5", "claude-3.5", "claude-opus", "gemini-pro", "grok-4"]
    if any(ind in model_lower for ind in flagship_indicators):
        return "flagship"
    
    # Free models
    free_indicators = ["free", "mini", "tiny", "small", "lite"]
    if any(ind in model_lower for ind in free_indicators):
        return "free"
    
    # Experimental
    experimental_indicators = ["preview", "beta", "experimental", "dev"]
    if any(ind in model_lower for ind in experimental_indicators):
        return "experimental"
    
    return "standard"


def _calculate_badge(rank: int, quality_score: float) -> Literal["gold", "silver", "bronze", "rising", "stable"]:
    """Calculate achievement badge based on rank and performance."""
    if rank == 1:
        return "gold"
    elif rank == 2:
        return "silver"
    elif rank == 3:
        return "bronze"
    elif quality_score >= 0.9:
        return "rising"
    else:
        return "stable"


def _transform_to_public_format(data: Dict[str, Any]) -> LeaderboardResponse:
    """Transform internal benchmark data to public leaderboard format."""
    model_results = data.get("model_results", [])
    benchmark_info = data.get("benchmark_info", {})
    
    rankings = []
    
    for idx, result in enumerate(model_results):
        model_name = result.get("model", "Unknown Model")
        summary = result.get("summary", {})
        
        # Calculate quality score from prompts
        prompts = result.get("prompts", [])
        quality_scores = [p.get("quality_score", 0) for p in prompts if p.get("quality_score")]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        
        success_rate = summary.get("success_rate", 1.0)
        avg_response_time = summary.get("average_response_time", 0.0)
        total_tokens = summary.get("total_tokens", 0)
        total_runs = summary.get("total_prompts", 1)
        
        performance = ModelPerformance(
            rank=idx + 1,
            modelName=model_name.split("/")[-1] if "/" in model_name else model_name,
            provider=_extract_provider(model_name),
            tier=_determine_tier(model_name),
            successRate=success_rate,
            qualityScore=avg_quality,
            avgResponseTime=avg_response_time,
            totalTokens=total_tokens,
            totalRuns=total_runs,
            lastUpdated=result.get("timestamp", datetime.now(timezone.utc).isoformat()),
            badge=_calculate_badge(idx + 1, avg_quality),
        )
        rankings.append(performance)
    
    # Sort by quality score descending
    rankings.sort(key=lambda x: (x.quality_score, x.success_rate), reverse=True)
    
    # Re-assign ranks after sorting
    for idx, r in enumerate(rankings):
        r.rank = idx + 1
        r.badge = _calculate_badge(r.rank, r.quality_score)
    
    # Calculate summary statistics
    avg_quality = sum(r.quality_score for r in rankings) / len(rankings) if rankings else 0
    avg_success = sum(r.success_rate for r in rankings) / len(rankings) if rankings else 0
    total_tokens = sum(r.total_tokens for r in rankings)
    
    summary = {
        "avgQualityScore": round(avg_quality, 3),
        "avgSuccessRate": round(avg_success, 3),
        "totalTokensConsumed": total_tokens,
        "topPerformer": rankings[0].model_name if rankings else "N/A",
        "benchmarkRunCount": sum(r.total_runs for r in rankings),
    }
    
    return LeaderboardResponse(
        generatedAt=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        totalModels=len(rankings),
        benchmarkVersion=benchmark_info.get("version", "2.0.0"),
        summary=summary,
        rankings=rankings,
    )


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get Public Leaderboard",
    description="Retrieve the public FBA-Bench Performance Index with all model rankings.",
)
async def get_public_leaderboard(
    limit: Optional[int] = Query(
        None, ge=1, le=100, description="Limit number of results"
    ),
    tier: Optional[Literal["flagship", "standard", "free", "experimental"]] = Query(
        None, description="Filter by model tier"
    ),
    provider: Optional[str] = Query(None, description="Filter by provider name"),
) -> LeaderboardResponse:
    """Get the public-facing leaderboard with optional filtering."""
    try:
        data = _load_benchmark_results()
        response = _transform_to_public_format(data)
        
        # Apply filters
        filtered_rankings = response.rankings
        
        if tier:
            filtered_rankings = [r for r in filtered_rankings if r.tier == tier]
        
        if provider:
            filtered_rankings = [
                r for r in filtered_rankings 
                if provider.lower() in r.provider.lower()
            ]
        
        if limit:
            filtered_rankings = filtered_rankings[:limit]
        
        # Re-rank after filtering
        for idx, r in enumerate(filtered_rankings):
            r.rank = idx + 1
        
        response.rankings = filtered_rankings
        response.total_models = len(filtered_rankings)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/leaderboard/top/{count}",
    response_model=List[ModelPerformance],
    summary="Get Top N Models",
    description="Retrieve the top N performing models.",
)
async def get_top_models(
    count: int = 10,
) -> List[ModelPerformance]:
    """Get the top N models from the leaderboard."""
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    
    data = _load_benchmark_results()
    response = _transform_to_public_format(data)
    return response.rankings[:count]


@router.get(
    "/leaderboard/model/{model_name}",
    response_model=ModelPerformance,
    summary="Get Model Details",
    description="Get detailed performance data for a specific model.",
)
async def get_model_details(
    model_name: str,
) -> ModelPerformance:
    """Get performance details for a specific model."""
    data = _load_benchmark_results()
    response = _transform_to_public_format(data)
    
    for ranking in response.rankings:
        if model_name.lower() in ranking.model_name.lower():
            return ranking
    
    raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")


@router.get(
    "/leaderboard/embed",
    response_model=EmbedWidget,
    summary="Get Embed Widget",
    description="Get an embeddable widget for the leaderboard.",
)
async def get_embed_widget(
    theme: Literal["dark", "light"] = Query("dark", description="Widget theme"),
    limit: int = Query(5, ge=1, le=10, description="Number of models to display"),
    request: Request = None,
) -> EmbedWidget:
    """Generate an embeddable widget for the leaderboard."""
    base_url = str(request.base_url) if request else "https://fba-bench.io"
    
    # Generate embed HTML
    html = f'''<iframe 
    src="{base_url}public/leaderboard/widget?theme={theme}&limit={limit}" 
    width="400" 
    height="600" 
    frameborder="0"
    style="border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.15);"
    title="FBA-Bench Performance Index">
</iframe>'''
    
    return EmbedWidget(html=html, width=400, height=600)


@router.get(
    "/leaderboard/widget",
    response_class=HTMLResponse,
    summary="Leaderboard Widget",
    description="Render the embeddable leaderboard widget.",
)
async def render_widget(
    theme: Literal["dark", "light"] = Query("dark", description="Widget theme"),
    limit: int = Query(5, ge=1, le=10, description="Number of models to display"),
) -> HTMLResponse:
    """Render an embeddable widget for the leaderboard."""
    data = _load_benchmark_results()
    response = _transform_to_public_format(data)
    rankings = response.rankings[:limit]
    
    # Generate widget HTML
    bg_color = "#0d1117" if theme == "dark" else "#ffffff"
    text_color = "#e6edf3" if theme == "dark" else "#1f2328"
    accent_color = "#00d2ff"
    
    rows_html = ""
    for r in rankings:
        badge_class = r.badge
        rows_html += f'''
        <tr>
            <td><span class="rank rank-{r.rank}">{r.rank}</span></td>
            <td>
                <div class="model-name">{r.model_name}</div>
                <div class="provider">{r.provider}</div>
            </td>
            <td><span class="score">{r.quality_score:.0%}</span></td>
        </tr>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FBA-Bench Top Models</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: {bg_color};
            color: {text_color};
            padding: 20px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .header h2 {{
            font-size: 1.1rem;
            background: linear-gradient(90deg, {accent_color}, #6e48aa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 4px;
        }}
        .header p {{
            font-size: 0.75rem;
            opacity: 0.6;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        th {{
            font-size: 0.7rem;
            text-transform: uppercase;
            opacity: 0.5;
        }}
        .rank {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            font-weight: 700;
            font-size: 0.85rem;
        }}
        .rank-1 {{ background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; }}
        .rank-2 {{ background: linear-gradient(135deg, #C0C0C0, #A0A0A0); color: #000; }}
        .rank-3 {{ background: linear-gradient(135deg, #CD7F32, #8B4513); color: #fff; }}
        .model-name {{
            font-weight: 600;
            font-size: 0.9rem;
        }}
        .provider {{
            font-size: 0.7rem;
            opacity: 0.5;
        }}
        .score {{
            font-weight: 700;
            color: {accent_color};
            font-size: 1rem;
        }}
        .footer {{
            text-align: center;
            margin-top: 16px;
            font-size: 0.7rem;
            opacity: 0.4;
        }}
        .footer a {{
            color: {accent_color};
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h2>FBA-Bench Performance Index</h2>
        <p>AI Business Agent Rankings</p>
    </div>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Model</th>
                <th>Score</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div class="footer">
        Powered by <a href="https://github.com/fba-bench" target="_blank">FBA-Bench</a>
    </div>
</body>
</html>'''
    
    return HTMLResponse(content=html)


@router.get(
    "/stats",
    summary="Get Platform Statistics",
    description="Get aggregate platform statistics for the Performance Index.",
)
async def get_platform_stats() -> Dict[str, Any]:
    """Get aggregate platform statistics."""
    data = _load_benchmark_results()
    benchmark_info = data.get("benchmark_info", {})
    model_results = data.get("model_results", [])
    
    total_tokens = 0
    total_prompts = 0
    unique_providers = set()
    
    for result in model_results:
        summary = result.get("summary", {})
        total_tokens += summary.get("total_tokens", 0)
        total_prompts += summary.get("total_prompts", 0)
        model = result.get("model", "")
        if "/" in model:
            unique_providers.add(model.split("/")[0])
    
    return {
        "platform": "FBA-Bench Performance Index",
        "version": "2.0.0",
        "stats": {
            "totalModels": len(model_results),
            "totalProviders": len(unique_providers),
            "totalBenchmarkRuns": total_prompts,
            "totalTokensProcessed": total_tokens,
            "lastBenchmarkTimestamp": benchmark_info.get("timestamp"),
            "benchmarkDurationSeconds": benchmark_info.get("total_duration"),
        },
        "providers": list(unique_providers),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }
