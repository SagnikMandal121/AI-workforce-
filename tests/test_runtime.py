from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient

from backend.app import app
from backend.core.config import Settings
from backend.core.deps import get_current_user, get_runtime_service
from backend.core.security import Role, UserStatus
from backend.database.models.organization import Organization
from backend.database.models.user import User
from backend.database.schemas.runtime import RuntimeAgentCreate, RuntimeTaskCreate, RuntimeTaskExecutionRequest
from backend.database.session import get_session
from backend.services.runtime_service import RuntimeService
from orchestration.tool_manager import CallableTool


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def lpush(self, key: str, value: str) -> int:
        self.store[key] = value
        return 1

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value


async def send_email(payload: dict[str, object]) -> dict[str, object]:
    return {"delivered": True, "payload": payload}


def make_settings() -> Settings:
    return Settings(
        environment="test",
        secret_key="test-secret-value-that-is-long-enough-for-hs256",
        integration_encryption_key="test-integration-secret",
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        knowledge_embedding_provider="deterministic",
        knowledge_embedding_dimensions=256,
        knowledge_chunk_size=1200,
        knowledge_chunk_overlap=200,
        knowledge_search_cache_ttl_seconds=60,
    )


def create_org_and_user(db_session):
    organization = Organization(company_name="Acme Inc", domain="acme.example", timezone="UTC", subscription="trial")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.organization_id,
        first_name="Ada",
        last_name="Lovelace",
        email="admin@acme.example",
        password_hash="hash",
        role=Role.ADMIN,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return organization, user


def build_service(db_session) -> RuntimeService:
    return RuntimeService(session=db_session, settings=make_settings(), redis_client=FakeRedis())


def test_runtime_service_planning_and_execution(db_session):
    _, user = create_org_and_user(db_session)
    service = build_service(db_session)
    service.orchestrator.tools.register(CallableTool("email.send", send_email), description="Send email")

    agent = service.register_agent(
        user.organization_id,
        RuntimeAgentCreate(
            name="Email Assistant",
            role="Operations",
            description="Generic email worker",
            allowed_tools=["email.send"],
            capabilities=["email"],
        ),
    )

    task, plan = service.plan_task(
        organization_id=user.organization_id,
        request=RuntimeTaskCreate(agent_id=agent.id, task="Reply email to customer"),
        current_user=user,
    )
    assert task.status.value == "planned"
    assert len(plan.steps) >= 4

    response = asyncio.run(
        service.execute_task(
            organization_id=user.organization_id,
            request=RuntimeTaskExecutionRequest(agent_id=agent.id, task="Reply email to customer"),
            current_user=user,
        )
    )
    assert response.task.status.value == "completed"
    assert response.result["success"] is True
    assert response.plan.steps[0].name == "Read email"
    assert service.get_status(user.organization_id).agents == 1
    assert len(service.list_events(user.organization_id)) >= 2
    assert len(service.list_telemetry(user.organization_id, response.task.id)) >= 1
    if response.task.conversation_id is not None:
        assert service.get_conversation(user.organization_id, response.task.conversation_id).messages is not None


def test_runtime_router_smoke(db_session):
    _, user = create_org_and_user(db_session)
    service = build_service(db_session)
    service.orchestrator.tools.register(CallableTool("email.send", send_email), description="Send email")
    client = TestClient(app)

    def override_current_user():
        return user

    def override_service():
        return service

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_runtime_service] = override_service
    try:
        create_agent = client.post(
            "/api/v1/runtime/agents",
            json={
                "name": "Email Assistant",
                "role": "Operations",
                "description": "Generic email worker",
                "allowed_tools": ["email.send"],
                "required_integrations": [],
                "system_prompt": None,
                "capabilities": ["email"],
                "max_context": 4096,
                "temperature": 0.2,
                "enabled": True,
                "metadata_json": {},
            },
        )
        assert create_agent.status_code == 200
        agent_id = UUID(create_agent.json()["id"])

        execute = client.post(
            "/api/v1/runtime/tasks/execute",
            json={"agent_id": str(agent_id), "task": "Reply email to customer", "metadata_json": {}},
        )
        assert execute.status_code == 200
        assert execute.json()["task"]["status"] == "completed"

        status = client.get("/api/v1/runtime/status")
        assert status.status_code == 200
        assert status.json()["agents"] == 1

        tasks = client.get("/api/v1/runtime/tasks")
        assert tasks.status_code == 200
        assert len(tasks.json()) == 1
    finally:
        app.dependency_overrides.clear()
