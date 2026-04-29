"""Frozen, extra-forbid, and per-model validator behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archit_app.protocol import (
    AgentHandoff,
    ElementRef,
    FloorplanSnapshot,
    MutationEnvelope,
    ProtocolReport,
)


def test_models_are_frozen():
    h = AgentHandoff(agent_role="architect", summary="ok")
    with pytest.raises(ValidationError):
        h.summary = "changed"  # type: ignore[misc]


def test_models_reject_unknown_keys():
    with pytest.raises(ValidationError):
        AgentHandoff(agent_role="architect", summary="ok", unknown_field=1)  # type: ignore[call-arg]


def test_element_ref_required_fields():
    ref = ElementRef(id="abc", kind="room", level_index=0)
    assert ref.id == "abc"
    with pytest.raises(ValidationError):
        ElementRef(id="abc")  # type: ignore[call-arg]


def test_handoff_summary_length_validator():
    AgentHandoff(agent_role="architect", summary="x")
    with pytest.raises(ValidationError):
        AgentHandoff(agent_role="architect", summary="")
    with pytest.raises(ValidationError):
        AgentHandoff(agent_role="architect", summary="x" * 501)


def test_mutation_envelope_diff_invariants():
    ref = ElementRef(id="r1", kind="room", level_index=0)
    # create: after required, before forbidden
    MutationEnvelope(
        agent_role="architect",
        operation="create",
        target_ref=ref,
        after={"name": "kitchen"},
        justification="add kitchen room from program brief",
    )
    with pytest.raises(ValidationError):
        MutationEnvelope(
            agent_role="architect",
            operation="create",
            target_ref=ref,
            before={"x": 1},
            after={"y": 2},
            justification="add kitchen room from program brief",
        )
    # delete: before required, after forbidden
    with pytest.raises(ValidationError):
        MutationEnvelope(
            agent_role="architect",
            operation="delete",
            target_ref=ref,
            after={"y": 2},
            justification="remove dangling room from old layout proposal",
        )
    # update: both required
    with pytest.raises(ValidationError):
        MutationEnvelope(
            agent_role="architect",
            operation="update",
            target_ref=ref,
            after={"y": 2},
            justification="rename room to better match the program brief notes",
        )


def test_mutation_envelope_justification_min_length():
    ref = ElementRef(id="r1", kind="room", level_index=0)
    with pytest.raises(ValidationError):
        MutationEnvelope(
            agent_role="architect",
            operation="create",
            target_ref=ref,
            after={"x": 1},
            justification="short",
        )


def test_floorplan_snapshot_compact_mode_rejects_raw_arrays():
    with pytest.raises(ValidationError):
        FloorplanSnapshot(
            mode="compact",
            building_id="b",
            levels=(
                {  # type: ignore[arg-type]
                    "index": 0,
                    "name": "L0",
                    "elevation_m": 0.0,
                    "walls": (),
                },
            ),
        )


def test_protocol_report_summarize_helper():
    from archit_app.protocol import ProtocolCheck

    checks = (
        ProtocolCheck(code="x.a", passed=True, severity="info", message="ok"),
        ProtocolCheck(code="x.b", passed=False, severity="error", message="fail"),
        ProtocolCheck(code="x.c", passed=False, severity="warn", message="careful"),
    )
    summary = ProtocolReport.summarize(checks)
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.warnings == 1
