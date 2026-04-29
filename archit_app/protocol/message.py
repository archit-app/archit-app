"""Discriminated union over all top-level protocol messages."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field, TypeAdapter

from archit_app.protocol.handoff import AgentHandoff
from archit_app.protocol.mutation import MutationEnvelope
from archit_app.protocol.report import ProtocolReport
from archit_app.protocol.snapshot import FloorplanSnapshot

ProtocolMessage = Annotated[
    Union[FloorplanSnapshot, AgentHandoff, MutationEnvelope, ProtocolReport],
    Field(discriminator="message_type"),
]

_ADAPTER: TypeAdapter[ProtocolMessage] = TypeAdapter(ProtocolMessage)


def parse_message(payload: str | bytes | dict) -> ProtocolMessage:
    """Parse a JSON string, bytes, or dict into a concrete protocol message."""
    if isinstance(payload, dict):
        return _ADAPTER.validate_python(payload)
    return _ADAPTER.validate_json(payload)


def dump_message(msg: ProtocolMessage) -> dict:
    """Serialize any protocol message to a JSON-safe dict."""
    return _ADAPTER.dump_python(msg, mode="json", exclude_none=True)
