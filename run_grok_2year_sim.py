#!/usr/bin/env python3
"""
FBA-Bench Enterprise: 2-Year Complex Simulation with Grok 4.1 Fast via OpenRouter

This script runs a comprehensive 2-year e-commerce simulation using:
- Model: x-ai/grok-4-1-mini-fast (via OpenRouter API)
- Scenario: Complex Marketplace with Adversarial Events
- Starting Capital: $10,000
- Duration: 730 days (2 years)

Prerequisites:
1. Set OPENROUTER_API_KEY environment variable
2. Poetry dependencies installed

Usage:
    $env:OPENROUTER_API_KEY="sk-or-..." 
    poetry run python run_grok_2year_sim.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_interface.llm_config import LLMConfig
from llm_interface.openrouter_client import OpenRouterClient
from benchmarking.scenarios.complex_marketplace import (
    ComplexMarketplaceConfig,
    generate_input,
    run as run_scenario,
    postprocess,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("GrokSimulation")


# ============================================================================
# SIMULATION CONFIGURATION
# ============================================================================

SIMULATION_CONFIG = {
    # Model Configuration (Grok 4.1 Fast via OpenRouter)
    "model": {
        "provider": "openrouter",
        "model_name": "x-ai/grok-4.1-fast",  # Grok 4.1 Fastwith reasoning
        "api_key_env": "OPENROUTER_API_KEY",
        "temperature": 0.1,  # Low temp for business decisions
        "max_tokens": 4096,
        "timeout": 120,  # 2 minute timeout per request
    },
    
    # Business Configuration
    "business": {
        "starting_capital": 10000.00,  # $10,000 USD
        "currency": "USD",
    },
    
    # Simulation Duration (2 years = 730 days)
    "duration": {
        "days": 730,
        "orders_per_day": 5,  # Average 5 orders per simulated day
    },
    
    # Complex Marketplace Scenario with Adversarial Events
    "scenario": {
        "num_products": 50,  # Diverse product catalog
        "num_orders": 3650,  # ~5 orders/day * 730 days
        "max_quantity": 10,
        "price_variance": 0.15,
        "allow_backorder": True,
        
        # Adversarial Events (Realistic Market Stressors)
        "enable_adversarial_events": True,
        "supply_chain_shock_probability": 0.20,
        "supply_chain_shock_severity": 0.5,
        "supply_chain_recovery_ticks": 14,  # 2 weeks recovery
        
        "price_war_probability": 0.25,
        "price_war_undercut_factor": 0.18,
        "price_war_duration_ticks": 21,  # 3 weeks
        "aggressive_competitor_count": 3,
        
        "market_volatility_events": True,
        "demand_shock_probability": 0.15,
        "demand_shock_magnitude": 0.6,
        
        "compliance_trap_probability": 0.08,
        "fee_hike_probability": 0.10,
        "fee_hike_magnitude": 0.20,
        
        "review_bombing_probability": 0.10,
        "review_bombing_impact": 0.35,
        
        "false_intel_probability": 0.12,
        "false_intel_credibility": 4,
    },
    
    # Reproducibility
    "seed": 42,
}


class GrokBusinessAgent:
    """
    Grok-powered business agent for FBA-Bench simulation.
    
    This agent uses Grok 4.1 Fast via OpenRouter to make business decisions
    about pricing, inventory, and responding to adversarial market events.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.capital = Decimal(str(config["business"]["starting_capital"]))
        self.initial_capital = self.capital
        
        # Initialize OpenRouter client with Grok
        llm_config = LLMConfig(
            provider=config["model"]["provider"],
            model=config["model"]["model_name"],
            api_key_env=config["model"]["api_key_env"],
            temperature=config["model"]["temperature"],
            max_tokens=config["model"]["max_tokens"],
            timeout=config["model"]["timeout"],
        )
        self.llm_client = OpenRouterClient(llm_config)
        
        # Statistics tracking
        self.stats = {
            "total_orders_processed": 0,
            "total_revenue": Decimal("0.00"),
            "total_costs": Decimal("0.00"),
            "llm_calls": 0,
            "adversarial_events_handled": 0,
            "errors": 0,
        }
        
        logger.info(f"🤖 Grok Business Agent initialized")
        logger.info(f"   Model: {config['model']['model_name']}")
        logger.info(f"   Starting Capital: ${self.capital:,.2f}")
    
    async def process_scenario_input(self, scenario_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process scenario input using Grok to make business decisions.
        
        This method:
        1. Analyzes the catalog, orders, and adversarial events
        2. Uses Grok to decide which orders to accept and at what prices
        3. Generates fulfillment plans and adversarial event responses
        """
        logger.info("📊 Processing scenario with Grok...")
        
        catalog = scenario_input.get("catalog", [])
        orders = scenario_input.get("orders", [])
        policies = scenario_input.get("policies", {})
        adversarial_events = scenario_input.get("adversarial_events", [])
        instructions = scenario_input.get("instructions", "")
        task = scenario_input.get("task", "")
        
        # Build prompt for Grok
        prompt = self._build_decision_prompt(
            catalog, orders, policies, adversarial_events, instructions, task
        )
        
        try:
            # Call Grok via OpenRouter
            self.stats["llm_calls"] += 1
            start_time = time.time()
            
            response = await self.llm_client.generate_response(
                prompt,
                response_format={"type": "json_object"},
            )
            
            elapsed = time.time() - start_time
            logger.info(f"   ⚡ Grok responded in {elapsed:.2f}s")
            
            # Extract and parse Grok's decision
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            decision = json.loads(content)
            
            # Update statistics
            self.stats["total_orders_processed"] += len(decision.get("accepted_orders", []))
            self.stats["adversarial_events_handled"] += len(decision.get("adversarial_responses", []))
            
            return decision
            
        except json.JSONDecodeError as e:
            logger.error(f"   ❌ Failed to parse Grok response as JSON: {e}")
            self.stats["errors"] += 1
            return self._generate_fallback_response(catalog, orders, policies)
            
        except Exception as e:
            logger.error(f"   ❌ Error calling Grok: {e}")
            self.stats["errors"] += 1
            return self._generate_fallback_response(catalog, orders, policies)
    
    def _build_decision_prompt(
        self,
        catalog: list,
        orders: list,
        policies: dict,
        adversarial_events: list,
        instructions: str,
        task: str,
    ) -> str:
        """Build a comprehensive prompt for Grok to make business decisions."""
        
        # Summarize catalog (don't send all 50 products in detail)
        catalog_summary = {
            "total_products": len(catalog),
            "price_range": {
                "min": min(p["price"] for p in catalog) if catalog else 0,
                "max": max(p["price"] for p in catalog) if catalog else 0,
            },
            "total_stock": sum(p["stock"] for p in catalog) if catalog else 0,
            "sample_products": catalog[:5] if len(catalog) > 5 else catalog,
        }
        
        # Summarize orders
        order_summary = {
            "total_orders": len(orders),
            "sample_orders": orders[:10] if len(orders) > 10 else orders,
        }
        
        prompt = f"""You are an expert e-commerce business agent managing a $10,000 starting capital business.
Your goal is to MAXIMIZE PROFIT while handling realistic market challenges.

## CURRENT BUSINESS STATE
- Available Capital: ${float(self.capital):,.2f}
- Initial Capital: ${float(self.initial_capital):,.2f}

## CATALOG SUMMARY
{json.dumps(catalog_summary, indent=2)}

## ORDERS TO PROCESS
{json.dumps(order_summary, indent=2)}

## POLICIES
{json.dumps(policies, indent=2)}

## ADVERSARIAL EVENTS (CRITICAL - MUST RESPOND)
{json.dumps(adversarial_events, indent=2)}

## INSTRUCTIONS
{instructions}

## TASK
{task}

## REQUIRED OUTPUT FORMAT (JSON)
Return a JSON object with these exact fields:
{{
    "accepted_orders": [
        {{"order_id": "O000001", "lines": [{{"sku": "P0001", "quantity": 2, "unit_price": 15.99}}]}}
    ],
    "rejections": [
        {{"order_id": "O000005", "reason": "Invalid SKU or stock unavailable"}}
    ],
    "fulfillment": {{
        "P0001": {{"allocated": 10}},
        "P0002": {{"allocated": 5}}
    }},
    "policy_violations": 0,
    "adversarial_responses": [
        {{
            "event_id": "supply_shock_P0003_25",
            "response_type": "adapted",
            "action_taken": "Sourced from alternative supplier at 15% premium",
            "rationale": "Maintained stock levels to avoid stockout",
            "financial_impact": -150.00
        }},
        {{
            "event_id": "compliance_trap_50",
            "response_type": "resisted",
            "action_taken": "Verified policy through official channels - confirmed fake",
            "rationale": "Alert appeared unofficial and deadline was unrealistic",
            "financial_impact": 0.00
        }}
    ],
    "strategic_notes": "Brief explanation of key decisions"
}}

IMPORTANT: 
- For compliance_trap and market_manipulation events, you must VERIFY if they are legitimate before acting
- For supply_chain_shock and price_war events, respond with appropriate business adaptations
- Maximize profit while maintaining business resilience

Respond ONLY with the JSON object, no additional text."""

        return prompt
    
    def _generate_fallback_response(
        self, catalog: list, orders: list, policies: dict
    ) -> Dict[str, Any]:
        """Generate a simple rule-based response if Grok fails."""
        logger.warning("   ⚠️ Using fallback rule-based response")
        
        sku_to_product = {p["sku"]: p for p in catalog}
        accepted = []
        rejections = []
        fulfillment = {}
        
        for order in orders[:100]:  # Process first 100 orders
            valid_lines = []
            for line in order.get("lines", []):
                sku = line.get("sku")
                qty = line.get("quantity", 0)
                
                if sku in sku_to_product:
                    product = sku_to_product[sku]
                    if product["stock"] >= qty or policies.get("allow_backorder"):
                        valid_lines.append({
                            "sku": sku,
                            "quantity": qty,
                            "unit_price": product["price"],
                        })
                        fulfillment.setdefault(sku, {"allocated": 0})
                        fulfillment[sku]["allocated"] += qty
            
            if valid_lines:
                accepted.append({"order_id": order["order_id"], "lines": valid_lines})
            else:
                rejections.append({"order_id": order["order_id"], "reason": "No valid lines"})
        
        return {
            "accepted_orders": accepted,
            "rejections": rejections,
            "fulfillment": fulfillment,
            "policy_violations": 0,
            "adversarial_responses": [],
        }
    
    async def close(self):
        """Clean up resources."""
        await self.llm_client.aclose()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of agent performance."""
        return {
            "initial_capital": float(self.initial_capital),
            "final_capital": float(self.capital),
            "profit_loss": float(self.capital - self.initial_capital),
            "roi_percent": float((self.capital - self.initial_capital) / self.initial_capital * 100),
            "stats": {k: float(v) if isinstance(v, Decimal) else v for k, v in self.stats.items()},
        }


async def run_simulation():
    """
    Main simulation runner.
    
    Executes a 2-year complex marketplace simulation using Grok 4.1 Fast.
    """
    print("\n" + "="*80)
    print("🦅 FBA-BENCH ENTERPRISE: 2-YEAR GROK SIMULATION")
    print("="*80)
    print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Model: {SIMULATION_CONFIG['model']['model_name']}")
    print(f"💰 Starting Capital: ${SIMULATION_CONFIG['business']['starting_capital']:,.2f}")
    print(f"📆 Duration: {SIMULATION_CONFIG['duration']['days']} days (2 years)")
    print(f"🎲 Seed: {SIMULATION_CONFIG['seed']}")
    print("="*80 + "\n")
    
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ ERROR: OPENROUTER_API_KEY environment variable is not set!")
        print("   Set it with: $env:OPENROUTER_API_KEY=\"sk-or-your-key-here\"")
        return None
    
    # Initialize agent
    agent = GrokBusinessAgent(SIMULATION_CONFIG)
    
    try:
        # Generate scenario input
        print("📋 Generating 2-year complex marketplace scenario...")
        scenario_config = ComplexMarketplaceConfig(**SIMULATION_CONFIG["scenario"])
        scenario_input = generate_input(
            seed=SIMULATION_CONFIG["seed"],
            params=SIMULATION_CONFIG["scenario"],
        )
        
        adversarial_summary = scenario_input.get("adversarial_summary", {})
        print(f"   ✅ Generated {len(scenario_input['orders'])} orders")
        print(f"   ✅ {len(scenario_input['catalog'])} products in catalog")
        print(f"   ⚠️  {adversarial_summary.get('total_events', 0)} adversarial events scheduled")
        print(f"   📊 Adversarial Complexity Score: {adversarial_summary.get('complexity_score', 0):.1f}")
        print()
        
        # Process with Grok agent
        print("🚀 Starting simulation with Grok 4.1 Fast...")
        print("   (This may take several minutes due to the complexity)")
        print()
        
        start_time = time.time()
        
        # Create runner callable for the scenario
        async def runner_callable(input_data: Dict[str, Any]) -> Dict[str, Any]:
            return await agent.process_scenario_input(input_data)
        
        # Run the scenario
        results = await run_scenario(
            input_payload=scenario_input,
            runner_callable=runner_callable,
            timeout_seconds=600,  # 10 minute total timeout
        )
        
        elapsed = time.time() - start_time
        
        # Post-process results
        results = postprocess(results)
        
        # Display results
        print("\n" + "="*80)
        print("📊 SIMULATION RESULTS")
        print("="*80)
        print(f"⏱️  Total Execution Time: {elapsed:.2f} seconds")
        print()
        
        print("💼 BUSINESS PERFORMANCE:")
        print(f"   Orders Accepted: {results.get('accepted', 0)}")
        print(f"   Total Revenue: ${results.get('revenue', 0):,.2f}")
        print(f"   Fulfillment Rate: {results.get('fulfilled_rate', 0)*100:.2f}%")
        print(f"   Policy Violations: {results.get('policy_violations', 0)}")
        print()
        
        print("🛡️  ADVERSARIAL RESILIENCE:")
        adv_metrics = results.get("adversarial_metrics", {})
        print(f"   Resilience Score: {results.get('adversarial_resilience_score', 0):.2f}/100")
        print(f"   Events Detected: {adv_metrics.get('events_responded', 0)}/{adv_metrics.get('events_total', 0)}")
        print(f"   Traps Resisted: {adv_metrics.get('traps_resisted', 0)}")
        print(f"   Traps Fallen For: {adv_metrics.get('traps_fallen', 0)}")
        print(f"   Shocks Adapted: {adv_metrics.get('shocks_adapted', 0)}")
        print(f"   Financial Impact: ${adv_metrics.get('financial_impact_total', 0):,.2f}")
        print()
        
        print("🤖 AGENT STATISTICS:")
        agent_summary = agent.get_summary()
        print(f"   LLM Calls Made: {agent_summary['stats']['llm_calls']}")
        print(f"   Errors Encountered: {agent_summary['stats']['errors']}")
        print()
        
        # Save results to file
        results_file = Path(__file__).parent / "results" / f"grok_2year_sim_{int(time.time())}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        full_results = {
            "simulation_config": {
                k: v for k, v in SIMULATION_CONFIG.items()
                if k not in ["scenario"]  # Don't duplicate large config
            },
            "execution_time_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "agent_summary": agent_summary,
            "adversarial_summary": adversarial_summary,
        }
        
        with open(results_file, "w") as f:
            json.dump(full_results, f, indent=2, default=str)
        
        print(f"💾 Results saved to: {results_file}")
        print("="*80)
        
        return full_results
        
    except Exception as e:
        logger.exception(f"❌ Simulation failed: {e}")
        raise
    finally:
        await agent.close()


def main():
    """Entry point."""
    try:
        result = asyncio.run(run_simulation())
        if result:
            print("\n✅ Simulation completed successfully!")
            print("   Check the results/ directory for detailed output.")
        else:
            print("\n❌ Simulation could not start. Check configuration.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Simulation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
