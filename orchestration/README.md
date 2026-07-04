# Orchestration

Cross-agent coordination, workflow management, and execution planning live here.

## Runtime Modules

- `runtime/`: Generic runtime facade that composes the orchestration pipeline.
- `planner/`: Task decomposition into executable steps.
- `executor/`: Step execution and pipeline coordination.
- `memory_manager/`: Short-term, conversation, long-term, and organization memory access.
- `knowledge_manager/`: Knowledge Engine adapter and citation ranking.
- `tool_manager/`: Common tool interface and execution registry.
- `agent_registry/`: Dynamic agent metadata registry.
- `workflow_engine/`: Sequential, parallel, conditional, retry, loop, approval, and timeout orchestration.
- `event_bus/`: Event publication for runtime lifecycle events.
- `approval_engine/`: Approval policies and decisions.
- `conversation_manager/`: Conversation, action, tool usage, cost, and latency tracking.
- `telemetry/`: Runtime metrics collection and emission.

## Runtime Contract

- No hardcoded agents.
- No employee-specific logic.
- No hardcoded prompts.
- Every AI employee must execute through the same runtime pipeline.
