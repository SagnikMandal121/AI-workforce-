from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class TelemetryRecord:
    id: UUID = field(default_factory=uuid4)
    organization_id: UUID | None = None
    task_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_id: UUID | None = None
    metric_name: str = ""
    metric_value: float = 0.0
    unit: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TelemetryCollector:
    def __init__(self) -> None:
        self._records: list[TelemetryRecord] = []

    def record(self, record: TelemetryRecord) -> TelemetryRecord:
        self._records.append(record)
        return record

    def record_latency(self, *, organization_id: UUID | None, task_id: UUID | None, metric_name: str, latency_ms: int, metadata_json: dict[str, Any] | None = None) -> TelemetryRecord:
        return self.record(
            TelemetryRecord(
                organization_id=organization_id,
                task_id=task_id,
                metric_name=metric_name,
                metric_value=float(latency_ms),
                unit="ms",
                metadata_json=metadata_json or {},
            )
        )

    def record_cost(self, *, organization_id: UUID | None, task_id: UUID | None, cost: float, metadata_json: dict[str, Any] | None = None) -> TelemetryRecord:
        return self.record(
            TelemetryRecord(
                organization_id=organization_id,
                task_id=task_id,
                metric_name="cost",
                metric_value=cost,
                unit="currency",
                metadata_json=metadata_json or {},
            )
        )

    def record_tokens(self, *, organization_id: UUID | None, task_id: UUID | None, prompt_tokens: int, completion_tokens: int, metadata_json: dict[str, Any] | None = None) -> tuple[TelemetryRecord, TelemetryRecord]:
        return (
            self.record(
                TelemetryRecord(
                    organization_id=organization_id,
                    task_id=task_id,
                    metric_name="prompt_tokens",
                    metric_value=float(prompt_tokens),
                    unit="tokens",
                    metadata_json=metadata_json or {},
                )
            ),
            self.record(
                TelemetryRecord(
                    organization_id=organization_id,
                    task_id=task_id,
                    metric_name="completion_tokens",
                    metric_value=float(completion_tokens),
                    unit="tokens",
                    metadata_json=metadata_json or {},
                )
            ),
        )

    def record_error(self, *, organization_id: UUID | None, task_id: UUID | None, error: str, metadata_json: dict[str, Any] | None = None) -> TelemetryRecord:
        payload = {"error": error, **(metadata_json or {})}
        return self.record(
            TelemetryRecord(
                organization_id=organization_id,
                task_id=task_id,
                metric_name="error",
                metric_value=1.0,
                unit="count",
                metadata_json=payload,
            )
        )

    def record_retry(self, *, organization_id: UUID | None, task_id: UUID | None, retries: int, metadata_json: dict[str, Any] | None = None) -> TelemetryRecord:
        return self.record(
            TelemetryRecord(
                organization_id=organization_id,
                task_id=task_id,
                metric_name="retry",
                metric_value=float(retries),
                unit="count",
                metadata_json=metadata_json or {},
            )
        )

    def list_records(self) -> list[TelemetryRecord]:
        return list(self._records)
