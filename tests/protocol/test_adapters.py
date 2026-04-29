"""Adapter parity tests — each legacy result type maps cleanly to a ProtocolReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from archit_app.protocol import (
    ProtocolReport,
    accessibility_report_to_protocol,
    circulation_egress_to_report,
    compliance_report_to_protocol,
    daylight_results_to_report,
    program_area_to_report,
)


def test_circulation_egress_adapter_counts_correctly():
    egress = {
        "overall_compliant": False,
        "max_distance_m": 30.0,
        "exit_count": 1,
        "rooms": [
            {
                "room_id": str(uuid4()),
                "room_name": "Lobby",
                "program": "lobby",
                "egress_distance_m": 0.0,
                "compliant": True,
                "is_exit": True,
                "issue": "",
                "suggested_fix": "",
            },
            {
                "room_id": str(uuid4()),
                "room_name": "Bedroom",
                "program": "bedroom",
                "egress_distance_m": 42.0,
                "compliant": False,
                "is_exit": False,
                "issue": "exceeds 30m",
                "suggested_fix": "add a door closer to the lobby",
            },
        ],
    }
    rep = circulation_egress_to_report(egress, level_index=0)
    assert isinstance(rep, ProtocolReport)
    assert rep.kind == "egress"
    assert rep.summary.passed == 1
    assert rep.summary.failed == 1
    assert any("door" in s.description for s in rep.suggestions)


def test_daylight_adapter():
    @dataclass
    class FakeDaylight:
        room_id: str = field(default_factory=lambda: str(uuid4()))
        room_name: str = "Bedroom"
        program: str = "bedroom"
        floor_area_m2: float = 12.0
        window_area_m2: float = 0.5
        window_to_floor_ratio: float = 0.04
        windows: list = field(default_factory=list)
        avg_solar_score: float = 0.3
        compliant: bool = False
        issue: str = "low WFR"
        suggested_fix: str = "add a window"

    rep = daylight_results_to_report([FakeDaylight()], level_index=0)
    assert rep.kind == "daylighting"
    assert rep.summary.failed == 1
    assert rep.checks[0].metric is not None
    assert rep.checks[0].metric["window_to_floor_ratio"] == 0.04


def test_accessibility_adapter_severity_mapping():
    from archit_app.analysis.accessibility import AccessibilityCheck, AccessibilityReport

    chk_err = AccessibilityCheck(name="Door width", passed=False, detail="too narrow", severity="error")
    chk_warn = AccessibilityCheck(name="Corridor", passed=False, detail="tight", severity="warning")
    rep = accessibility_report_to_protocol(
        AccessibilityReport(level_index=1, checks=(chk_err, chk_warn))
    )
    assert rep.kind == "accessibility"
    assert rep.level_index == 1
    severities = {c.severity for c in rep.checks}
    assert severities == {"error", "warn"}


def test_compliance_adapter():
    from archit_app.analysis.compliance import ComplianceCheck, ComplianceReport

    rep_in = ComplianceReport(checks=[
        ComplianceCheck(name="FAR", actual=2.5, limit=3.0, unit="ratio", compliant=True),
        ComplianceCheck(name="Height", actual=20.0, limit=15.0, unit="m", compliant=False, note="too tall"),
    ])
    rep = compliance_report_to_protocol(rep_in)
    assert rep.kind == "compliance"
    assert rep.summary.passed == 1
    assert rep.summary.failed == 1


def test_area_adapter_handles_missing_target():
    @dataclass
    class FakeAreaResult:
        program: str
        rooms: list = field(default_factory=list)
        actual_m2: float = 0.0
        target_m2: float | None = None
        deviation_fraction: float | None = None
        compliant: bool | None = None

    rep = program_area_to_report([
        FakeAreaResult(program="kitchen", actual_m2=12.0),
        FakeAreaResult(program="bedroom", actual_m2=10.0, target_m2=12.0, deviation_fraction=-0.16, compliant=False),
    ])
    assert rep.kind == "area"
    assert rep.summary.passed == 1  # the no-target one is "info/passed"
    assert rep.summary.failed == 1
