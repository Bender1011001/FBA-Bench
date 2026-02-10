"""
Token Counter - Utility for counting tokens in text.

This module provides utilities for counting tokens in text, which is
essential for managing LLM API costs, context window limits, and
rate limiting.
"""

import functools
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Attempt to import tiktoken, make it an optional feature
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


@functools.total_ordering
@dataclass
class TokenCountResult:
    """
    Result of token counting operation.

    Attributes:
        count: Number of tokens counted
        model: Model used for counting (if applicable)
        method: Method used for counting
        text_sample: Sample of text that was counted (truncated if too long)
        estimated: Whether the count is estimated or exact
    """

    count: int
    model: Optional[str] = None
    method: str = "unknown"
    text_sample: str = ""
    estimated: bool = False

    # compat: numeric semantics so callers comparing/adding to ints continue to work
    def __int__(self) -> int:
        return int(self.count)

    def __eq__(self, other) -> bool:  # type: ignore[override]
        # Allow direct comparison to ints
        if isinstance(other, int):
            return self.count == other
        # Preserve dataclass-like equality for same-type comparisons
        if isinstance(other, TokenCountResult):
            return (
                self.count == other.count
                and self.model == other.model
                and self.method == other.method
                and self.text_sample == other.text_sample
                and self.estimated == other.estimated
            )
        return NotImplemented

    def __lt__(self, other) -> bool:
        # Ordering comparisons compare by count
        if isinstance(other, int):
            return self.count < other
        if isinstance(other, TokenCountResult):
            return self.count < other.count
        return NotImplemented  # type: ignore[return-value]

    def __add__(self, other):
        # Support arithmetic with ints and other results, returning an int
        if isinstance(other, int):
            return self.count + other
        if isinstance(other, TokenCountResult):
            return self.count + other.count
        return NotImplemented

    def __radd__(self, other):
        # Enable sum([TokenCountResult, ...]) where sum starts with 0
        if isinstance(other, int):
            return other + self.count
        if isinstance(other, TokenCountResult):
            return other.count + self.count
        return NotImplemented

    def __str__(self) -> str:
        return f"TokenCountResult(count={self.count}, method={self.method}, estimated={self.estimated})"

    def __repr__(self) -> str:
        return (
            f"TokenCountResult(count={self.count!r}, model={self.model!r}, "
            f"method={self.method!r}, text_sample={self.text_sample!r}, estimated={self.estimated!r})"
        )


# Known model/encoding aliases to improve tiktoken model-awareness.
# This allows us to map newer model names to stable encodings even when
# tiktoken.encoding_for_model doesn't recognize the exact string.
_MODEL_ENCODING_ALIASES = {
    # OpenAI modern families that use o200k_base
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4o-realtime": "o200k_base",
    "gpt-4o-audio": "o200k_base",
    "gpt-4o-mini-transcribe": "o200k_base",
    "gpt-4o-mini-translate": "o200k_base",
    "gpt-4.1": "o200k_base",
    "gpt-4.1-mini": "o200k_base",
    "o3": "o200k_base",
    "o4": "o200k_base",
    # Classic GPT families that use cl100k_base
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-3.5": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "text-davinci-003": "p50k_base",
    # Non-OpenAI families mapped to a safe fallback encoding where exact tokenizer isn't available
    "claude-3": "cl100k_base",
    "claude": "cl100k_base",
    "gemini": "cl100k_base",
    "mistral": "cl100k_base",
    "llama": "cl100k_base",
    # Additional popular variants (best-effort)
    "llama-3": "cl100k_base",
    "mixtral": "cl100k_base",
    "sonnet": "cl100k_base",
    "opus": "cl100k_base",
}


