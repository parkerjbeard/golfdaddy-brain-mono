from __future__ import annotations

import io
import json
import logging
import time
from typing import Any, Dict, Iterable, List, Optional

from openai import OpenAI

from app.config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIBatchService:
    """Helper for submitting and retrieving OpenAI Batch API jobs.

    Usage pattern:
      1) Build requests as JSON objects using build_chat_request or build_responses_request
      2) enqueue_batch(requests, endpoint="/v1/responses")
      3) poll_until_complete(batch_id)
      4) download_results(batch)
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        api_key = api_key or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for batch operations")
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def build_chat_request(
        custom_id: str,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if temperature is not None:
            body["temperature"] = temperature
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        }

    @staticmethod
    def build_responses_request(
        custom_id: str,
        model: str,
        input_messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        reasoning: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model,
            "input": input_messages,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if reasoning is not None:
            body["reasoning"] = reasoning
        return {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/responses",
            "body": body,
        }

    def _serialize_requests_to_bytes(self, requests: Iterable[Dict[str, Any]]) -> bytes:
        buffer = io.StringIO()
        for req in requests:
            buffer.write(json.dumps(req, ensure_ascii=False))
            buffer.write("\n")
        return buffer.getvalue().encode("utf-8")

    def enqueue_batch(
        self,
        requests: Iterable[Dict[str, Any]],
        completion_window: str = "24h",
    ) -> Dict[str, Any]:
        """Create a batch from iterable of request objects.

        Returns the created batch object dict.
        """
        file_bytes = self._serialize_requests_to_bytes(requests)
        upload = self.client.files.create(file=("requests.jsonl", io.BytesIO(file_bytes)), purpose="batch")
        batch = self.client.batches.create(
            input_file_id=upload.id,
            completion_window=completion_window,
        )
        logger.info(f"Enqueued OpenAI batch {batch.id} with file {upload.id}")
        return batch.to_dict() if hasattr(batch, "to_dict") else batch

    def poll_until_complete(
        self,
        batch_id: str,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 60 * 60 * 24,
    ) -> Dict[str, Any]:
        """Poll batch status until it reaches a terminal state or timeout."""
        start = time.time()
        while True:
            batch = self.client.batches.retrieve(batch_id)
            status = getattr(batch, "status", None) or getattr(batch, "state", None)
            if status in {"completed", "failed", "cancelled", "expired"}:
                return batch.to_dict() if hasattr(batch, "to_dict") else batch
            if time.time() - start > timeout_seconds:
                raise TimeoutError(f"Batch {batch_id} did not complete within timeout")
            time.sleep(poll_interval_seconds)

    def download_results(self, batch: Dict[str, Any] | Any) -> List[Dict[str, Any]]:
        """Download and parse output file results for a completed batch."""
        if hasattr(batch, "output_file_id"):
            output_file_id = batch.output_file_id
        else:
            output_file_id = batch.get("output_file_id")
        if not output_file_id:
            logger.warning("No output_file_id found on batch; returning empty results")
            return []
        file_content = self.client.files.content(output_file_id)
        # file_content can be a stream; ensure bytes
        data_bytes = file_content.read() if hasattr(file_content, "read") else file_content
        lines = (data_bytes.decode("utf-8")).splitlines()
        results: List[Dict[str, Any]] = []
        for line in lines:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results
