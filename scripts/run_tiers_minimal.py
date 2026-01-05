import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure repository root on sys.path for importing infrastructure client
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.openrouter_client import OpenRouterClient  # noqa: E402

MODELS = [
    "x-ai/grok-4-fast:free",
    "deepseek/deepseek-chat-v3.1:free",
    "deepseek/deepseek-r1-0528:free",
    "qwen/qwen3-coder:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "openai/gpt-oss-20b:free",
    "moonshotai/kimi-k2:free",
    "cognitivecomputations/dolphin3.0-mistral-24b:free",
    "openai/gpt-oss-120b:free",
]

TIERS = ["T0", "T1", "T2"]


def sanitize_slug(slug: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", ".", "_") else "_" for ch in slug)


async def run_single(client: OpenRouterClient, model: str, tier: str) -> dict:
    """
    Execute a minimal tier check against a model via OpenRouter.
    The prompt requests an exact token to make verification trivial.
    """
    prompt = f"Tier {tier} quick check: Return exactly OK_{tier} and nothing else."
    try:
        # Some providers require a minimum completion token count; use 32 to be safe
        result = await client.chat_completions(
            model=model,
            prompt=prompt,
            max_tokens=32,
            temperature=0.0,
        )
        content = result.get("content", "")
        usage = result.get("usage", {})
        cost = result.get("cost", 0.0)
        status = "ok" if content.strip().startswith(f"OK_{tier}") else "mismatch"
        return {
            "status": status,
            "model": model,
            "tier": tier,
            "prompt": prompt,
            "content": content,
            "usage": usage,
            "cost": cost,
        }
    except Exception as e:
        return {
            "status": "error",
            "model": model,
            "tier": tier,
            "error": str(e),
        }


async def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is required in environment.", file=sys.stderr)
        sys.exit(1)

    out_root = ROOT / "artifacts" / "tier_runs_minimal" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root.mkdir(parents=True, exist_ok=True)

    # Configure optional headers via env (OpenRouter recommends Referer and Title)
    os.environ.setdefault("OPENROUTER_TITLE", "FBA-Bench")
    os.environ.setdefault("OPENROUTER_REFERER", "https://github.com/")

    summary = {"runs": []}

    async with OpenRouterClient(
        api_key=api_key,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "90")),
        max_retries=3,
        initial_backoff_ms=1000,
    ) as client:
        for model in MODELS:
            for tier in TIERS:
                res = await run_single(client, model, tier)
                summary["runs"].append(res)

                # Persist per-run result
                fname = f"{sanitize_slug(model)}__{tier}.json"
                with open(out_root / fname, "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False, indent=2)

                # Console feedback
                if res["status"] == "ok":
                    print(f"[OK] {tier} {model}: matched")
                elif res["status"] == "mismatch":
                    got = (res.get("content") or "").strip().replace("\n", " ")[:80]
                    print(f"[MISMATCH] {tier} {model}: got '{got}'")
                else:
                    print(f"[ERROR] {tier} {model}: {res.get('error')}")

    # Write aggregate summary
    with open(out_root / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Final brief summary counts
    ok = sum(1 for r in summary["runs"] if r["status"] == "ok")
    mismatch = sum(1 for r in summary["runs"] if r["status"] == "mismatch")
    errs = sum(1 for r in summary["runs"] if r["status"] == "error")
    total = len(summary["runs"])
    print(f"\nCompleted minimal tier runs: {ok} ok, {mismatch} mismatch, {errs} error, out of {total}.")
    print(f"Artifacts: {out_root}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Aborted by user", file=sys.stderr)
        sys.exit(130)
