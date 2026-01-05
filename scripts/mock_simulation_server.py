import asyncio
import json
import random
import logging
from typing import List, Dict
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Data models for mock state
class MockAgent:
    def __init__(self, agent_id: str, role: str):
        self.id = agent_id
        self.role = role
        self.x = 400.0  # Center of 800x600 view
        self.y = 300.0
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.state = "Idle"
        self.cash = 10000.0
        self.inventory_val = 5000.0
        self.profit = 0.0
        self.thoughts = [
            "Analyzing market trends...",
            "Competitor detected near aisle 4.",
            "Restocking widgets to optimize inventory levels.",
            "Calculating margin impact of recent price drop.",
            "Waiting for demand signal."
        ]
        self.events = []

    def update(self):
        # Move
        self.x += self.vx
        self.y += self.vy
        
        # Bounce off walls (800x600)
        if self.x < 20 or self.x > 780: self.vx *= -1
        if self.y < 20 or self.y > 580: self.vy *= -1
        
        # Random state change
        if random.random() < 0.05:
            self.state = random.choice(["Active", "Idle", "Buying", "Selling", "Waiting"])
            # Update thought
            new_thought = random.choice(self.thoughts)
            self.current_thought = new_thought
            self.events.insert(0, f"T+{int(asyncio.get_event_loop().time())}: {self.state} - {new_thought[:20]}...")
            if len(self.events) > 5: self.events.pop()
            
            # Update financials
            change = random.uniform(-100, 150)
            self.profit += change
            self.cash += change

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "role": self.role,
            "x": self.x,
            "y": self.y,
            "state": self.state,
            "last_reasoning": getattr(self, "current_thought", "Initializing..."),
            "financials": {
                "cash": self.cash,
                "inventory_value": self.inventory_val,
                "net_profit": self.profit
            },
            "recent_events": self.events
        }

# Global State
agents = [
    MockAgent("Agent-GPT4", "Strategic Planner"),
    MockAgent("Agent-Claude", "Analyst"),
    MockAgent("Agent-Gemini", "Logistics Manager")
]
tick_count = 0

@app.websocket("/ws/simulation/{sim_id}")
async def websocket_endpoint(websocket: WebSocket, sim_id: str):
    global tick_count
    await websocket.accept()
    logger.info(f"Client connected to simulation {sim_id}")
    
    try:
        while True:
            # Check for incoming messages (e.g., 'step' or 'pause')
            # For this mock, we'll auto-step every 100ms
            # data = await websocket.receive_text() # Un-comment to wait for manual steps
            
            # Update Simulation
            tick_count += 1
            tick_metrics = {
                "total_revenue": 100000 + (tick_count * 50),
                "inventory_count": 5000 - (tick_count % 100),
                "pending_orders": random.randint(0, 50)
            }
            
            agent_data = []
            for agent in agents:
                agent.update()
                agent_data.append(agent.to_dict())
            
            # Construct Payload
            payload = {
                "type": "tick",
                "tick": tick_count,
                "metrics": tick_metrics,
                "agents": agent_data,
                "heatmap": [], # Placeholder
                "world": {} # Placeholder
            }
            
            await websocket.send_json(payload)
            await asyncio.sleep(0.1) # 10 ticks per second
            
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
