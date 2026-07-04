from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from backend.database.models.runtime import RuntimeAgent
from backend.database.repositories.runtime import RuntimeAgentRepository
from backend.database.schemas.runtime import RuntimeAgentCreate


@dataclass(slots=True)
class AgentProfile:
    id: UUID
    organization_id: UUID
    name: str
    role: str
    description: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    required_integrations: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    capabilities: list[str] = field(default_factory=list)
    max_context: int = 8192
    temperature: float = 0.2
    enabled: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentRegistry(Protocol):
    def register(self, *, organization_id: UUID, payload: RuntimeAgentCreate) -> AgentProfile: ...

    def list_agents(self, *, organization_id: UUID) -> list[AgentProfile]: ...

    def load(self, *, organization_id: UUID, agent_id: UUID | None = None, name: str | None = None) -> AgentProfile | None: ...


class SQLAlchemyAgentRegistry:
    def __init__(self, repository: RuntimeAgentRepository) -> None:
        self.repository = repository

    def register(self, *, organization_id: UUID, payload: RuntimeAgentCreate) -> AgentProfile:
        existing = self.repository.get_by_name(organization_id, payload.name)
        if existing is None:
            agent = RuntimeAgent(
                organization_id=organization_id,
                name=payload.name,
                role=payload.role,
                description=payload.description,
                allowed_tools=payload.allowed_tools,
                required_integrations=payload.required_integrations,
                system_prompt=payload.system_prompt,
                capabilities=payload.capabilities,
                max_context=payload.max_context,
                temperature=payload.temperature,
                enabled=payload.enabled,
                metadata_json=payload.metadata_json,
            )
            self.repository.create(agent)
        else:
            existing.role = payload.role
            existing.description = payload.description
            existing.allowed_tools = payload.allowed_tools
            existing.required_integrations = payload.required_integrations
            existing.system_prompt = payload.system_prompt
            existing.capabilities = payload.capabilities
            existing.max_context = payload.max_context
            existing.temperature = payload.temperature
            existing.enabled = payload.enabled
            existing.metadata_json = payload.metadata_json
            agent = existing
        return self._serialize(agent)

    def list_agents(self, *, organization_id: UUID) -> list[AgentProfile]:
        return [self._serialize(agent) for agent in self.repository.list_by_organization(organization_id)]

    def load(self, *, organization_id: UUID, agent_id: UUID | None = None, name: str | None = None) -> AgentProfile | None:
        agent = None
        if agent_id is not None:
            agent = self.repository.get_by_id(agent_id)
        elif name is not None:
            agent = self.repository.get_by_name(organization_id, name)
        if agent is None or agent.organization_id != organization_id:
            return None
        return self._serialize(agent)

    def _serialize(self, agent: RuntimeAgent) -> AgentProfile:
        return AgentProfile(
            id=agent.id,
            organization_id=agent.organization_id,
            name=agent.name,
            role=agent.role,
            description=agent.description,
            allowed_tools=list(agent.allowed_tools or []),
            required_integrations=list(agent.required_integrations or []),
            system_prompt=agent.system_prompt,
            capabilities=list(agent.capabilities or []),
            max_context=agent.max_context,
            temperature=float(agent.temperature),
            enabled=agent.enabled,
            metadata_json=dict(agent.metadata_json or {}),
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
