# AI Workforce Runtime Architecture

## Overview
The AI Workforce Runtime is the core orchestration engine powering all AI employees. It provides a generalized, stateful, and resilient execution environment for processing tasks, managing memory, interacting with the knowledge base, and safely executing tools.

## Core Modules

### 1. Agent Registry (`agent_registry/`)
Stores configuration for all AI employees. Data is stored in PostgreSQL via SQLAlchemy.
- **Fields**: id, name, role, system_prompt, allowed_tools, capabilities.
- **Why**: Allows agents to be dynamically loaded rather than hardcoded.

### 2. Workflow Engine & Planner (`workflow_engine/`, `planner/`, `executor/`)
Built with **LangGraph** to handle stateful task execution.
- **Planner**: Takes a user task and uses an LLM to break it down into an actionable plan (`PlanStep` objects).
- **Executor**: Steps through the plan, invoking tools and pausing for human approval when necessary.
- **Graph**: Manages state transitions (Sequential, Parallel, Conditional loops).

### 3. Tool Manager (`tool_manager/`)
Provides a generic base class (`BaseTool`) for all integrations (Email, Slack, Calendar, CRM).
- Enforces a standard contract: `execute`, `validate`, `health`, and built-in `retry` mechanisms.

### 4. Memory & Knowledge (`memory_manager/`, `knowledge_manager/`)
- **Memory**: Backed by Redis (Short-term) and PostgreSQL (Long-term) to retain conversation history and context compression.
- **Knowledge**: Interfaces with an external Knowledge Engine to retrieve, rank, and inject relevant context into the LLM prompt.

### 5. Event Bus (`event_bus/`)
Backed by **Redis Pub/Sub** to decouple system components.
- Broadcasts system events like `Task Started`, `Tool Called`, `Task Completed`.
- Consumed by telemetry and conversation storage listeners.

### 6. Telemetry & Approval (`telemetry/`, `approval_engine/`, `conversation_manager/`)
- Tracks latency, token usage, cost, and errors to PostgreSQL.
- **Approval Engine**: Enforces threshold-based or manual-approval gates before critical actions are executed by the `executor`.

## Tech Stack Summary
- **API Framework**: FastAPI
- **State Machine**: LangGraph
- **Database (Relational)**: PostgreSQL via SQLAlchemy (asyncpg)
- **Database (Cache/Events)**: Redis
- **Concurrency**: AsyncIO
