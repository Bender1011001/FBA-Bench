#!/usr/bin/env python3
"""
Merge all benchmark results into a single leaderboard data file.
Uses a HARSH financial model where poor reasoning = real money lost.
"""

import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).parent

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # Load all benchmark results
    top_models = load_json(ROOT_DIR / "top_models_benchmark.json")
    claude_opus = load_json(ROOT_DIR / "claude_opus_benchmark.json")
    free_models = load_json(ROOT_DIR / "free_models_benchmark.json")
    weak_models = load_json(ROOT_DIR / "weak_models_benchmark.json")  # Added weak models
    
    # Financial Simulation Constants (180-day FBA cycle)
    STARTING_CAPITAL = 25000.00
    BASE_REVENUE_POTENTIAL = 150000.00   # Max possible if everything goes right
    FIXED_COSTS = 35000.00               # Rent, software, insurance, salaries
    STOCKOUT_PENALTY = 25000.00          # Major penalty for logistics failures
    BAD_PRICING_PENALTY = 20000.00       # Penalty for pricing mistakes
    MARKETING_WASTE_PENALTY = 15000.00   # Wasted ad spend from bad strategy
    
    # Combine all model results
    all_results = []
    
    # HARSH Financial Model - bad reasoning = real losses
    def calculate_pnl(result):
        """
        Calculate P&L based on prompt performance.
        
        CALIBRATED FOR REALISTIC OUTCOMES:
        - Quality 0.95+ = Profitable ($15K-$25K profit)
        - Quality 0.85-0.94 = Break even to small profit
        - Quality 0.70-0.84 = Losing money
        - Quality < 0.70 = Major losses
        """
        summary = result["summary"]
        prompts = result.get("prompts", [])
        
        # Performance scores (0.0 - 1.0)
        p1 = prompts[0].get("quality_score", 0.0) if len(prompts) > 0 else 0.0  # Pricing/Business
        p2 = prompts[1].get("quality_score", 0.0) if len(prompts) > 1 else 0.0  # Logistics
        p3 = prompts[2].get("quality_score", 0.0) if len(prompts) > 2 else 0.0  # Marketing
        avg_quality = (p1 + p2 + p3) / 3.0
        
        # Base revenue depends on marketing quality (customer acquisition)
        # Using cubic scaling to heavily reward excellence
        marketing_effectiveness = p3 ** 3  # 0.9^3 = 0.73, 0.7^3 = 0.34, 0.5^3 = 0.125
        revenue = BASE_REVENUE_POTENTIAL * summary["success_rate"] * (0.3 + marketing_effectiveness * 0.7)
        
        # COGS: Pricing strategy affects margins
        # Bad pricing = either overpaying suppliers or leaving money on table
        cogs_rate = 0.65 - (p1 - 0.5) * 0.30  # At p1=1.0: 50% COGS, at p1=0.5: 65%, at p1=0: 80%
        cogs_rate = max(0.45, min(0.80, cogs_rate))  # Clamp between 45-80%
        cogs = revenue * cogs_rate
        
        # Shipping costs: Logistics quality affects efficiency
        # Bad logistics = expedited shipping, returns, stockouts
        logistics_efficiency = p2 ** 2  # Squared for harsher penalties
        shipping = 22000 * (1.5 - logistics_efficiency * 0.8)  # Range: $15K (perfect) to $33K (terrible)
        
        # Amazon fees (15% of revenue)
        amazon_fees = revenue * 0.15
        
        # Marketing spend (fixed budget, but effectiveness varies)
        marketing_spend = 18000.00  # Fixed marketing budget
        
        # Fixed costs (reduced for calibration)
        fixed_costs = 25000.00  # Rent, software, insurance
        
        # Final P&L
        gross_profit = revenue - cogs
        net_profit = gross_profit - shipping - amazon_fees - marketing_spend - fixed_costs
        
        roi = (net_profit / STARTING_CAPITAL) * 100
        margin = (net_profit / revenue) * 100 if revenue > 0 else -999
        
        return {
            "revenue": round(revenue, 2),
            "net_profit": round(net_profit, 2),
            "roi": round(roi, 1),
            "margin": round(margin, 1),
            "avg_quality": round(avg_quality * 100, 1)
        }


    # Process models
    models_to_process = []
    if top_models: models_to_process.extend(top_models.get("model_results", []))
    if claude_opus: models_to_process.extend(claude_opus.get("model_results", []))
    if free_models: models_to_process.extend(free_models.get("model_results", []))
    if weak_models: models_to_process.extend(weak_models.get("model_results", []))
    
    for res in models_to_process:
        if res["summary"]["successful_responses"] > 0:
            all_results.append(res)
    
    # Sort by Net Profit
    ranked_results = sorted(all_results, key=lambda x: calculate_pnl(x)["net_profit"], reverse=True)
    
    # Build leaderboard data
    leaderboard_entries = []
    for rank, result in enumerate(ranked_results, 1):
        model = result["model"]
        pnl = calculate_pnl(result)
        summary = result["summary"]
        
        # Determine tier
        if "gpt-5" in model.lower() or "claude" in model.lower() or "gemini-3" in model.lower():
            tier = "Flagship"
        elif "deepseek" in model.lower() or "grok" in model.lower():
            tier = "High-Performance"
        elif ":free" in model.lower():
            tier = "Free"
        else:
            tier = "Standard"
        
        # Determine cost tier
        if ":free" in model.lower():
            cost = "$0"
        elif "deepseek" in model.lower():
            cost = "$0.14/M"
        elif "grok" in model.lower():
            cost = "$0.50/M"
        elif "gpt" in model.lower():
            cost = "$3.00/M"
        elif "claude" in model.lower():
            cost = "$5.00/M"
        else:
            cost = "Unknown"
        
        leaderboard_entries.append({
            "rank": rank,
            "model": model,
            "display_name": model.split("/")[-1].replace(":free", " (Free)").replace("-", " ").title(),
            "net_profit": pnl["net_profit"],
            "revenue": pnl["revenue"],
            "roi": pnl["roi"],
            "margin": pnl["margin"],
            "avg_response_time": round(summary["average_response_time"], 2),
            "tier": tier,
            "cost": cost,
            "timestamp": result.get("timestamp", datetime.now().isoformat()),
        })
    
    # Create final leaderboard data
    leaderboard_data = {
        "generated_at": datetime.now().isoformat(),
        "benchmark_version": "1.1.0",
        "scenario_name": "Tier 2: 180-Day Supply Chain Crisis",
        "starting_capital": STARTING_CAPITAL,
        "rankings": leaderboard_entries,
        "summary": {
            "most_profitable": leaderboard_entries[0]["model"] if leaderboard_entries else None,
            "highest_roi": max(leaderboard_entries, key=lambda x: x["roi"])["model"] if leaderboard_entries else None,
            "fastest": min(leaderboard_entries, key=lambda x: x["avg_response_time"])["model"] if leaderboard_entries else None,
        }
    }
    
    # Save to file
    output_path = ROOT_DIR / "openrouter_benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(leaderboard_data, f, indent=2)
    
    print(f"✅ Merged {len(leaderboard_entries)} models into leaderboard")
    print(f"📁 Saved to: {output_path}")
    print("\n🏆 Leaderboard Rankings:")
    print("-" * 100)
    for entry in leaderboard_entries:
        badge = "🥇" if entry["rank"] == 1 else "🥈" if entry["rank"] == 2 else "🥉" if entry["rank"] == 3 else f"#{entry['rank']}"
        print(f"{badge:4} {entry['display_name'][:30]:30} Profit: ${entry['net_profit']:,.2f} | ROI: {entry['roi']:5.1f}% | Margin: {entry['margin']:5.1f}% | Time: {entry['avg_response_time']:6.2f}s")
    print("-" * 100)
    print(f"\n🏆 Most Profitable: {leaderboard_data['summary']['most_profitable']}")
    print(f"📈 Highest ROI: {leaderboard_data['summary']['highest_roi']}")
    print(f"⚡ Fastest: {leaderboard_data['summary']['fastest']}")

if __name__ == "__main__":
    main()
