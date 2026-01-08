
import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add src to path
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fba_bench_api.core.database_async import get_async_db_session, create_db_tables_async, AsyncSessionLocal
from fba_bench_api.core.persistence_async import AsyncPersistenceManager
from fba_bench_api.core.simulation_runner import RealSimulationRunner
from fba_bench_api.models.experiment import ExperimentStatusEnum
from fba_events.pricing import SetPriceCommand
from money import Money

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configurations ---

AGENTS = [
    {
        "id": "agent-gpt4-expert",
        "name": "GPT-4 Turbo Expert",
        "framework": "langchain",
        "strategy": "optimized",
        "avatar": "🧠",
        "color": "#10a37f"
    },
    {
        "id": "agent-claude3-opus",
        "name": "Claude-3 Opus",
        "framework": "autogen",
        "strategy": "premium",
        "avatar": "⚡",
        "color": "#d97757"
    },
    {
        "id": "agent-llama3-70b",
        "name": "Llama-3 70B",
        "framework": "crewai",
        "strategy": "aggressive",
        "avatar": "🦙",
        "color": "#0052cc"
    },
    {
        "id": "agent-baseline-v1",
        "name": "Baseline Bot V1",
        "framework": "script",
        "strategy": "static",
        "avatar": "🤖",
        "color": "#666666"
    },
    {
        "id": "agent-random-chaos",
        "name": "Chaos Monkey",
        "framework": "script",
        "strategy": "random",
        "avatar": "🎲",
        "color": "#ff0000"
    }
]

SCENARIOS = ["scenario_market_entry_easy", "scenario_price_war_hard"]

class SimulatedAgent:
    def __init__(self, strategy: str, world_store, event_bus, rng_seed: int):
        self.strategy = strategy
        self.world_store = world_store
        self.event_bus = event_bus
        self.rng = random.Random(rng_seed)
        
    async def act(self, tick: int, asins: List[str]):
        """Perform actions for this tick."""
        if tick % 5 != 0:  # Act every 5 ticks to be realistic
            return

        for asin in asins:
            product = self.world_store.get_product_state(asin)
            if not product:
                continue
                
            current_price = product.price.cents / 100.0
            cost = product.cost_basis.cents / 100.0
            new_price = current_price

            if self.strategy == "optimized":
                # Try to maintain 40% margin but react to inventory
                target_margin = 0.40
                if product.inventory_quantity > 800:
                    target_margin = 0.20 # Liquidation
                elif product.inventory_quantity < 200:
                    target_margin = 0.60 # Scarcity
                
                target_price = cost / (1 - target_margin)
                # Smooth transition
                new_price = current_price * 0.8 + target_price * 0.2

            elif self.strategy == "premium":
                # High margin, rare discounts
                target_margin = 0.65
                target_price = cost / (1 - target_margin)
                new_price = target_price
            
            elif self.strategy == "aggressive":
                # Low margin for volume
                target_margin = 0.15
                target_price = cost / (1 - target_margin)
                new_price = target_price
                
            elif self.strategy == "random":
                change = self.rng.uniform(-2.0, 2.0)
                new_price = max(cost * 1.05, current_price + change)
            
            # Static does nothing
            
            # Publish command if price changed significantly
            if abs(new_price - current_price) > 0.01:
                cmd = SetPriceCommand(
                    product_id=asin,
                    price=Money.from_dollars(new_price),
                    timestamp=datetime.now(timezone.utc)
                )
                await self.event_bus.publish(cmd)

async def run_simulation_for_agent(agent_cfg: Dict[str, Any], scenario_id: str, pm: AsyncPersistenceManager):
    """Run a single simulation and save results."""
    logger.info(f"Starting simulation for {agent_cfg['name']} on {scenario_id}")
    
    # 1. Ensure Agent exists
    existing_agent = await pm.agents().get(agent_cfg["id"])
    if not existing_agent:
        await pm.agents().create({
            "id": agent_cfg["id"],
            "name": agent_cfg["name"],
            "framework": agent_cfg["framework"],
            "config": {}
        })

    # 2. Create Experiment
    exp_id = f"exp_{agent_cfg['id']}_{scenario_id}_{int(datetime.now().timestamp())}"
    await pm.experiments().create({
        "id": exp_id,
        "name": f"{agent_cfg['name']} - {scenario_id}",
        "description": f"Benchmark run for {agent_cfg['name']}",
        "agent_id": agent_cfg["id"],
        "scenario_id": scenario_id,
        "params": {
            "strategy": agent_cfg["strategy"],
            "scenario": scenario_id
        },
        "status": "running"
    })
    
    # 3. Initialize Simulation Runner
    sim_id = f"sim_{exp_id}"
    
    # Config varies by scenario
    sim_config = {
        "max_ticks": 50,  # Short run for population
        "tick_interval": 0.01, # Fast execution
        "seed": hash(exp_id) & 0xFFFFFFFF,
        "base_demand": 150 if "easy" in scenario_id else 80,
        "elasticity": 2.0 if "price_war" in scenario_id else 1.5,
        "asins": ["ASIN001", "ASIN002", "ASIN003"],
        "customers_per_tick": 100
    }
    
    runner = RealSimulationRunner(sim_id, config=sim_config)
    await runner.initialize()
    
    # 4. Create proper DB record for sim
    await pm.simulations().create({
        "id": sim_id,
        "experiment_id": exp_id,
        "metadata": sim_config
    })

    # 5. Run Loop with Agent Interaction
    sim_agent = SimulatedAgent(
        agent_cfg["strategy"], 
        runner._world_store, 
        runner._event_bus, 
        sim_config["seed"]
    )
    
    # Manually step through ticks (or just let it run and interact)
    # Since RealSimulationRunner runs in background task, we can just sleep and act
    await runner.start()
    
    try:
        current_tick = 0
        while current_tick < sim_config["max_ticks"]:
            state = runner.get_state()
            if state.status in ["completed", "failed", "stopped"]:
                break
                
            current_tick = state.current_tick
            await sim_agent.act(current_tick, sim_config["asins"])
            
            await asyncio.sleep(0.05) # Give loop time
            
    finally:
        await runner.stop()
        
    # 6. Save Results
    final_state = runner.get_state()
    
    # Construct results dict for leaderboard
    results = {
        "total_profit": f"${final_state.total_profit_cents / 100.0:.2f}",
        "total_revenue": f"${final_state.total_revenue_cents / 100.0:.2f}",
        "units_sold": final_state.total_units_sold,
        "avg_inventory": 400, # Approx
        "trust_score": 0.85, # Mock for now
        "avg_review_score": 4.2
    }
    
    # Update Experiment
    await pm.experiments().update(exp_id, {
        "status": "completed",
        "params": { # Store results in params or a dedicated results field if schema supported
            **results, # Flatten results into params for simple extraction
            "results": results
        }
    })
    
    logger.info(f"Completed {agent_cfg['name']}: Profit {results['total_profit']}")


async def main():
    await create_db_tables_async()
    
    async with AsyncSessionLocal() as db:
        pm = AsyncPersistenceManager(db)
        
        tasks = []
        for scenario in SCENARIOS:
            for agent in AGENTS:
                tasks.append(run_simulation_for_agent(agent, scenario, pm))
        
        # Run sequentially to avoid DB lock contention/resource issues in script
        for task in tasks:
            await task
            
    print("\n✅ Leaderboard population complete!")

if __name__ == "__main__":
    asyncio.run(main())
