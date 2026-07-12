from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from backend.app import app
from backend.core.config import Settings
from backend.core.deps import get_current_user, get_knowledge_service
from backend.core.security import Role, UserStatus
from database.models.knowledge import DocumentSourceType
from database.models.organization import Organization
from database.models.user import User
from database.schemas.knowledge import DocumentUploadCreate, KnowledgeBaseCreate, SearchRequest
from backend.services.knowledge_service import KnowledgeService


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        return True

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.kv[key] = value

    def get(self, key: str):
        return self.kv.get(key)

    def delete(self, key: str) -> None:
        self.kv.pop(key, None)
        self.lists.pop(key, None)

    def exists(self, key: str) -> int:
        return 1 if key in self.kv or key in self.lists else 0

    def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def rpop(self, key: str):
        values = self.lists.get(key)
        if not values:
            return None
        return values.pop()

    def scan_iter(self, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self.kv.keys()):
            if key.startswith(prefix):
                yield key


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
        knowledge_embedding_provider="deterministic",
        knowledge_embedding_dimensions=256,
        knowledge_chunk_size=1200,
        knowledge_chunk_overlap=200,
        knowledge_search_cache_ttl_seconds=60,
    )


def create_org_and_user(db_session, *, role: Role = Role.ADMIN) -> tuple[Organization, User]:
    organization = Organization(company_name="Acme Inc", domain="acme.example", timezone="UTC", subscription="trial")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.organization_id,
        first_name="Ada",
        last_name="Lovelace",
        email="admin@acme.example",
        password_hash="hash",
        role=role,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return organization, user


def build_service(db_session, redis_client: FakeRedis | None = None) -> KnowledgeService:
    return KnowledgeService(session=db_session, settings=make_settings(), redis_client=redis_client or FakeRedis())


def test_service_upload_search_reindex_and_cache(db_session):
    _, actor = create_org_and_user(db_session)
    redis_client = FakeRedis()
    service = build_service(db_session, redis_client)

    knowledge_base = service.create_knowledge_base(
        actor,
        KnowledgeBaseCreate(name="Policy Library", description="Internal policies"),
    )

    uploaded = service.upload_document(
        actor,
        knowledge_base.id,
        DocumentUploadCreate(
            title="Employee Handbook",
            source_type=DocumentSourceType.TXT,
            content_text="Alpha beta gamma delta epsilon zeta",
            process_inline=True,
        ),
    )

    assert uploaded.version.chunk_count == 1
    assert len(uploaded.chunks) == 1

    search_payload = SearchRequest(
        query="Alpha beta gamma delta epsilon zeta",
        top_k=1,
        knowledge_base_id=knowledge_base.id,
    )

    first_search = service.semantic_search(actor, search_payload)
    assert first_search.cache_hit is False
    assert first_search.results[0].document.id == uploaded.document.id

    second_search = service.semantic_search(actor, search_payload)
    assert second_search.cache_hit is True
    assert second_search.results[0].chunk.id == first_search.results[0].chunk.id

    reindexed = service.reindex_document(actor, uploaded.document.id)
    assert reindexed.version.chunk_count == 1
    assert len(reindexed.chunks) == 1

    third_search = service.semantic_search(actor, search_payload)
    assert third_search.cache_hit is False

    health = service.get_health(actor)
    assert health.knowledge_bases == 1
    assert health.documents == 1
    assert health.chunks == 1
    assert health.embeddings == 1


def test_router_smoke_flow(db_session):
    _, actor = create_org_and_user(db_session)
    service = build_service(db_session)
    client = TestClient(app)

    def override_current_user():
        return actor

    def override_service():
        return service

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_knowledge_service] = override_service
    try:
        create_base = client.post(
            "/api/v1/knowledge/bases",
            json={"name": "Policy Library", "description": "Internal policies", "metadata": {}},
        )
        assert create_base.status_code == 200
        knowledge_base_id = UUID(create_base.json()["id"])

        upload = client.post(
            f"/api/v1/knowledge/bases/{knowledge_base_id}/documents",
            json={
                "title": "Employee Handbook",
                "source_type": "txt",
                "content_text": "Alpha beta gamma delta epsilon zeta",
                "process_inline": True,
            },
        )
        assert upload.status_code == 200

        search = client.post(
            "/api/v1/knowledge/search/semantic",
            json={
                "query": "Alpha beta gamma delta epsilon zeta",
                "top_k": 1,
                "knowledge_base_id": str(knowledge_base_id),
                "filters": {},
                "search_type": "semantic",
            },
        )
        assert search.status_code == 200
        assert search.json()["results"]

        document_id = upload.json()["id"]
        reindex = client.post(f"/api/v1/knowledge/documents/{document_id}/reindex")
        assert reindex.status_code == 200

        health = client.get("/api/v1/knowledge/health")
        assert health.status_code == 200
        assert health.json()["documents"] == 1
    finally:
        app.dependency_overrides.clear()