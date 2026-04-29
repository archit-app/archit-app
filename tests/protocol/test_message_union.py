"""Discriminated union dispatches to the correct concrete model."""

from __future__ import annotations

import pytest

from archit_app.protocol import (
    AgentHandoff,
    ElementRef,
    FloorplanSnapshot,
    MutationEnvelope,
    ProtocolReport,
    parse_message,
)


def test_parse_handoff():
    h = AgentHandoff(agent_role="architect", summary="ok")
    parsed = parse_message(h.model_dump_json())
    assert isinstance(parsed, AgentHandoff)


def test_parse_mutation():
    m = MutationEnvelope(
        agent_role="architect",
        operation="create",
        target_ref=ElementRef(id="r1", kind="room", level_index=0),
        after={"name": "kitchen"},
        justification="add kitchen room per program brief from planner",
    )
    parsed = parse_message(m.model_dump_json())
    assert isinstance(parsed, MutationEnvelope)


def test_parse_report():
    r = ProtocolReport(kind="egress", level_index=0)
    parsed = parse_message(r.model_dump_json())
    assert isinstance(parsed, ProtocolReport)


def test_parse_snapshot(tiny_building):
    snap = tiny_building.to_protocol_snapshot(mode="compact")
    parsed = parse_message(snap.model_dump_json())
    assert isinstance(parsed, FloorplanSnapshot)


def test_parse_rejects_unknown_message_type():
    with pytest.raises(Exception):
        parse_message('{"message_type": "totally_made_up", "x": 1}')


def test_parse_rejects_unknown_field():
    h = AgentHandoff(agent_role="architect", summary="ok")
    payload = h.model_dump()
    payload["extra_field"] = "no"
    with pytest.raises(Exception):
        parse_message(payload)
