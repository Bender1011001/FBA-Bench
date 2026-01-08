#!/usr/bin/env python3
"""
FBA-Bench LLM Benchmark

Tests raw LLM reasoning capability on FBA pricing decisions.
No agent scaffolding, no tools, no memory - just the LLM.

For agentic benchmarks (multi-step, tools, memory), see: Agent Benchmark

Usage:
    python scripts/run_llm_benchmark.py
    
Requires OPENROUTER_API_KEY in environment or .env file.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from llm_interface.generic_openai_client import GenericOpenAIClient
from leaderboard.score_tracker import ScoreTracker
from leaderboard.leaderboard_manager import LeaderboardManager
from leaderboard.leaderboard_renderer import LeaderboardRenderer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OpenRouter configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ============================================================================
# RAW LLM BENCHMARK - Minimal Scaffolding
# ============================================================================
# This benchmark tests the raw reasoning capability of LLMs with a single
# FBA pricing prompt. No agent memory, no tools, no multi-turn conversation.
# 
# For agentic systems (multi-step, tool-use, memory), see: Agent Benchmark
# ============================================================================

# Top models to benchmark (OpenRouter slugs - December 2026)
# NOTE: Only models we DON'T already have in scores.json
TOP_MODELS = [
    # === NEW: Frontier Models ===
    {
        "name": "GPT-5.2",
        "slug": "openai/gpt-5.2",
        "tier": "T3",
        "category": "frontier",
    },
    {
        "name": "Grok 4.1 Fast",
        "slug": "x-ai/grok-4.1-fast",
        "tier": "T3",
        "category": "frontier",
    },
    {
        "name": "DeepSeek R1",
        "slug": "deepseek/deepseek-r1-0528:free",
        "tier": "T2",
        "category": "strong",
    },
    # The following are FREE tier - minimal cost
    {
        "name": "Gemini 2.0 Flash",
        "slug": "google/gemini-2.0-flash-exp:free",
        "tier": "T2",
        "category": "free",
    },
]

# Test scenario prompt - FBA pricing decision
TEST_PROMPT = """You are an expert FBA (Fulfillment by Amazon) pricing agent. 
Your goal is to maximize profit while maintaining competitive positioning.

CURRENT STATE:
- Product ASIN: B0EXAMPLE123
- Current Price: $24.99
- Cost: $12.50
- Inventory: 150 units
- Sales Rank: #1,245
- Competitor Price: $23.99
- Market Trend: Upward demand
- Days of Stock: 45

TASK: Analyze the market conditions and make a pricing decision.

