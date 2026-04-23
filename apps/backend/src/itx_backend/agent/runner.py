from __future__ import annotations

import json
import logging
from typing import Any, Optional

from itx_backend.agent.llm_client import LLMUnavailable, llm_client
from itx_backend.agent.tool_registry import ToolRegistry, tool_registry
from itx_backend.config import settings

# Import for side effects: each tool module registers itself with `tool_registry` at import time.
from itx_backend.agent import tools as _tools  # noqa: F401

logger = logging.getLogger(__name__)


class AgentRunner:
    """Tool-calling loop.

    The runner speaks Anthropic's tool-use protocol:
    1. Send user message + prior history + tool schemas to the model.
    2. If the model stops with `tool_use`, execute each requested tool against the registry and
       append a `tool_result` message; loop.
    3. Otherwise (stop_reason = "end_turn" or step cap hit) return the final text.

    The runner is deliberately provider-specific (Anthropic only) — a provider-neutral wrapper is
    out of scope for Phase 0 per the approved plan.
    """

    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self._registry = registry or tool_registry

    async def run(
        self,
        *,
        thread_id: str,
        user_message: str,
        history: Optional[list[dict[str, Any]]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute one user turn.

        Args:
            thread_id: The chat thread this turn belongs to. Passed to every tool handler.
            user_message: The new user message text.
            history: Prior messages in Anthropic format (`{"role": "user"|"assistant", "content": ...}`).
                Only the last ~20 turns should be passed; the caller controls trimming.
            context: Optional extension-supplied context (e.g. current portal URL). Embedded into
                the user message as a structured prefix so the model can read it without a tool call.

        Returns:
            Dict with `content` (final assistant text), `tool_calls` (list of tools invoked this
            turn), `steps` (loop iterations taken), and `metadata` (usage totals, stop_reason).
        """
        messages: list[dict[str, Any]] = list(history or [])
        messages.append(
            {
                "role": "user",
                "content": self._build_user_content(user_message=user_message, context=context),
            }
        )

        tools = self._registry.anthropic_schemas() or None
        tool_calls_log: list[dict[str, Any]] = []
        usage_totals: dict[str, int] = {}
        last_stop_reason: Optional[str] = None

        for step in range(settings.agent_max_steps):
            response = await llm_client.complete(messages=messages, tools=tools)
            last_stop_reason = response.get("stop_reason")
            self._accumulate_usage(usage_totals, response.get("usage") or {})
            content_blocks = response.get("content") or []

            tool_use_blocks = [block for block in content_blocks if block.get("type") == "tool_use"]

            # Always append the assistant turn before handling tool results.
            messages.append({"role": "assistant", "content": content_blocks})

            if not tool_use_blocks:
                final_text = self._extract_text(content_blocks)
                return {
                    "content": final_text,
                    "tool_calls": tool_calls_log,
                    "steps": step + 1,
                    "metadata": {
                        "stop_reason": last_stop_reason,
                        "usage": usage_totals,
                    },
                }

            tool_result_blocks: list[dict[str, Any]] = []
            for block in tool_use_blocks:
                tool_name = block.get("name", "")
                tool_input = block.get("input") or {}
                tool_use_id = block.get("id", "")
                result_payload, is_error = await self._invoke_tool(
                    thread_id=thread_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                )
                tool_calls_log.append(
                    {
                        "name": tool_name,
                        "input": tool_input,
                        "is_error": is_error,
                        # Surface the tool's raw result so the chat layer can extract structured
                        # payloads (e.g. propose_fill proposals) without re-executing the tool.
                        # Keep it best-effort — some results are large, but the chat service trims.
                        "result": self._scrub_tool_result_for_log(result_payload),
                    }
                )
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": self._format_tool_result_content(result_payload),
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_result_blocks})

        # Step cap hit without a final answer. Synthesize a terse message.
        logger.warning(
            "agent.step_cap_hit",
            extra={"thread_id": thread_id, "max_steps": settings.agent_max_steps},
        )
        return {
            "content": "I could not finish this request within the tool-call budget. Please rephrase or ask a narrower question.",
            "tool_calls": tool_calls_log,
            "steps": settings.agent_max_steps,
            "metadata": {
                "stop_reason": last_stop_reason or "step_cap",
                "usage": usage_totals,
                "truncated": True,
            },
        }

    async def _invoke_tool(
        self,
        *,
        thread_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        spec = self._registry.get(tool_name)
        if spec is None:
            return ({"error": f"unknown_tool:{tool_name}"}, True)
        try:
            result = await spec.handler(thread_id=thread_id, **tool_input)
        except TypeError as exc:
            return ({"error": f"invalid_tool_arguments:{exc}"}, True)
        except Exception as exc:  # noqa: BLE001 — tool errors must not crash the turn
            logger.exception("tool.error", extra={"tool": tool_name, "thread_id": thread_id})
            return ({"error": f"tool_failed:{type(exc).__name__}:{exc}"}, True)
        if not isinstance(result, dict):
            return ({"error": "tool_returned_non_dict", "value": str(result)[:500]}, True)
        return (result, False)

    def _build_user_content(
        self,
        *,
        user_message: str,
        context: Optional[dict[str, Any]],
    ) -> str:
        if not context:
            return user_message
        context_str = json.dumps(context, sort_keys=True, default=str)
        return f"[portal_context]\n{context_str}\n[/portal_context]\n\n{user_message}"

    def _extract_text(self, content_blocks: list[dict[str, Any]]) -> str:
        parts = [block.get("text", "") for block in content_blocks if block.get("type") == "text"]
        return "\n\n".join(part for part in parts if part).strip()

    def _scrub_tool_result_for_log(self, payload: Any) -> Any:
        """Drop inline base64 image bytes from a tool result before logging.

        The `image.source.data` field can be hundreds of KB and has zero debugging value — the
        capture is re-obtainable on demand. Everything else (reason, captured_at, viewport,
        size_bytes) stays.
        """
        if not isinstance(payload, dict):
            return payload
        image = payload.get("image")
        if isinstance(image, dict) and isinstance(image.get("source"), dict):
            scrubbed_image = dict(image)
            scrubbed_source = dict(image["source"])
            if "data" in scrubbed_source:
                scrubbed_source["data"] = "<elided>"
            scrubbed_image["source"] = scrubbed_source
            payload = {**payload, "image": scrubbed_image}
        return payload

    def _format_tool_result_content(self, payload: Any) -> Any:
        """Return either a JSON string (default) or a content-block list when the tool
        surfaced an image.

        Anthropic tool_result `content` may be a string OR a list of blocks. Only when we have
        a real image do we use the list form, because emitting a list means the model has to
        re-parse structure — for text-only tools, a single JSON string is cheaper.
        """
        if isinstance(payload, dict) and isinstance(payload.get("image"), dict) and payload["image"].get("type") == "image":
            image_block = payload["image"]
            sidecar = {k: v for k, v in payload.items() if k != "image"}
            blocks: list[dict[str, Any]] = [image_block]
            if sidecar:
                blocks.append({"type": "text", "text": json.dumps(sidecar, default=str)})
            return blocks
        return json.dumps(payload, default=str)

    def _accumulate_usage(self, totals: dict[str, int], delta: dict[str, Any]) -> None:
        for key, value in delta.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value


agent_runner = AgentRunner()


async def run_turn(
    *,
    thread_id: str,
    user_message: str,
    history: Optional[list[dict[str, Any]]] = None,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Module-level shortcut used by the chat service.

    Centralising the entrypoint here makes it trivial to swap the runner or inject a mock in tests
    without reaching into the chat service internals.
    """
    try:
        return await agent_runner.run(
            thread_id=thread_id,
            user_message=user_message,
            history=history,
            context=context,
        )
    except LLMUnavailable as exc:
        logger.warning(
            "agent.llm_unavailable reason=%s thread_id=%s",
            str(exc),
            thread_id,
            extra={"thread_id": thread_id, "reason": str(exc)},
        )
        return {
            "content": (
                "The assistant is temporarily unavailable. Please try again in a moment; "
                "if this persists, contact support."
            ),
            "tool_calls": [],
            "steps": 0,
            "metadata": {"stop_reason": "llm_unavailable", "error": str(exc)},
        }
