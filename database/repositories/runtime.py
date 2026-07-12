from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models.runtime import (
    RuntimeAgent,
    RuntimeApproval,
    RuntimeConversation,
    RuntimeConversationMessage,
    RuntimeEvent,
    RuntimeTelemetry,
    RuntimeTask,
    RuntimeTaskStep,
)
from database.repositories.base import BaseRepository


class RuntimeAgentRepository(BaseRepository):
    def create(self, agent: RuntimeAgent) -> RuntimeAgent:
        self.session.add(agent)
        self.session.flush()
        return agent

    def get_by_id(self, agent_id: UUID) -> RuntimeAgent | None:
        stmt = select(RuntimeAgent).where(RuntimeAgent.id == agent_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_name(self, organization_id: UUID, name: str) -> RuntimeAgent | None:
        stmt = select(RuntimeAgent).where(RuntimeAgent.organization_id == organization_id, RuntimeAgent.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[RuntimeAgent]:
        stmt = select(RuntimeAgent).where(RuntimeAgent.organization_id == organization_id).order_by(RuntimeAgent.name)
        return list(self.session.execute(stmt).scalars().all())


class RuntimeConversationRepository(BaseRepository):
    def create(self, conversation: RuntimeConversation) -> RuntimeConversation:
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def get_by_id(self, conversation_id: UUID) -> RuntimeConversation | None:
        stmt = (
            select(RuntimeConversation)
            .where(RuntimeConversation.id == conversation_id)
            .options(selectinload(RuntimeConversation.messages), selectinload(RuntimeConversation.tasks))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[RuntimeConversation]:
        stmt = (
            select(RuntimeConversation)
            .where(RuntimeConversation.organization_id == organization_id)
            .order_by(RuntimeConversation.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())


class RuntimeConversationMessageRepository(BaseRepository):
    def create(self, message: RuntimeConversationMessage) -> RuntimeConversationMessage:
        self.session.add(message)
        self.session.flush()
        return message

    def list_by_conversation(self, conversation_id: UUID) -> list[RuntimeConversationMessage]:
        stmt = (
            select(RuntimeConversationMessage)
            .where(RuntimeConversationMessage.conversation_id == conversation_id)
            .order_by(RuntimeConversationMessage.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())


class RuntimeTaskRepository(BaseRepository):
    def create(self, task: RuntimeTask) -> RuntimeTask:
        self.session.add(task)
        self.session.flush()
        return task

    def get_by_id(self, task_id: UUID) -> RuntimeTask | None:
        stmt = (
            select(RuntimeTask)
            .where(RuntimeTask.id == task_id)
            .options(
                selectinload(RuntimeTask.steps),
                selectinload(RuntimeTask.events),
                selectinload(RuntimeTask.approvals),
                selectinload(RuntimeTask.telemetry),
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_organization(self, organization_id: UUID) -> list[RuntimeTask]:
        stmt = select(RuntimeTask).where(RuntimeTask.organization_id == organization_id).order_by(RuntimeTask.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())


class RuntimeTaskStepRepository(BaseRepository):
    def create_many(self, steps: list[RuntimeTaskStep]) -> list[RuntimeTaskStep]:
        self.session.add_all(steps)
        self.session.flush()
        return steps

    def list_by_task(self, task_id: UUID) -> list[RuntimeTaskStep]:
        stmt = select(RuntimeTaskStep).where(RuntimeTaskStep.task_id == task_id).order_by(RuntimeTaskStep.step_index)
        return list(self.session.execute(stmt).scalars().all())


class RuntimeEventRepository(BaseRepository):
    def create(self, event: RuntimeEvent) -> RuntimeEvent:
        self.session.add(event)
        self.session.flush()
        return event

    def list_by_organization(self, organization_id: UUID, limit: int = 100) -> list[RuntimeEvent]:
        stmt = (
            select(RuntimeEvent)
            .where(RuntimeEvent.organization_id == organization_id)
            .order_by(RuntimeEvent.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())


class RuntimeApprovalRepository(BaseRepository):
    def create(self, approval: RuntimeApproval) -> RuntimeApproval:
        self.session.add(approval)
        self.session.flush()
        return approval

    def list_by_task(self, task_id: UUID) -> list[RuntimeApproval]:
        stmt = select(RuntimeApproval).where(RuntimeApproval.task_id == task_id).order_by(RuntimeApproval.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())


class RuntimeTelemetryRepository(BaseRepository):
    def create(self, entry: RuntimeTelemetry) -> RuntimeTelemetry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_by_task(self, task_id: UUID) -> list[RuntimeTelemetry]:
        stmt = select(RuntimeTelemetry).where(RuntimeTelemetry.task_id == task_id).order_by(RuntimeTelemetry.created_at.desc())
        return list(self.session.execute(stmt).scalars().all())
