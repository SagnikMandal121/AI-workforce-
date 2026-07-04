from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Awaitable, Callable, Protocol


class Tool(Protocol):
    name: str

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def validate(self) -> dict[str, Any]: ...

    async def health(self) -> dict[str, Any]: ...

    async def retry(self, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]: ...


@dataclass(slots=True)
class ToolResult:
    tool_name: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: int = 0
    retries: int = 0


@dataclass(slots=True)
class ToolDescriptor:
    name: str
    description: str | None = None
    enabled: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)


class CallableTool:
    def __init__(self, name: str, executor: Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]) -> None:
        self.name = name
        self._executor = executor

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._executor(payload)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def validate(self) -> dict[str, Any]:
        return {"tool": self.name, "valid": True}

    async def health(self) -> dict[str, Any]:
        return {"tool": self.name, "status": "ok"}

    async def retry(self, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        last_error: Exception | None = None
        for _ in range(max(attempts, 1)):
            try:
                return await self.execute(payload)
            except Exception as exc:  # pragma: no cover - tool-specific failure path
                last_error = exc
        raise RuntimeError(f"Tool {self.name} failed after {attempts} attempts") from last_error


class ToolManager:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._descriptors: dict[str, ToolDescriptor] = {}

    def register(self, tool: Tool, *, description: str | None = None, metadata_json: dict[str, Any] | None = None) -> None:
        self._tools[tool.name] = tool
        self._descriptors[tool.name] = ToolDescriptor(
            name=tool.name,
            description=description,
            metadata_json=metadata_json or {},
        )

    def has(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def list_tools(self) -> list[ToolDescriptor]:
        return list(self._descriptors.values())

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> ToolResult:
        if tool_name not in self._tools:
            return ToolResult(tool_name=tool_name, success=False, error="tool_not_registered")
        tool = self._tools[tool_name]
        start = perf_counter()
        try:
            output = await tool.execute(payload)
            latency_ms = int((perf_counter() - start) * 1000)
            return ToolResult(tool_name=tool_name, success=True, output=output, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((perf_counter() - start) * 1000)
            return ToolResult(tool_name=tool_name, success=False, error=str(exc), latency_ms=latency_ms)

    async def validate(self, tool_name: str) -> dict[str, Any]:
        if tool_name not in self._tools:
            return {"tool": tool_name, "valid": False, "error": "tool_not_registered"}
        return await self._tools[tool_name].validate()

    async def health(self) -> dict[str, Any]:
        results = {}
        for name, tool in self._tools.items():
            results[name] = await tool.health()
        return results

    async def retry(self, tool_name: str, payload: dict[str, Any], attempts: int = 3) -> ToolResult:
        if tool_name not in self._tools:
            return ToolResult(tool_name=tool_name, success=False, error="tool_not_registered")
        start = perf_counter()
        try:
            output = await self._tools[tool_name].retry(payload, attempts=attempts)
            latency_ms = int((perf_counter() - start) * 1000)
            return ToolResult(tool_name=tool_name, success=True, output=output, latency_ms=latency_ms, retries=max(attempts - 1, 0))
        except Exception as exc:
            latency_ms = int((perf_counter() - start) * 1000)
            return ToolResult(tool_name=tool_name, success=False, error=str(exc), latency_ms=latency_ms, retries=max(attempts - 1, 0))
