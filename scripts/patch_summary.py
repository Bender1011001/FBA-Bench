
import json
import shutil
from pathlib import Path

def patch_summary():
    # Paths
    backup_path = Path("results/openrouter_tier_runs/t2/summary.json.bak")
    target_path = Path("results/openrouter_tier_runs/t2/summary.json")
    
    # New Run ID from live.json or hardcoded (I know it)
    new_run_id = "run-20260211-v2-consolidated"
    
    if not backup_path.exists():
        print(f"Error: {backup_path} does not exist.")
        return

    # Read backup
    print(f"Reading backup from {backup_path}...")
    with open(backup_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    patched_data = []
    
    # Process records
    for record in data:
        # Keep successful records, update their run_id
        if record.get("success", False):
            record["run_id"] = new_run_id
            patched_data.append(record)
        # Skip failed GPT-5.2 (it will be provided by live.json progress)
        elif record.get("model_slug") == "openai/gpt-5.2" and not record.get("success"):
            print("Skipping old failed GPT-5.2 record.")
            continue
        else:
            # Keep other failed records (e.g. DeepSeek-R1) but update run_id so they show up
            record["run_id"] = new_run_id
            patched_data.append(record)
            
    # Write back to target
    print(f"Writing patched data to {target_path}...")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(patched_data, f, indent=2)
        
    print("Patch complete.")

if __name__ == "__main__":
    patch_summary()
