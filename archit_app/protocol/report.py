"""Unified analysis report — wraps egress / daylighting / accessibility / area / compliance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from archit_app.protocol._base import ProtocolBase
from archit_app.protocol.handoff import AgentRole
from archit_app.protocol.mutation import MutationEnvelope
from archit_app.protocol.refs import ElementRef
from archit_app.protocol.version import PROTOCOL_VERSION

ReportKind = Literal[
    "egress",
    "daylighting",
    "accessibility",
    "area",
    "compliance",
    "custom",
]

Severity = Literal["info", "warn", "error"]


class ProtocolCheck(ProtocolBase):
    """One pass/fail check inside a :class:`ProtocolReport`."""

    code: str = Field(..., min_length=1, max_length=80)
    target_ref: ElementRef | None = None
    passed: bool
    severity: Severity = "error"
    message: str = Field(..., min_length=1, max_length=400)
    metric: dict[str, float] | None = None


class Suggestion(ProtocolBase):
    """A remediation suggestion attached to a report."""

    description: str = Field(..., min_length=1, max_length=400)
    proposed_mutation: MutationEnvelope | None = None


class ReportSummary(ProtocolBase):
    """Roll-up counts for a :class:`ProtocolReport`."""

    passed: int = 0
    failed: int = 0
    warnings: int = 0


class ProtocolReport(ProtocolBase):
    """Unified analysis report — one schema for all archit-app analyses."""

    message_type: Literal["protocol_report"] = "protocol_report"
    protocol_version: str = PROTOCOL_VERSION
    message_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_role: AgentRole | None = None
    kind: ReportKind
    level_index: int | None = None
    checks: tuple[ProtocolCheck, ...] = ()
    summary: ReportSummary = Field(default_factory=ReportSummary)
    suggestions: tuple[Suggestion, ...] = ()

    @field_validator("created_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @classmethod
    def summarize(cls, checks: tuple[ProtocolCheck, ...]) -> ReportSummary:
        """Helper to compute :class:`ReportSummary` from a checks tuple."""
        passed = sum(1 for c in checks if c.passed)
        failed = sum(1 for c in checks if not c.passed and c.severity == "error")
        warnings = sum(1 for c in checks if not c.passed and c.severity == "warn")
        return ReportSummary(passed=passed, failed=failed, warnings=warnings)
