import argparse
import asyncio
import logging
import os
import sys

# Ensure project root is on sys.path so 'infrastructure' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.openrouter_client import OpenRouterClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_openrouter")

async def main(model: str, prompt: str, temperature: float = 0.7):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: OPENROUTER_API_KEY is required.")

    async with OpenRouterClient(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        timeout_seconds=float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "60")),
        max_retries=3,
        initial_backoff_ms=1000,
    ) as client:
        result = await client.chat_completions(
            model=model,
            prompt=prompt,
            max_tokens=None,
            temperature=temperature,
        )

    # Pretty print results
    content = result.get("content", "")
    usage = result.get("usage", {})
    cost = result.get("cost", 0.0)
    print("==== OpenRouter ChatCompletion ====")
    print(f"Model: {model}")
    print(f"Content:\n{content}\n")
    print(f"Usage: {usage}")
    print(f"Estimated Cost (USD): {cost:.6f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenRouter connectivity test")
    parser.add_argument("--model", required=True, help="Model slug, e.g. x-ai/grok-4-fast:free")
    parser.add_argument("--prompt", default="Return the word OK only.", help="Prompt to send")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    args = parser.parse_args()
    asyncio.run(main(args.model, args.prompt, args.temperature))