Respond with ONLY a JSON object in this exact format:
{
    "decisions": [
        {
            "asin": "B0EXAMPLE123",
            "new_price": <number>,
            "reasoning": "<brief explanation>"
        }
    ],
    "meta": {
        "confidence": <0.0-1.0>,
        "market_analysis": "<brief market summary>"
    }
}
"""


async def run_single_model(api_key: str, model_config: dict) -> dict:
    """Run benchmark on a single model and return results."""
    model_name = model_config["name"]
    model_slug = model_config["slug"]
    
    logger.info(f"🚀 Running benchmark for {model_name} ({model_slug})...")
    
    start_time = datetime.now()
    
    try:
        # Create client for this model
        client = GenericOpenAIClient(
            model_name=model_slug,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            cost_tracker=None,
        )
        
        # Make the API call
        result = await client.generate_response(
            prompt=TEST_PROMPT,
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Extract response
        output = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        
        # Try to parse the JSON response
        try:
            parsed = json.loads(output)
            confidence = parsed.get("meta", {}).get("confidence", 0.5)
            decisions = parsed.get("decisions", [])
            
            # Calculate a score based on response quality
            score = 50.0  # Base score
            if decisions:
                score += 20.0  # Has decisions
                decision = decisions[0]
                if "new_price" in decision:
                    price = float(decision.get("new_price", 0))
                    # Reward reasonable pricing (between cost and current)
                    if 12.50 <= price <= 30.00:
                        score += 10.0
                if "reasoning" in decision and len(decision.get("reasoning", "")) > 20:
                    score += 10.0  # Has good reasoning
            if confidence and float(confidence) > 0.7:
                score += 5.0  # High confidence
            if "market_analysis" in parsed.get("meta", {}):
                score += 5.0  # Has market analysis
                
        except json.JSONDecodeError:
            score = 35.0  # Penalty for non-JSON response
            confidence = 0.3
            
        logger.info(f"✅ {model_name}: Score={score:.1f}, Duration={duration:.2f}s, Tokens={total_tokens}")
        
        # Close client
        await client.http_client.aclose()
        
        return {
            "model_name": model_name,
            "model_slug": model_slug,
            "tier": model_config["tier"],
            "category": model_config["category"],
            "score": score,
            "duration": duration,
            "tokens": total_tokens,
            "success": True,
            "verified": True,  # Raw LLM = Verified (no agent scaffolding)
            "output_preview": output[:300] + "..." if len(output) > 300 else output,
        }
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.exception(f"❌ {model_name}: Exception - {e}")
        return {
            "model_name": model_name,
            "model_slug": model_slug,
            "tier": model_config["tier"],
            "category": model_config["category"],
            "score": 0.0,
            "duration": duration,
            "tokens": 0,
            "success": False,
            "verified": True,
            "error": str(e),
        }


async def main():
    """Run the full benchmark."""
    print("=" * 70)
    print("🧠 FBA-Bench Enterprise: LLM Benchmark")
    print("   Raw LLM reasoning - no agent scaffolding")
    print("=" * 70)
    
    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY not found in environment.")
        print("   Set it in .env or export OPENROUTER_API_KEY=sk-or-...")
        return 1
    
    print(f"✓ OpenRouter API key found (ends with ...{api_key[-4:]})")
    print(f"✓ Testing {len(TOP_MODELS)} top-tier models")
    print()
    
    results = []
    
    for model_config in TOP_MODELS:
        result = await run_single_model(api_key, model_config)
        results.append(result)
        print()
    
    # Summary
    print("=" * 70)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("=" * 70)
    
    successful = [r for r in results if r.get("success")]
    
    for r in results:
        status = "✅" if r.get("success") else "❌"
        verified = "🔒 VERIFIED" if r.get("verified") else ""
        print(f"{status} {r['model_name']:20} Score={r['score']:5.1f}  {verified}")
    
    print()
    print(f"Total: {len(successful)}/{len(results)} successful")
    
    # Update leaderboard with verified results
    if successful:
        print()
        print("📝 Updating Leaderboard with VERIFIED results...")
        
        tracker = ScoreTracker()
        
        for r in successful:
            tracker.add_run_result(
                bot_name=r["model_name"],
                tier=r["tier"],
                score=r["score"],
                run_details={
                    "duration": r["duration"],
                    "model_slug": r["model_slug"],
                    "tokens": r["tokens"],
                    "category": r["category"],
                    "benchmark_type": "raw_llm",  # Not agentic
                },
                verified=r["verified"],  # This marks them as VERIFIED on leaderboard
            )
        
        # Generate leaderboard artifacts
        renderer = LeaderboardRenderer()
        manager = LeaderboardManager(tracker, renderer)
        await manager.generate_leaderboard_artifacts()
        
        print("✅ Leaderboard updated!")
        print("   → artifacts/leaderboard.json")
        print("   → artifacts/leaderboard.html")
        print()
        print("   Look for the 'VERIFIED LLM' badge next to each model name!")
    
    # Save raw results
    results_path = Path("artifacts/top_models_verified_results.json")
    results_path.parent.mkdir(exist_ok=True)
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "models_tested": len(TOP_MODELS),
            "successful": len(successful),
            "results": results,
        }, f, indent=2)
    
    print(f"📄 Raw results saved to {results_path}")
    
    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
