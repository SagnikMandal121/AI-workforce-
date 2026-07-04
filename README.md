# AI Workforce

Production-ready monorepo scaffold for a scalable enterprise SaaS platform that orchestrates many AI employees.

## Layout

- `apps/`: Frontend applications (`web`, `landing`, `admin`)
- `backend/`: FastAPI-based backend architecture and domain modules
- `agents/`: Individual AI employee packages with isolated internal structure
- `orchestration/`: Cross-agent orchestration and workflow coordination
- `orchestration/`: Cross-agent orchestration, runtime planning, workflow execution, and telemetry
- `integrations/`: External provider adapters
- `memory/`: Shared memory and retrieval primitives
- `knowledge/`: Knowledge base and RAG-ready content structure
- `analytics/`: Analytics and reporting boundaries
- `shared/`: Shared utilities, types, constants, prompts, and middleware
- `infrastructure/`: Docker, Nginx, Redis, Postgres, monitoring, and CI/CD scaffolding
- `scripts/`: Operational scripts and developer helpers
- `tests/`: Cross-cutting test scaffolding
- `docs/`: Architecture and implementation notes

This repository now includes the shared AI Workforce Runtime and supporting orchestration modules.
