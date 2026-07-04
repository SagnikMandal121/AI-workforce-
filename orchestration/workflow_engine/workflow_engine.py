from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from backend.database.models.runtime import RuntimeStepType
from orchestration.planner.planner import ExecutionPlan, PlanStep

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback when langgraph is unavailable
    END = "END"
    StateGraph = None


@dataclass(slots=True)
class WorkflowStepResult:
    name: str
    step_type: RuntimeStepType
    success: bool
    output_json: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    retries: int = 0


@dataclass(slots=True)
class WorkflowRunResult:
    success: bool
    step_results: list[WorkflowStepResult] = field(default_factory=list)
    metadata_json: dict[str, Any] = field(default_factory=dict)


class StepExecutor(Protocol):
    async def __call__(self, step: PlanStep, state: dict[str, Any]) -> WorkflowStepResult: ...


class WorkflowEngine:
    def build_graph(self, step_executor: StepExecutor):
        if StateGraph is None:
            return None
        graph = StateGraph(dict)

        async def run_steps(state: dict[str, Any]) -> dict[str, Any]:
            plan: ExecutionPlan = state["plan"]
            results: list[WorkflowStepResult] = []
            for step in plan.steps:
                result = await step_executor(step, state)
                results.append(result)
                state.setdefault("step_results", []).append(result)
                if not result.success and step.step_type not in {RuntimeStepType.RETRY, RuntimeStepType.LOOP}:
                    state["failed"] = True
                    state["error"] = result.error
                    break
            state["step_results"] = results
            state["success"] = not state.get("failed", False)
            return state

        graph.add_node("run_steps", run_steps)
        graph.set_entry_point("run_steps")
        graph.add_edge("run_steps", END)
        return graph.compile()

    async def execute(self, plan: ExecutionPlan, step_executor: StepExecutor) -> WorkflowRunResult:
        graph = self.build_graph(step_executor)
        if graph is not None:
            state = await graph.ainvoke({"plan": plan, "step_results": [], "failed": False})
            return WorkflowRunResult(
                success=bool(state.get("success", False)),
                step_results=list(state.get("step_results", [])),
                metadata_json={"engine": "langgraph"},
            )
        results: list[WorkflowStepResult] = []
        success = True
        for step in plan.steps:
            result = await step_executor(step, {"plan": plan, "step_results": results})
            results.append(result)
            if not result.success:
                success = False
                break
        return WorkflowRunResult(success=success, step_results=results, metadata_json={"engine": "fallback"})
