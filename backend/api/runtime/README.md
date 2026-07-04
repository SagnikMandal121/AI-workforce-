# Runtime API

Generic runtime endpoints for agent registry, planning, execution, conversations, approvals, events, and telemetry.

## Endpoints

- `GET /api/v1/runtime/status`
- `GET /api/v1/runtime/agents`
- `POST /api/v1/runtime/agents`
- `GET /api/v1/runtime/agents/{agent_id}`
- `POST /api/v1/runtime/tasks/plan`
- `POST /api/v1/runtime/tasks/execute`
- `GET /api/v1/runtime/tasks`
- `GET /api/v1/runtime/tasks/{task_id}`
- `GET /api/v1/runtime/conversations`
- `GET /api/v1/runtime/conversations/{conversation_id}`
- `GET /api/v1/runtime/events`
- `GET /api/v1/runtime/tasks/{task_id}/telemetry`
- `POST /api/v1/runtime/approvals/approve`
- `POST /api/v1/runtime/approvals/reject`

## Design Notes

- No employee-specific behavior lives here.
- Agents are loaded dynamically from the runtime registry.
- The execution pipeline is intentionally pluggable across planner, knowledge, memory, tools, approval, workflow, and telemetry modules.
- LangGraph is used as the workflow orchestration layer with a fallback execution path.