def _resolve_tiktoken_encoding_name(model: str, provider: Optional[str] = None) -> Optional[str]:
    """
    Resolve a best-effort tiktoken encoding name for a given model string.
    Uses substring matching against _MODEL_ENCODING_ALIASES keys and optional provider hint.
    """
    if not model and not provider:
        return None
    m = (model or "").lower()
    p = (provider or "").lower()

    # Provider-level hints (best-effort, safe fallbacks)
    # We prefer OpenAI-accurate mappings when possible; for other providers we use cl100k_base as a robust default.
    if p:
        if "openai" in p:
            # Let model hints decide (o200k_base for modern 4o/4.1 families else cl100k_base)
            pass
        elif (
            "anthropic" in p
            or "claude" in p
            or "google" in p
            or "gemini" in p
            or "mistral" in p
            or "meta" in p
            or "llama" in p
        ):
            return "cl100k_base"

    # Model-level hints via substring
    for hint, enc in _MODEL_ENCODING_ALIASES.items():
        if hint in m:
            return enc
    return None


class TokenCounter:
    """
    Utility class for counting tokens in text.

    This class provides methods to count tokens using various strategies,
    including exact counting with tiktoken (when available) and fallback
    estimation methods.
    """

    def __init__(self, default_model: str = "gpt-3.5-turbo"):
        """
        Initialize the token counter.

        Args:
            default_model: Default model to use for token counting
        """
        self.default_model = default_model
        self.encoding_cache: Dict[str, Any] = {}

        # Initialize tiktoken encoding if available. Do NOT mutate the module-level
        # TIKTOKEN_AVAILABLE flag here (avoids UnboundLocalError and supports monkeypatch in tests).
        self.encoding = None
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.encoding_for_model(default_model)
                logger.info(f"Initialized tiktoken encoding for model: {default_model}")
            except KeyError:
                logger.warning(
                    f"Unknown model for tiktoken: {default_model}, using cl100k_base as fallback"
                )
                self.encoding = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                # If tiktoken is installed but any error occurs during init, fall back gracefully.
                logger.debug(f"Failed to initialize tiktoken encoding for {default_model}: {e}")
                self.encoding = None

    def calculate_cost(self, tokens: int, usd_per_1k: float) -> float:
        """
        Calculate estimated API cost in USD for a given token count.

        Args:
            tokens: Total tokens (prompt + completion).
            usd_per_1k: Dollar cost per 1,000 tokens.

        Returns:
            Estimated cost in USD as a float (not cents).
        """
        try:
            t = max(0, int(tokens))
            rate = float(usd_per_1k)
        except Exception:
            # Defensive defaults if inputs are malformed
            t = max(0, int(tokens) if isinstance(tokens, int) else 0)
            try:
                rate = float(usd_per_1k)
            except Exception:
                rate = 0.0
        return (t / 1000.0) * rate

    def count_tokens(
        self,
        text: str,
        model: Optional[str] = None,
        method: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> TokenCountResult:
        """
        Count tokens in the given text.

        Args:
            text: Text to count tokens for
            model: Model to use for counting (uses default if not provided)
            method: Method to use for counting ("auto", "tiktoken", "estimate")

        Returns:
            TokenCountResult with count and metadata
        """
        if not text:
            return TokenCountResult(count=0, method="empty", text_sample="")

        model = model or self.default_model

        # Determine method
        if method == "auto" or method is None:
            method = "tiktoken" if TIKTOKEN_AVAILABLE else "estimate"

        # Count tokens based on method
        if method == "tiktoken" and TIKTOKEN_AVAILABLE:
            return self._count_with_tiktoken(text, model, provider=provider)
        else:
            return self._estimate_tokens(text, model)

    def _count_with_tiktoken(
        self, text: str, model: str, provider: Optional[str] = None
    ) -> TokenCountResult:
        """
        Count tokens using tiktoken.

        Args:
            text: Text to count tokens for
            model: Model to use for counting

        Returns:
            TokenCountResult with count and metadata
        """
        try:
            # Get or create encoding for the model (provider-aware)
            encoding = self._get_encoding(model, provider=provider)

            # Count tokens
            tokens = encoding.encode(text)
            count = len(tokens)

            # Create text sample (first 100 chars)
            text_sample = text[:100] + "..." if len(text) > 100 else text

            return TokenCountResult(
                count=count,
                model=model,
                method="tiktoken",
                text_sample=text_sample,
                estimated=False,
            )

        except Exception as e:
            logger.error(f"Error counting tokens with tiktoken: {e}")
            # Fall back to estimation
            return self._estimate_tokens(text, model)
        except KeyError as e:
            logger.debug(f"Unknown model for tiktoken, falling back to estimation: {e}")
            return self._estimate_tokens(text, model)
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid text input or encoding failure, falling back to estimation: {e}")
            return self._estimate_tokens(text, model)
        except Exception as e:
            logger.error(
                f"Unexpected error counting tokens with tiktoken, falling back to estimation: {e}"
            )
            return self._estimate_tokens(text, model)

    def _get_encoding(self, model: str, provider: Optional[str] = None):
        """
        Get or create tiktoken encoding for a model.

        Selection order:
        1) Direct encoding_for_model when supported by tiktoken
        2) Provider/model alias mapping (e.g., gpt-4o → o200k_base; anthropic/claude → cl100k_base)
        3) Final fallback to cl100k_base
        """
        if model in self.encoding_cache:
            return self.encoding_cache[model]

        # Try tiktoken's native resolver first
        try:
            encoding = tiktoken.encoding_for_model(model)
            self.encoding_cache[model] = encoding
            return encoding
        except KeyError:
            pass

        # Try alias-based resolution (provider-aware)
        alias_name = _resolve_tiktoken_encoding_name(model, provider=provider)
        if alias_name:
            try:
                encoding = tiktoken.get_encoding(alias_name)
                self.encoding_cache[model] = encoding
                return encoding
            except KeyError:
                logger.debug(
                    f"Alias encoding '{alias_name}' not recognized by tiktoken; will use cl100k_base."
                )

        # Final fallback
        logger.warning(f"Unknown model for tiktoken: {model}, using cl100k_base as fallback")
        encoding = tiktoken.get_encoding("cl100k_base")
        self.encoding_cache[model] = encoding
        return encoding

    @functools.lru_cache(maxsize=1)
    def _load_ratio_overrides(self, env_var: str = "FBA_TOKEN_RATIOS_FILE") -> Dict[str, float]:
        """
        Load model-specific token ratio overrides from an environment-specified JSON file.

        Args:
            env_var: Environment variable name that points to the JSON file path.

        Returns:
            A dictionary mapping model names (str) to their override ratios (float).
            Returns an empty dictionary if the env var is not set, the file is not found,
            is invalid JSON, or contains invalid entries.
        """
        file_path = os.environ.get(env_var)
        if not file_path:
            logger.debug(
                f"Environment variable {env_var} not set or empty. No ratio overrides loaded."
            )
            return {}

        overrides: Dict[str, float] = {}
        try:
            with open(file_path) as f:
                data = json.load(f)

            if not isinstance(data, dict):
                logger.debug(
                    f"Invalid JSON in {file_path}: expected an object. No ratio overrides loaded."
                )
                return {}

            for key, value in data.items():
                if not isinstance(key, str):
                    logger.debug(
                        f"Skipping invalid entry in {file_path}: key '{key}' is not a string."
                    )
                    continue
                if isinstance(value, int):
                    value = float(value)
                if not isinstance(value, float):
                    logger.debug(
                        f"Skipping invalid entry in {file_path}: value for key '{key}' is not a number (int/float)."
                    )
                    continue
                overrides[key] = value

            if overrides:
                logger.debug(
                    f"Successfully loaded {len(overrides)} ratio overrides from {file_path}."
                )
            else:
                logger.debug(f"No valid ratio overrides found in {file_path}.")

        except FileNotFoundError:
            logger.debug(f"Ratio overrides file not found at {file_path}. No overrides loaded.")
        except json.JSONDecodeError:
            logger.debug(f"Error decoding JSON from {file_path}. No overrides loaded.")
        except PermissionError:
            logger.debug(f"Permission denied when reading {file_path}. No overrides loaded.")
        except ValueError:  # Catches other potential value errors during processing
            logger.debug(f"ValueError processing {file_path}. No overrides loaded.")

        return overrides

    def _estimate_tokens(self, text: str, model: Optional[str]) -> TokenCountResult:
        """
        Estimate tokens using character-based heuristics.
        Ratios can be overridden via the FBA_TOKEN_RATIOS_FILE environment variable.

        Args:
            text: Text to estimate tokens for
            model: Model to use for estimation (affects heuristic)

        Returns:
            TokenCountResult with estimated count and metadata
        """
        # Different models have different token-to-character ratios
        # These are rough estimates based on common patterns
        ratios = {
            # OpenAI families
            "gpt-4o": 0.24,
            "gpt-4.1": 0.24,
            "gpt-4": 0.25,
            "gpt-3.5": 0.25,
            "gpt-3.5-turbo": 0.25,
            "text-davinci-003": 0.25,
            "o3": 0.24,
            "o4": 0.24,
            # Anthropic families
            "claude-3": 0.25,
            "claude": 0.25,
            # Google
            "gemini": 0.25,
            # Mistral / Llama (approx)
            "mistral": 0.25,
            "llama": 0.25,
            # Default
            "default": 0.25,
        }

        # Apply overrides if available
        overrides = self._load_ratio_overrides()
        if overrides:
            ratios = {**ratios, **overrides}  # Overrides take precedence

        # Choose ratio by exact match, then substring hint, else default
        model_key = (model or "").lower()
        ratio = ratios.get(model)
        if ratio is None:
            ratio = next(
                (v for k, v in ratios.items() if k != "default" and k in model_key),
                ratios["default"],
            )

        # Calculate estimated token count
        count = int(len(text) * ratio)

        # Create text sample (first 100 chars)
        text_sample = text[:100] + "..." if len(text) > 100 else text

        return TokenCountResult(
            count=count, model=model, method="estimate", text_sample=text_sample, estimated=True
        )

    def count_messages(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        method: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> TokenCountResult:
        """
        Count tokens in a list of messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use for counting
            method: Method to use for counting

        Returns:
            TokenCountResult with total count and metadata
        """
        if not messages:
            return TokenCountResult(count=0, method="empty", text_sample="")

        model = model or self.default_model

        # Determine method
        if method == "auto" or method is None:
            method = "tiktoken" if TIKTOKEN_AVAILABLE else "estimate"

        # Count tokens based on method
        if method == "tiktoken" and TIKTOKEN_AVAILABLE:
            return self._count_messages_with_tiktoken(messages, model, provider=provider)
        else:
            return self._estimate_message_tokens(messages, model)

    def count_message_tokens(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        method: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> TokenCountResult:
        """
        compat: legacy alias expected by some tests.
        Mirrors count_messages(...) API and semantics exactly.
        """
        return self.count_messages(messages, model=model, method=method, provider=provider)

    def _count_messages_with_tiktoken(
        self, messages: List[Dict[str, str]], model: str, provider: Optional[str] = None
    ) -> TokenCountResult:
        """
        Count tokens in messages using tiktoken.

        Args:
            messages: List of message dictionaries
            model: Model to use for counting

        Returns:
            TokenCountResult with total count and metadata
        """
        # Get encoding for the model
        encoding = self._get_encoding(model, provider=provider)

        # Count tokens per message and add overhead
        # Based on OpenAI's token counting guidance
        # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        total_tokens = 0

        for message in messages:
            # Add message format tokens
            total_tokens += 4  # Each message adds ~4 tokens for format

            # Add content tokens
            content = message.get("content", "")
            if content:
                total_tokens += len(encoding.encode(content))

            # Add role tokens
            role = message.get("role", "")
            if role:
                total_tokens += len(encoding.encode(role))

        # Add final tokens for the assistant's reply
        total_tokens += 2  # Every reply is primed with <|start|>assistant<|message|>

        # Create text sample from first message
        text_sample = ""
        if messages:
            first_content = messages[0].get("content", "")
            text_sample = first_content[:100] + "..." if len(first_content) > 100 else first_content

        return TokenCountResult(
            count=total_tokens,
            model=model,
            method="tiktoken",
            text_sample=text_sample,
            estimated=False,
        )

    def _estimate_message_tokens(
        self, messages: List[Dict[str, str]], model: str
    ) -> TokenCountResult:
        """
        Estimate tokens in messages using character-based heuristics.

        Args:
            messages: List of message dictionaries
            model: Model to use for estimation

        Returns:
            TokenCountResult with estimated count and metadata
        """
        # Different models have different token-to-character ratios
        ratios = {
            # OpenAI families
            "gpt-4o": 0.24,
            "gpt-4.1": 0.24,
            "gpt-4": 0.25,
            "gpt-3.5": 0.25,
            "gpt-3.5-turbo": 0.25,
            "text-davinci-003": 0.25,
            "o3": 0.24,
            "o4": 0.24,
            # Anthropic families
            "claude-3": 0.25,
            "claude": 0.25,
            # Google
            "gemini": 0.25,
            # Mistral / Llama (approx)
            "mistral": 0.25,
            "llama": 0.25,
            # Default
            "default": 0.25,
        }

        # Choose ratio by exact match, then substring hint, else default
        model_key = (model or "").lower()
        ratio = ratios.get(model)
        if ratio is None:
            ratio = next(
                (v for k, v in ratios.items() if k != "default" and k in model_key),
                ratios["default"],
            )

        # Calculate estimated token count
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        estimated_tokens = int(total_chars * ratio)

        # Add overhead for message formatting (rough estimate)
        # Each message adds some overhead for role and formatting
        estimated_tokens += len(messages) * 6  # ~6 tokens per message for format

        # Add final tokens for the assistant's reply
        estimated_tokens += 2  # Every reply is primed with some tokens

        # Create text sample from first message
        text_sample = ""
        if messages:
            first_content = messages[0].get("content", "")
            text_sample = first_content[:100] + "..." if len(first_content) > 100 else first_content

        return TokenCountResult(
            count=estimated_tokens,
            model=model,
            method="estimate",
            text_sample=text_sample,
            estimated=True,
        )

    def count_tokens_by_chunks(
        self,
        text: str,
        chunk_size: int = 1000,
        model: Optional[str] = None,
        method: Optional[str] = None,
    ) -> List[TokenCountResult]:
        """
        Count tokens in text by processing it in chunks.

        Args:
            text: Text to count tokens for
            chunk_size: Size of each chunk in characters
            model: Model to use for counting
            method: Method to use for counting

        Returns:
            List of TokenCountResult objects, one for each chunk
        """
        if not text:
            return []

        model = model or self.default_model

        # Split text into chunks
        chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

        # Count tokens for each chunk
        results = []
        for i, chunk in enumerate(chunks):
            result = self.count_tokens(chunk, model, method)
            result.text_sample = f"Chunk {i+1}: {result.text_sample}"
            results.append(result)

        return results

    def get_token_usage_stats(self, results: List[TokenCountResult]) -> Dict[str, Any]:
        """
        Get statistics from a list of token count results.

        Args:
            results: List of TokenCountResult objects

        Returns:
            Dictionary with usage statistics
        """
        if not results:
            return {
                "total_tokens": 0,
                "average_tokens": 0,
                "min_tokens": 0,
                "max_tokens": 0,
                "estimated_count": 0,
                "exact_count": 0,
                "models_used": [],
                "methods_used": [],
            }

        total_tokens = sum(r.count for r in results)
        average_tokens = total_tokens / len(results)
        min_tokens = min(r.count for r in results)
        max_tokens = max(r.count for r in results)
        estimated_count = sum(1 for r in results if r.estimated)
        exact_count = sum(1 for r in results if not r.estimated)
        models_used = list(set(r.model for r in results if r.model))
        methods_used = list(set(r.method for r in results))

        return {
            "total_tokens": total_tokens,
            "average_tokens": average_tokens,
            "min_tokens": min_tokens,
            "max_tokens": max_tokens,
            "estimated_count": estimated_count,
            "exact_count": exact_count,
            "models_used": models_used,
            "methods_used": methods_used,
        }

    def is_available(self) -> bool:
        """
        Check if tiktoken is available for exact token counting.

        Returns:
            True if tiktoken is available, False otherwise
        """
        return TIKTOKEN_AVAILABLE
