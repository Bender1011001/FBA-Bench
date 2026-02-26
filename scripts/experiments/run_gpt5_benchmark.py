#!/usr/bin/env python3
"""
This script performs a simple smoke test of the GPT-5 API endpoint to verify connectivity and authentication.
Minimal GPT-5 live smoke test without loading the full benchmarking engine.

Why: Importing benchmarking.core.engine triggers broader package imports that currently
raise a NameError in benchmarking.scenarios.base. This script directly calls the
OpenAI-compatible endpoint using the project's GenericOpenAIClient to validate GPT-5 access.

Usage:
  1) Set your OpenAI key:
     - PowerShell: $Env:OPENAI_API_KEY="sk-..."
     - cmd.exe:    setx OPENAI_API_KEY "sk-..."
     - bash/zsh:   export OPENAI_API_KEY="sk-..."
  2) Optionally set a custom base URL (defaults to OpenAI public endpoint):
     - OPENAI_BASE_URL="https://api.openai.com/v1"
  3) Run:
     python run_gpt5_benchmark.py

Exit codes:
  0 = Success and exact expected reply received
  1 = API reached, but reply differs from expected (still proves connectivity)
  2 = Configuration error (e.g., missing OPENAI_API_KEY) or API/network failure
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

from instrumentation.clearml_tracking import ClearMLTracker
from llm_interface.generic_openai_client import GenericOpenAIClient


async def gpt5_smoke_test() -> Dict[str, Any]:
    prompt = "Please reply exactly with: GPT-5 test successful."
    expected = "GPT-5 test successful."

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = GenericOpenAIClient(model_name="gpt-5", api_key=api_key, base_url=base_url)

    resp = await client.generate_response(prompt=prompt, max_tokens=64)

    # Extract content if available
    content = None
    try:
        choices = resp.get("choices") or []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                content = content.strip()
    except Exception:
        content = None

    return {
        "model": "gpt-5",
        "prompt": prompt,
        "expected": expected,
        "content": content,
        "raw_response": resp,
    }


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    tracker = None
    try:
        # Initialize ClearML task (safe no-op if ClearML SDK not installed/configured)
        tracker = ClearMLTracker(
            project_name="FBA-Bench", task_name="GPT5_SmokeTest", tags=["smoke", "gpt5"]
        )
        # Connect non-sensitive run configuration
        tracker.connect(
            {
                "model": "gpt-5",
                "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "environment": "local",
            }
        )

        result = await gpt5_smoke_test()
        print("=== GPT-5 Smoke Test Result ===")
        print(json.dumps(result, indent=2, default=str))

        # Log outcome to ClearML
        success = bool(result.get("content") == result.get("expected"))
        tracker.log_scalar(
            "GPT5Connectivity", "status", 1.0 if result.get("raw_response") else 0.0, iteration=0
        )
        tracker.log_scalar("GPT5ContentMatch", "status", 1.0 if success else 0.0, iteration=0)
        tracker.log_parameters(result, name="gpt5_smoke_result")
        try:
            tracker.upload_artifact(
                "gpt5_smoke_raw_response", artifact_object=result.get("raw_response")
            )
        except Exception:
            pass

        if success:
            print("Result: success")
            return 0
        else:
            print("Result: completed (content mismatch). Connectivity verified.")
            return 1

    except Exception as e:
        print("=== GPT-5 Smoke Test Error ===")
        print(str(e))
        return 2
    finally:
        try:
            if tracker is not None:
                tracker.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
