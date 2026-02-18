import requests
import json
import uuid

API_URL = "http://localhost:8000/api/v1/benchmarks/log"

def test_logging():
    payload = {
        "run_id": str(uuid.uuid4()),
        "agent_id": "test-agent-001",
        "scenario_id": "tier_1_basic",
        "metrics": {
            "profit": 1500.50,
            "efficiency": 0.85,
            "sales": 120,
            "customer_satisfaction": 0.92
        },
        "params": {
            "model": "test-model-v1",
            "temperature": 0.7
        }
    }

    try:
        print(f"Sending payload to {API_URL}...")
        response = requests.post(API_URL, json=payload)
        
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response Body: {response.text}")
        except:
            print("Response Body: <non-printable>")

        if response.status_code == 201:
            print("SUCCESS: Benchmark result logged.")
        else:
            print("FAILURE: Could not log result.")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_logging()
