from fastapi import APIRouter

from backend.api.employees.router import router as agent_management_router
from backend.api.analytics.router import router as analytics_router
from backend.api.auth.router import router as auth_router
from backend.api.billing.router import router as billing_router
from backend.api.conversations.router import router as conversation_router
from backend.api.integrations.router import router as integrations_router
from backend.api.knowledge.router import router as knowledge_router
from backend.api.runtime.router import router as runtime_router
from backend.api.memory.router import router as memory_router
from backend.api.permissions.router import router as permissions_router
from backend.api.organizations.router import router as organizations_router
from backend.api.roles.router import router as roles_router
from backend.api.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(billing_router)
api_router.include_router(analytics_router)
api_router.include_router(agent_management_router)
api_router.include_router(integrations_router)
api_router.include_router(conversation_router)
api_router.include_router(knowledge_router)
api_router.include_router(runtime_router)
api_router.include_router(memory_router)
