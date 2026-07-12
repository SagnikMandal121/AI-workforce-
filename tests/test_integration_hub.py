from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app import app
from backend.core.config import Settings
from backend.core.deps import get_current_user, get_integration_service
from backend.core.security import Role, UserStatus
from database.models.integration import Integration, IntegrationProvider, IntegrationStatus
from database.models.organization import Organization
from database.models.user import User
from database.repositories.integration import IntegrationRepository, OAuthTokenRepository
from database.schemas.integration import IntegrationActionRequest, IntegrationConnectRequest, IntegrationCallbackRequest
from database.session import get_session
from backend.services.integration_service import IntegrationService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def get(self, key: str):
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0


def make_settings() -> Settings:
    return Settings(
        environment="test",
        secret_key="test-secret-value-that-is-long-enough-for-hs256",
        integration_encryption_key="test-integration-secret",
        database_url="sqlite+pysqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
        integration_oauth_state_expire_minutes=10,
        integration_refresh_window_minutes=15,
        integration_refresh_lock_seconds=60,
    )


def create_org_and_owner(db_session):
    organization = Organization(company_name="Acme Inc", domain="acme.example", timezone="UTC", subscription="trial")
    db_session.add(organization)
    db_session.flush()
    owner = User(
        organization_id=organization.organization_id,
        first_name="Ada",
        last_name="Lovelace",
        email="owner@acme.example",
        password_hash="hash",
        role=Role.OWNER,
        status=UserStatus.ACTIVE,
    )
    db_session.add(owner)
    db_session.commit()
    return organization, owner


def build_service(db_session):
    return IntegrationService(session=db_session, settings=make_settings(), redis_client=FakeRedis())


def test_service_lifecycle_and_refresh(db_session):
    _, owner = create_org_and_owner(db_session)
    service = build_service(db_session)

    connect_response = service.connect(
        owner,
        IntegrationConnectRequest(provider=IntegrationProvider.GMAIL, allowed_user_ids=[owner.id]),
    )

    assert connect_response.requires_authorization is True
    assert connect_response.authorization_url is not None
    assert connect_response.state is not None

    integration = service.callback(
        current_user=None,
        provider=IntegrationProvider.GMAIL,
        payload=IntegrationCallbackRequest(code="auth-code", state=connect_response.state),
    )
    assert integration.status == IntegrationStatus.CONNECTED
    assert integration.has_tokens is True
    assert integration.metadata_json["provider"] == "gmail"

    validate_response = service.validate(owner, integration.id)
    assert validate_response.valid is True

    execute_response = service.test(
        owner,
        IntegrationActionRequest(
            integration_id=integration.id,
            action="send_message",
            payload={"to": "hello@example.com"},
        ),
    )
    assert execute_response.valid is True
    assert execute_response.result["action"] == "send_message"

    token = OAuthTokenRepository(db_session).get_by_integration_id(integration.id)
    assert token is not None
    token.access_token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    refreshed = service.refresh_due_tokens()
    assert refreshed == 1

    updated_token = OAuthTokenRepository(db_session).get_by_integration_id(integration.id)
    assert updated_token is not None
    assert updated_token.refresh_attempts == 0
    assert updated_token.last_refresh_error is None

    disconnected = service.disconnect(owner, integration.id)
    assert disconnected.status == IntegrationStatus.DISCONNECTED


def test_visible_hub_lists_supported_integrations(db_session):
    _, owner = create_org_and_owner(db_session)
    service = build_service(db_session)

    hub = service.list_hub(owner)
    providers = {item.provider.value for item in hub.supported_integrations}
    assert {"gmail", "outlook", "google_calendar", "notion"}.issubset(providers)


def test_router_endpoints(db_session):
    _, owner = create_org_and_owner(db_session)
    service = build_service(db_session)
    client = TestClient(app)

    def override_current_user():
        return owner

    def override_service():
        return service

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_integration_service] = override_service
    try:
        connect = client.post(
            "/api/v1/integrations/connect",
            json={"provider": "gmail", "allowed_user_ids": [str(owner.id)]},
        )
        assert connect.status_code == 200
        state = connect.json()["state"]

        callback = client.get(
            "/api/v1/integrations/oauth/gmail/callback",
            params={"code": "auth-code", "state": state},
        )
        assert callback.status_code == 200

        status = client.get("/api/v1/integrations/status")
        assert status.status_code == 200
        assert status.json()["connected_integrations"] == 1

        hub = client.get("/api/v1/integrations")
        assert hub.status_code == 200

        integration_id = callback.json()["id"]
        test_action = client.post(
            "/api/v1/integrations/test",
            json={"integration_id": integration_id, "action": "validate", "payload": {}},
        )
        assert test_action.status_code == 200

        disconnect = client.delete(f"/api/v1/integrations/{integration_id}")
        assert disconnect.status_code == 200
    finally:
        app.dependency_overrides.clear()