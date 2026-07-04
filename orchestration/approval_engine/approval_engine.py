from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from backend.database.models.runtime import RuntimeApprovalStatus


class ApprovalMode(str, Enum):
    ALWAYS_APPROVE = "always_approve"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    SPECIFIC_ACTIONS = "specific_actions"
    MANUAL_APPROVAL = "manual_approval"
    ESCALATION = "escalation"


@dataclass(slots=True)
class ApprovalPolicy:
    name: str = "default"
    mode: ApprovalMode = ApprovalMode.CONFIDENCE_THRESHOLD
    confidence_threshold: float = 0.8
    specific_actions: set[str] = field(default_factory=set)
    manual_actions: set[str] = field(default_factory=set)
    escalation_actions: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ApprovalDecision:
    status: RuntimeApprovalStatus
    approved: bool
    requires_human: bool = False
    escalated: bool = False
    reason: str | None = None
    decided_by: UUID | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


class ApprovalEngine(Protocol):
    def decide(
        self,
        *,
        action_name: str,
        confidence: float,
        policy: ApprovalPolicy | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ApprovalDecision: ...


class DefaultApprovalEngine:
    def decide(
        self,
        *,
        action_name: str,
        confidence: float,
        policy: ApprovalPolicy | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ApprovalDecision:
        policy = policy or ApprovalPolicy()
        metadata = metadata_json or {}
        if policy.mode == ApprovalMode.ALWAYS_APPROVE:
            return ApprovalDecision(status=RuntimeApprovalStatus.APPROVED, approved=True, metadata_json=metadata)
        if action_name in policy.escalation_actions:
            return ApprovalDecision(
                status=RuntimeApprovalStatus.ESCALATED,
                approved=False,
                requires_human=True,
                escalated=True,
                reason="Action requires escalation",
                metadata_json=metadata,
            )
        if action_name in policy.manual_actions or policy.mode == ApprovalMode.MANUAL_APPROVAL:
            return ApprovalDecision(
                status=RuntimeApprovalStatus.PENDING,
                approved=False,
                requires_human=True,
                reason="Manual approval required",
                metadata_json=metadata,
            )
        if policy.mode == ApprovalMode.SPECIFIC_ACTIONS and action_name in policy.specific_actions:
            return ApprovalDecision(status=RuntimeApprovalStatus.APPROVED, approved=True, metadata_json=metadata)
        if confidence < policy.confidence_threshold:
            return ApprovalDecision(
                status=RuntimeApprovalStatus.PENDING,
                approved=False,
                requires_human=True,
                reason="Confidence below threshold",
                metadata_json=metadata,
            )
        return ApprovalDecision(status=RuntimeApprovalStatus.APPROVED, approved=True, metadata_json=metadata)
