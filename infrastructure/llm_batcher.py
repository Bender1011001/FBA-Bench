import asyncio
import logging
import os
import time
import hashlib
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from infrastructure.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)


class LLMRequest:
    """Represents a single LLM request."""

    def __init__(self, request_id: str, prompt: str, model: str, callback: Callable):
        self.request_id = request_id
        self.prompt = prompt
        self.model = model
        self.callback = callback
        self.timestamp = time.time()
        self.batch_id: Optional[str] = None
        self.status: str = "pending"
        self.response: Any = None
        self.error: Optional[Exception] = None


class LLMBatcher:
    """
    Manages LLM request batching for cost optimization and throughput.
    """

    def __init__(self):
        self._pending_requests: Dict[str, LLMRequest] = {}
        self._batch_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None

        # Public attributes
        self.max_batch_size: int = 10
        self.batch_timeout_ms: int = 500
        self.similarity_threshold: float = 0.8

        # Back-compat private mirrors
        self._max_batch_size: int = self.max_batch_size
        self._batch_timeout_ms: int = self.batch_timeout_ms
        self._similarity_threshold: float = self.similarity_threshold

        self.stats = {
            "total_requests_received": 0,
            "total_requests_batched": 0,
            "total_batches_processed": 0,
            "total_tokens_estimated": 0,
            "total_api_cost_estimated": 0.0,
            "requests_deduplicated": 0,
            "avg_batch_size": 0.0,
            "max_batch_latency_ms": 0.0,
        }

    async def start(self):
        if self._running:
            logger.warning("LLMBatcher already running.")
            return
        self._running = True
        self._processing_task = asyncio.create_task(self._batching_loop())
        logger.info("LLMBatcher started.")

    async def stop(self):
        if not self._running:
            return
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("LLMBatcher stopped.")

    def add_request(self, request_id: str, prompt: str, model: str, callback: Callable):
        self.stats["total_requests_received"] += 1
        new_request = LLMRequest(request_id, prompt, model, callback)
        if request_id in self._pending_requests:
            logger.warning(f"Request ID {request_id} already exists, overwriting.")
        self._pending_requests[request_id] = new_request
        logger.debug(f"Added request {request_id} for model {model}.")

    def set_batch_parameters(
        self, max_size: int = None, timeout_ms: int = None, similarity_threshold: float = None
    ):
        if max_size is not None:
            self.max_batch_size = max_size
            self._max_batch_size = int(max_size)
        if timeout_ms is not None:
            self.batch_timeout_ms = timeout_ms
            self._batch_timeout_ms = int(timeout_ms)
        if similarity_threshold is not None:
            self.similarity_threshold = similarity_threshold
            self._similarity_threshold = float(similarity_threshold)
        logger.info(
            f"LLMBatcher parameters updated: max_size={self.max_batch_size}, timeout={self.batch_timeout_ms}ms"
        )

    async def _batching_loop(self):
        logger.info("LLMBatching loop started.")
        while self._running:
            try:
                await self._aggregate_and_process()
            except Exception as e:
                logger.error(f"Error in batching loop: {e}", exc_info=True)
            await asyncio.sleep(self.batch_timeout_ms / 1000.0 / 2)
        logger.info("LLMBatching loop stopped.")

    async def _aggregate_and_process(self):
        if not self._pending_requests:
            return

        current_time = time.time()
        requests_to_batch = []
        requests_to_remove_from_pending = []

        for req_id, req in list(self._pending_requests.items()):
            if len(requests_to_batch) < self.max_batch_size:
                if (current_time - req.timestamp) * 1000 >= self.batch_timeout_ms:
                    requests_to_batch.append(req)
                    requests_to_remove_from_pending.append(req_id)
            elif len(requests_to_batch) >= self.max_batch_size:
                break

        if not requests_to_batch and self._pending_requests:
            requests_to_batch = list(self._pending_requests.values())
            requests_to_remove_from_pending = list(self._pending_requests.keys())

        if requests_to_batch:
            for req_id in requests_to_remove_from_pending:
                self._pending_requests.pop(req_id, None)

            processed_batch = self.optimize_batch_composition(requests_to_batch)
            self._update_stats_from_batch(processed_batch)
            await self.process_batch(processed_batch)

            if self.stats["total_batches_processed"] > 0:
                self.stats["avg_batch_size"] = (
                    self.stats["total_requests_batched"] / self.stats["total_batches_processed"]
                )

            earliest_ts = min(
                (req.timestamp for lst in processed_batch.values() for req in lst),
                default=time.time(),
            )
            batch_latency = (time.time() - earliest_ts) * 1000
            self.stats["max_batch_latency_ms"] = max(
                self.stats["max_batch_latency_ms"], batch_latency
            )

    def optimize_batch_composition(self, requests: List[LLMRequest]) -> Dict[str, List[LLMRequest]]:
        """
        Groups similar requests.
        Fixes Issue #105: Uses SHA256 for stable hashing instead of UUID5.
        """
        optimized_batches: Dict[str, List[LLMRequest]] = defaultdict(list)
        deduplicated_prompts: Dict[Tuple[str, str], str] = {}

        for req in requests:
            prompt_key = (req.model, req.prompt)
            if prompt_key not in deduplicated_prompts:
                # Fix #105: Stable SHA256 hash
                prompt_hash = hashlib.sha256((req.prompt + req.model).encode('utf-8')).hexdigest()
                deduplicated_prompts[prompt_key] = prompt_hash
            else:
                self.stats["requests_deduplicated"] += 1
                logger.debug(
                    f"Deduplicated request {req.request_id} (prompt already seen for model {req.model})."
                )

            batch_key = f"{req.model}_{deduplicated_prompts[prompt_key]}"
            optimized_batches[batch_key].append(req)
            req.batch_id = batch_key

        return optimized_batches

    async def process_batch(self, batched_requests: Dict[str, List[LLMRequest]]):
        if not batched_requests:
            return

        logger.info(f"Processing {len(batched_requests)} optimized batches.")
        processor_tasks = []
        for _, requests_in_batch in batched_requests.items():
            primary_request_for_batch = requests_in_batch[0]
            task = asyncio.create_task(
                self._execute_llm_api_call(
                    primary_request_for_batch.prompt,
                    primary_request_for_batch.model,
                    requests_in_batch,
                )
            )
            processor_tasks.append(task)

        if processor_tasks:
            await asyncio.gather(*processor_tasks, return_exceptions=True)

    async def _execute_llm_api_call(
        self, prompt: str, model: str, original_requests: List[LLMRequest]
    ):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            try:
                async with OpenRouterClient(api_key) as client:
                    response = await client.chat_completions(
                        model=model,
                        prompt=prompt,
                        max_tokens=None,
                        temperature=0.7,
                    )

                content = response["content"]
                usage = response["usage"]
                cost = response["cost"]

                total_tokens = usage["total_tokens"]
                self.stats["total_tokens_estimated"] += total_tokens
                self.stats["total_api_cost_estimated"] += cost

                for req in original_requests:
                    req.status = "completed"
                    req.response = content
                    try:
                        result = req.callback(req.request_id, content, None)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("Error invoking callback for request %s", req.request_id)

            except Exception as e:
                logger.error(f"OpenRouter call failed for model {model}: {e}", exc_info=True)
                for req in original_requests:
                    req.status = "failed"
                    req.error = e
                    try:
                        result = req.callback(req.request_id, None, e)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
        else:
            error_msg = "OPENROUTER_API_KEY environment variable required for real LLM calls."
            logger.error(error_msg)
            # Ensure callback called with error to unblock waiting callers
            for req in original_requests:
                req.status = "failed"
                req.error = ValueError(error_msg)
                try:
                    result = req.callback(req.request_id, None, req.error)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

    def estimate_batch_cost(
        self, batch_of_requests: Dict[str, List[LLMRequest]]
    ) -> Tuple[int, float]:
        total_estimated_tokens = 0
        total_estimated_cost = 0.0

        for _, requests_in_batch in batch_of_requests.items():
            if requests_in_batch:
                unique_prompt = requests_in_batch[0].prompt
                estimated_prompt_tokens = len(unique_prompt) / 4
                estimated_response_tokens = 50
                batch_tokens = estimated_prompt_tokens + estimated_response_tokens
                total_estimated_tokens += batch_tokens
                cost_per_1k_tokens = 0.002
                total_estimated_cost += (batch_tokens / 1000) * cost_per_1k_tokens

        return int(total_estimated_tokens), total_estimated_cost

    def _update_stats_from_batch(self, batched_requests: Dict[str, List[LLMRequest]]):
        self.stats["total_batches_processed"] += len(batched_requests)
        for _, requests_in_batch in batched_requests.items():
            self.stats["total_requests_batched"] += len(requests_in_batch)
