from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from itx_backend.config import settings
from itx_backend.security.pii import redact_payload

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


class LLMUnavailable(RuntimeError):
    """Raised when the LLM provider is not configured or the call failed in a non-recoverable way."""


class LLMClient:
    """Thin async wrapper around the Anthropic Messages API.

    Responsibilities:
    - Lazy-load the SDK and system prompt so import-time cost is zero.
    - Apply prompt caching to the system prompt and the tool schemas (these change rarely; the user
      message and tool results change every turn).
    - Surface a uniform response shape the runner can consume regardless of SDK quirks.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._system_prompt: Optional[str] = None

    def _load_system_prompt(self) -> str:
        if self._system_prompt is None:
            try:
                self._system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise LLMUnavailable(f"system_prompt_missing:{exc}") from exc
        return self._system_prompt

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not settings.anthropic_api_key:
            raise LLMUnavailable("anthropic_api_key_not_configured")
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as exc:
            raise LLMUnavailable("anthropic_sdk_not_installed") from exc
        kwargs: dict[str, Any] = {
            "api_key": settings.anthropic_api_key,
            "timeout": settings.agent_request_timeout_seconds,
        }
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        self._client = AsyncAnthropic(**kwargs)
        return self._client

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        """Call Anthropic Messages API once.

        Args:
            messages: Conversation turns in Anthropic format: [{"role": "user"|"assistant", "content": ...}].
            tools: Tool schemas the model may call, in Anthropic tool format.
            model: Override the configured model (e.g. for one-shot deep reasoning).
            max_tokens: Override the configured output cap.

        Returns:
            Dict with keys: `stop_reason`, `content` (list of blocks), `usage`.
        """
        client = self._get_client()
        system_prompt = self._load_system_prompt()

        # Prompt caching: system prompt rarely changes, tool schemas rarely change, so mark both
        # with cache_control. The user messages and tool_results are NOT cached (they change every turn).
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        request_kwargs: dict[str, Any] = {
            "model": model or settings.agent_model,
            "max_tokens": max_tokens or settings.agent_max_output_tokens,
            "system": system_blocks,
            "messages": messages,
        }
        if tools:
            # Cache the last tool's schema block so the whole tools list is cached as a prefix.
            cached_tools = [dict(tool) for tool in tools]
            if cached_tools:
                cached_tools[-1] = {
                    **cached_tools[-1],
                    "cache_control": {"type": "ephemeral"},
                }
            request_kwargs["tools"] = cached_tools

        logger.debug("llm.request", extra={"payload": redact_payload(request_kwargs)})
        try:
            response = await client.messages.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001 — upstream SDK raises a broad hierarchy
            logger.warning("llm.error", extra={"error": str(exc), "model": request_kwargs["model"]})
            raise LLMUnavailable(f"anthropic_call_failed:{type(exc).__name__}") from exc

        content_blocks: list[dict[str, Any]] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                content_blocks.append({"type": "text", "text": getattr(block, "text", "")})
            elif block_type == "tool_use":
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}) or {},
                    }
                )

        usage = getattr(response, "usage", None)
        usage_dict: dict[str, Any] = {}
        if usage is not None:
            for field in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
                value = getattr(usage, field, None)
                if value is not None:
                    usage_dict[field] = value

        return {
            "stop_reason": getattr(response, "stop_reason", None),
            "content": content_blocks,
            "usage": usage_dict,
        }


llm_client = LLMClient()
