#!/usr/bin/env python3
"""
OpenRouter Free Models Benchmark Runner

This script runs benchmark tests with OpenRouter's free models to evaluate their performance
across various business scenarios while the free tier is available.

Free Models Tested:
- deepseek/deepseek-chat-v3.1:free
- x-ai/grok-4-fast:free
- deepseek/deepseek-r1-0528:free
- deepseek/deepseek-chat-v3-0324:free
- tngtech/deepseek-r1t2-chimera:free

Usage:
  1) Set your OpenRouter API key:
     - PowerShell: $Env:OPENROUTER_API_KEY="sk-or-..."
     - cmd.exe:    setx OPENROUTER_API_KEY "sk-or-..."
     - bash/zsh:   export OPENROUTER_API_KEY="sk-or-..."
  2) Run all models:
     python run_openrouter_benchmark.py
  3) Run specific model:
     python run_openrouter_benchmark.py --model "deepseek/deepseek-chat-v3.1:free"
  4) Run with custom scenario:
     python run_openrouter_benchmark.py --scenario configs/clearml_smoketest.yaml
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# from instrumentation.clearml_tracking import ClearMLTracker  # Disabled for standalone run

from llm_interface.generic_openai_client import GenericOpenAIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OpenRouter configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Top-tier paid models (December 2025 rankings)
OPENROUTER_TOP_MODELS = [
    "openai/gpt-5.2",                    # GPT-5.2 - Top reasoning & speed
    "anthropic/claude-opus-4.5",         # Claude Opus 4.5 - Best coding
    "google/gemini-3-pro-preview",       # Gemini 3 Pro - Best multimodal
    "deepseek/deepseek-v3.2",            # DeepSeek V3.2 - Best value
    "x-ai/grok-4.1-fast",                # Grok 4.1 Fast - Fast reasoning
]

# Mid-tier models (expected to do moderately well)
OPENROUTER_MID_MODELS = [
    "meta-llama/llama-3.3-70b-instruct", # Llama 3.3 70B
    "mistralai/mistral-large-latest",    # Mistral Large
    "google/gemini-2.0-flash-exp:free",  # Gemini 2.0 Flash (free)
    "anthropic/claude-3.5-sonnet",       # Claude 3.5 Sonnet (older)
]

# Weak/Small models (EXPECTED TO LOSE MONEY - this is the validation test!)
OPENROUTER_WEAK_MODELS = [
    "mistralai/mistral-7b-instruct:free",     # Mistral 7B - Small model
    "meta-llama/llama-3.2-3b-instruct:free",  # Llama 3.2 3B - Tiny model
    "google/gemma-2-9b-it:free",              # Gemma 2 9B - Small Google model
    "microsoft/phi-3-mini-128k-instruct:free",# Phi-3 Mini - Micro model
    "qwen/qwen-2-7b-instruct:free",           # Qwen 2 7B - Small Alibaba model
    "nvidia/nemotron-nano-12b-2:free",        # Nemotron Nano 12B
]

# Free tier models available on OpenRouter (mixed quality)
OPENROUTER_FREE_MODELS = [
    "deepseek/deepseek-r1-0528:free",    # DeepSeek R1 Free (good)
    "tngtech/deepseek-r1t2-chimera:free",# DeepSeek R1T2 Chimera (good)
    "allenai/olmo-3-32b-think:free",     # OLMo 3 32B Think (medium)
    "arcee-ai/trinity-mini:free",        # Arcee Trinity Mini (small)
    "xiaomi/mimo-v2-flash:free",         # MiMo V2 Flash (small)
]

# Standard test prompts for benchmarking
TEST_PROMPTS = [
    {
        "name": "business_reasoning",
        "prompt": """You are a business analyst. Analyze this scenario:
        
Company A sells widgets for $10 each with a cost of $6 per unit. They currently sell 1000 units per month.
A competitor is offering similar widgets for $9. 

What pricing strategy would you recommend and why? Consider:
1. Profit margins
2. Market share impact  
3. Long-term sustainability
4. Competitive positioning

