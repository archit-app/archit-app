"""Inter-agent handoff message — what an agent emits when it finishes a turn."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from archit_app.protocol._base import ProtocolBase
from archit_app.protocol.refs import ElementRef
from archit_app.protocol.version import PROTOCOL_VERSION

AgentRole = Literal[
    "planner",
    "architect",
    "structural",
    "compliance",
    "interior",
    "program",
    "bim",
]

Priority = Literal["low", "med", "high"]


class Decision(ProtocolBase):
    """A single design decision an agent made during its turn."""

    title: str = Field(..., max_length=120)
    rationale: str = Field(..., min_length=1, max_length=600)
    affected_refs: tuple[ElementRef, ...] = ()


class OpenQuestion(ProtocolBase):
    """An unresolved question for a downstream agent or the user."""

    question: str = Field(..., min_length=1, max_length=300)
    blocks_next: bool = False
    for_role: AgentRole | None = None


class NextAgentHint(ProtocolBase):
    """A hint to the next agent — where to focus."""

    for_role: AgentRole
    focus_refs: tuple[ElementRef, ...] = ()
    priority: Priority = "med"
    note: str | None = Field(default=None, max_length=300)


class Telemetry(ProtocolBase):
    """Lightweight telemetry attached to a handoff."""

    tokens_in: int | None = None
    tokens_out: int | None = None
    wall_clock_s: float | None = None
    tool_calls: int = 0


class AgentHandoff(ProtocolBase):
    """Structured envelope each agent emits at task completion.

    Replaces the plain-text outputs CrewAI tasks currently exchange.
    """

    message_type: Literal["agent_handoff"] = "agent_handoff"
    protocol_version: str = PROTOCOL_VERSION
    message_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_role: AgentRole
    summary: str = Field(..., min_length=1, max_length=500)
    decisions: tuple[Decision, ...] = ()
    changes: tuple[ElementRef, ...] = ()
    open_questions: tuple[OpenQuestion, ...] = ()
    next_agent_hints: tuple[NextAgentHint, ...] = ()
    telemetry: Telemetry = Field(default_factory=Telemetry)

    @field_validator("created_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
