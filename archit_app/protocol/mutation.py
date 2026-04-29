"""Mutation envelope — every agent-proposed state change is wrapped in one."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from archit_app.protocol._base import ProtocolBase
from archit_app.protocol.handoff import AgentRole
from archit_app.protocol.refs import ElementRef
from archit_app.protocol.version import PROTOCOL_VERSION

Operation = Literal["create", "update", "delete", "move", "split", "merge"]


class MutationEnvelope(ProtocolBase):
    """Records a single state mutation an agent caused."""

    message_type: Literal["mutation_envelope"] = "mutation_envelope"
    protocol_version: str = PROTOCOL_VERSION
    message_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_role: AgentRole
    operation: Operation
    target_ref: ElementRef
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    justification: str = Field(..., min_length=20, max_length=600)
    constraints_respected: tuple[str, ...] = ()

    @field_validator("created_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @model_validator(mode="after")
    def _check_diff_shape(self) -> "MutationEnvelope":
        op = self.operation
        if op == "create":
            if self.before is not None:
                raise ValueError("create mutations must have before=None")
            if self.after is None:
                raise ValueError("create mutations must have after set")
        elif op == "delete":
            if self.after is not None:
                raise ValueError("delete mutations must have after=None")
            if self.before is None:
                raise ValueError("delete mutations must have before set")
        else:
            if self.before is None or self.after is None:
                raise ValueError(
                    f"{op!r} mutations must have both before and after set"
                )
        return self