Provide a structured analysis with specific recommendations.""",
        "expected_elements": ["profit", "margin", "competition", "strategy", "recommendation"],
    },
    {
        "name": "problem_solving",
        "prompt": """Solve this logistics problem step by step:

A warehouse has 3 loading docks and needs to schedule deliveries for 8 trucks today.
- Dock A can handle trucks weighing up to 10 tons
- Dock B can handle trucks weighing up to 15 tons  
- Dock C can handle trucks weighing up to 20 tons

The trucks are: 8t, 12t, 9t, 18t, 7t, 14t, 16t, 11t

Each truck takes 2 hours to load. The warehouse operates 8 hours today.
Can all trucks be scheduled? If so, provide an optimal schedule. If not, explain why.""",
        "expected_elements": ["schedule", "dock", "time", "capacity", "optimization"],
    },
    {
        "name": "creative_strategy",
        "prompt": """Design a marketing campaign for a new eco-friendly product line.

Product: Biodegradable phone cases made from plant materials
Target: Environmentally conscious millennials and Gen Z
Budget: $50,000 for 3 months
Goal: 20% brand awareness increase

Create a comprehensive strategy including:
1. Key messaging
2. Channel selection
3. Budget allocation
4. Success metrics
5. Timeline

Be specific and actionable.""",
        "expected_elements": ["messaging", "channels", "budget", "metrics", "timeline"],
    },
]


class OpenRouterBenchmarkRunner:
    """Manages OpenRouter model benchmarking with comprehensive testing and tracking."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.cost_tracker = None
        self.results: List[Dict[str, Any]] = []
        self.tracker = None

    async def initialize_tracking(self) -> None:
        """Skip ClearML tracking for standalone benchmark run."""
        logger.info("Skipping ClearML tracking (not configured)")
        self.tracker = None

    async def test_model(self, model_name: str) -> Dict[str, Any]:
        """Test a single OpenRouter model with comprehensive evaluation."""
        logger.info(f"Testing model: {model_name}")

        model_results = {
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "prompts": [],
            "summary": {
                "total_prompts": 0,
                "successful_responses": 0,
                "average_response_time": 0.0,
                "total_tokens": 0,
                "errors": [],
            },
        }

        try:
            # Initialize client for this model
            client = GenericOpenAIClient(
                model_name=model_name,
                api_key=self.api_key,
                base_url=OPENROUTER_BASE_URL,
                cost_tracker=self.cost_tracker,
            )

            total_time = 0.0
            total_tokens = 0

            # Test each prompt
            for prompt_data in TEST_PROMPTS:
                prompt_result = await self._test_single_prompt(client, prompt_data)
                model_results["prompts"].append(prompt_result)

                if prompt_result["success"]:
                    model_results["summary"]["successful_responses"] += 1
                    total_time += prompt_result["response_time"]
                    total_tokens += prompt_result.get("token_count", 0)
                else:
                    model_results["summary"]["errors"].append(prompt_result["error"])

            # Calculate summary metrics
            model_results["summary"]["total_prompts"] = len(TEST_PROMPTS)
            if model_results["summary"]["successful_responses"] > 0:
                model_results["summary"]["average_response_time"] = (
                    total_time / model_results["summary"]["successful_responses"]
                )
            model_results["summary"]["total_tokens"] = total_tokens
            model_results["summary"]["success_rate"] = model_results["summary"][
                "successful_responses"
            ] / len(TEST_PROMPTS)

            logger.info(
                f"Model {model_name} completed: "
                f"{model_results['summary']['successful_responses']}/{len(TEST_PROMPTS)} successful"
            )

        except Exception as e:
            error_msg = f"Failed to test model {model_name}: {e}"
            logger.error(error_msg)
            model_results["summary"]["errors"].append(error_msg)

        return model_results

    async def _test_single_prompt(
        self, client: GenericOpenAIClient, prompt_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test a single prompt with the given client."""
        prompt_result = {
            "prompt_name": prompt_data["name"],
            "success": False,
            "response_time": 0.0,
            "token_count": 0,
            "response_content": None,
            "error": None,
            "quality_score": 0.0,
        }

        try:
            start_time = asyncio.get_event_loop().time()

            # Make the API call
            logger.info(f"    Running prompt: {prompt_data['name']}...")
            response = await client.generate_response(
                prompt=prompt_data["prompt"], temperature=0.7, max_tokens=2048
            )

            end_time = asyncio.get_event_loop().time()
            prompt_result["response_time"] = end_time - start_time
            logger.info(f"    ✓ {prompt_data['name']} completed in {prompt_result['response_time']:.1f}s")

            # Extract response content
            if response.get("choices") and len(response["choices"]) > 0:
                content = response["choices"][0].get("message", {}).get("content", "")
                prompt_result["response_content"] = content
                prompt_result["success"] = True

                # Calculate token usage
                usage = response.get("usage", {})
                prompt_result["token_count"] = usage.get("total_tokens", 0) or usage.get(
                    "prompt_tokens", 0
                ) + usage.get("completion_tokens", 0)

                # Basic quality assessment
                prompt_result["quality_score"] = self._assess_response_quality(
                    content, prompt_data.get("expected_elements", [])
                )

        except Exception as e:
            prompt_result["error"] = str(e)
            logger.error(f"Prompt '{prompt_data['name']}' failed: {e}")

        return prompt_result

    def _assess_response_quality(self, content: str, expected_elements: List[str]) -> float:
        """Basic quality assessment based on expected elements presence."""
        if not content or not expected_elements:
            return 0.0

        content_lower = content.lower()
        found_elements = sum(1 for element in expected_elements if element.lower() in content_lower)

        # Quality score based on coverage + length appropriateness
        coverage_score = found_elements / len(expected_elements)
        length_score = min(1.0, len(content.split()) / 100.0)  # Favor detailed responses

        return (coverage_score * 0.7) + (length_score * 0.3)


    async def run_benchmark(self, models: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run benchmark across specified models or all free models."""
        test_models = models or OPENROUTER_FREE_MODELS

        logger.info(f"Starting OpenRouter benchmark for {len(test_models)} models")

        # Initialize tracking
        await self.initialize_tracking()

        benchmark_start = asyncio.get_event_loop().time()

        # Test each model
        for model_name in test_models:
            try:
                model_result = await self.test_model(model_name)
                self.results.append(model_result)
            except Exception as e:
                logger.error(f"Critical error testing {model_name}: {e}")
                # Add failed model result
                self.results.append(
                    {
                        "model": model_name,
                        "timestamp": datetime.now().isoformat(),
                        "prompts": [],
                        "summary": {
                            "total_prompts": 0,
                            "successful_responses": 0,
                            "success_rate": 0.0,
                            "errors": [f"Critical failure: {e}"],
                        },
                    }
                )

        benchmark_end = asyncio.get_event_loop().time()

        # Compile final results
        final_results = {
            "benchmark_info": {
                "timestamp": datetime.now().isoformat(),
                "total_duration": benchmark_end - benchmark_start,
                "models_tested": len(test_models),
                "openrouter_endpoint": OPENROUTER_BASE_URL,
            },
            "model_results": self.results,
            "summary": self._generate_summary(),
        }

        return final_results

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall benchmark summary."""
        if not self.results:
            return {"error": "No results to summarize"}

        total_tests = sum(r["summary"]["total_prompts"] for r in self.results)
        total_successes = sum(r["summary"]["successful_responses"] for r in self.results)

        working_models = [r for r in self.results if r["summary"]["successful_responses"] > 0]

        summary = {
            "total_models_tested": len(self.results),
            "working_models": len(working_models),
            "total_api_calls": total_tests,
            "successful_calls": total_successes,
            "overall_success_rate": total_successes / total_tests if total_tests > 0 else 0.0,
            "best_performing_model": None,
            "model_rankings": [],
        }

        if working_models:
            # Rank models by success rate, then by average quality
            def model_score(result):
                success_rate = result["summary"]["success_rate"]
                avg_quality = 0.0
                if result["prompts"]:
                    avg_quality = sum(p.get("quality_score", 0) for p in result["prompts"]) / len(
                        result["prompts"]
                    )
                return (success_rate * 0.7) + (avg_quality * 0.3)

            ranked_models = sorted(working_models, key=model_score, reverse=True)
            summary["best_performing_model"] = ranked_models[0]["model"]
            summary["model_rankings"] = [
                {
                    "model": r["model"],
                    "success_rate": r["summary"]["success_rate"],
                    "avg_response_time": r["summary"]["average_response_time"],
                    "total_tokens": r["summary"]["total_tokens"],
                }
                for r in ranked_models
            ]

        return summary

    async def cleanup(self) -> None:
        """Clean up resources."""
        pass


async def main() -> int:
    """Main function to run the OpenRouter benchmark."""
    parser = argparse.ArgumentParser(description="Run OpenRouter models benchmark")
    parser.add_argument(
        "--model",
        type=str,
        help="Test specific model by slug",
    )
    parser.add_argument(
        "--top",
        action="store_true",
        help="Test top-tier paid models (GPT-5.2, Claude Opus 4.5, Gemini 3 Pro, DeepSeek V3.2, Grok 4.1 Fast)",
    )
    parser.add_argument(
        "--free",
        action="store_true",
        help="Test free tier models only (default if no flag specified)",
    )
    parser.add_argument(
        "--weak",
        action="store_true",
        help="Test weak/small models (expected to lose money - validation test)",
    )
    parser.add_argument(
        "--mid",
        action="store_true",
        help="Test mid-tier models",
    )
    parser.add_argument(
        "--wide",
        action="store_true",
        help="Test WIDE range: top + mid + weak + free (full benchmark validation)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all models (top + free)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="openrouter_benchmark_results.json",
        help="Output file for results",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--scenario", type=str, default="configs/tier_2_advanced.yaml", help="Path to the scenario YAML file.")

    args = parser.parse_args()
    scenario_path = args.scenario

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY environment variable is required")
        logger.error("Get your key from: https://openrouter.ai/keys")
        return 2

    try:
        # Determine models to test
        if args.model:
            models_to_test = [args.model]
            logger.info(f"Testing single model: {args.model}")
        elif args.top:
            models_to_test = OPENROUTER_TOP_MODELS
            logger.info(f"Testing {len(models_to_test)} top-tier paid models")
        elif args.weak:
            models_to_test = OPENROUTER_WEAK_MODELS
            logger.info(f"Testing {len(models_to_test)} WEAK/SMALL models (expected to lose money)")
        elif args.mid:
            models_to_test = OPENROUTER_MID_MODELS
            logger.info(f"Testing {len(models_to_test)} mid-tier models")
        elif getattr(args, 'wide', False):
            models_to_test = OPENROUTER_TOP_MODELS + OPENROUTER_MID_MODELS + OPENROUTER_WEAK_MODELS + OPENROUTER_FREE_MODELS
            logger.info(f"Testing WIDE range: {len(models_to_test)} models across all tiers")
        elif getattr(args, 'all', False):
            models_to_test = OPENROUTER_TOP_MODELS + OPENROUTER_FREE_MODELS
            logger.info(f"Testing all {len(models_to_test)} models (top + free)")
        else:
            # Default to free models
            models_to_test = OPENROUTER_FREE_MODELS
            logger.info(f"Testing {len(models_to_test)} free tier models")


        # Run benchmark
        runner = OpenRouterBenchmarkRunner(api_key)
        results = await runner.run_benchmark(models_to_test)

        # Save results
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)

        # Print summary
        logger.info("=== OpenRouter Benchmark Complete ===")
        summary = results["summary"]
        logger.info(f"Models tested: {summary['total_models_tested']}")
        logger.info(f"Working models: {summary['working_models']}")
        logger.info(f"Overall success rate: {summary['overall_success_rate']:.2%}")

        if summary.get("best_performing_model"):
            logger.info(f"Best performing: {summary['best_performing_model']}")

        logger.info(f"Detailed results saved to: {args.output}")

        # Clean up
        await runner.cleanup()

        return 0 if summary["working_models"] > 0 else 1

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        logger.exception("Benchmark execution error")
        return 2


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
        raise SystemExit(130)
