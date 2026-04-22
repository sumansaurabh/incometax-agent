from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    """Single tool the LLM may invoke.

    name: identifier the LLM will call. Must be stable; changing it breaks prompt caches.
    description: natural-language description the LLM reads when choosing a tool. Be specific
        about WHEN to call it, not just what it does.
    input_schema: JSON Schema for the tool's input arguments (Anthropic-compatible draft).
    handler: async function that takes (thread_id=..., **args) and returns a JSON-serializable dict.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ToolRegistry:
    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"tool_already_registered:{spec.name}")
        self._tools[spec.name] = spec
        return spec

    def tool(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Decorator form: @registry.tool(name=..., description=..., input_schema=...)."""

        def decorator(handler: ToolHandler) -> ToolHandler:
            if not inspect.iscoroutinefunction(handler):
                raise TypeError(f"tool_handler_must_be_async:{name}")
            self.register(ToolSpec(name=name, description=description, input_schema=input_schema, handler=handler))
            return handler

        return decorator

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def anthropic_schemas(self) -> list[dict[str, Any]]:
        return [spec.anthropic_schema() for spec in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


tool_registry = ToolRegistry()
