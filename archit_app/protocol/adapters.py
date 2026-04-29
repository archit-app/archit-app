"""Adapters: convert existing archit-app analysis results into ``ProtocolReport``.

These functions are pure — they do not import or modify the underlying
analysis modules.  Use them to bridge legacy dataclass/dict results into the
unified protocol shape that agents consume.
"""

from __future__ import annotations

from typing import Any, Iterable

from archit_app.protocol.report import (
    ProtocolCheck,
    ProtocolReport,
    Severity,
    Suggestion,
)
from archit_app.protocol.refs import ElementRef


def _room_ref(room_id: Any, level_index: int | None) -> ElementRef:
    return ElementRef(id=str(room_id), kind="room", level_index=level_index)


def _opening_ref(opening_id: Any, level_index: int | None) -> ElementRef:
    return ElementRef(id=str(opening_id), kind="opening", level_index=level_index)


def _element_ref(element_id: Any, level_index: int | None) -> ElementRef:
    return ElementRef(id=str(element_id), kind="opening", level_index=level_index)


def circulation_egress_to_report(
    egress: dict[str, Any],
    level_index: int | None,
) -> ProtocolReport:
    """Convert ``analysis.circulation.egress_report`` dict result into a ``ProtocolReport``."""
    checks: list[ProtocolCheck] = []
    suggestions: list[Suggestion] = []
    for entry in egress.get("rooms", ()):  # type: ignore[arg-type]
        compliant = bool(entry.get("compliant"))
        message = (
            entry.get("issue")
            or f"egress {entry.get('egress_distance_m', 'n/a')}m within limit"
        )
        metric: dict[str, float] = {}
        if entry.get("egress_distance_m") is not None:
            metric["egress_distance_m"] = float(entry["egress_distance_m"])
        checks.append(
            ProtocolCheck(
                code="egress.distance",
                target_ref=_room_ref(entry["room_id"], level_index),
                passed=compliant,
                severity="error" if not compliant else "info",
                message=message,
                metric=metric or None,
            )
        )
        fix = entry.get("suggested_fix") or ""
        if not compliant and fix:
            suggestions.append(Suggestion(description=fix))

    checks_t = tuple(checks)
    return ProtocolReport(
        kind="egress",
        level_index=level_index,
        checks=checks_t,
        summary=ProtocolReport.summarize(checks_t),
        suggestions=tuple(suggestions),
    )


def daylight_results_to_report(
    results: Iterable[Any],
    level_index: int | None,
) -> ProtocolReport:
    """Convert a list of ``RoomDaylightResult`` dataclasses into a ``ProtocolReport``."""
    checks: list[ProtocolCheck] = []
    suggestions: list[Suggestion] = []
    for r in results:
        compliant = bool(getattr(r, "compliant", True))
        message = getattr(r, "issue", "") or (
            f"WFR {getattr(r, 'window_to_floor_ratio', 0.0):.2f} meets minimum"
        )
        metric = {
            "window_to_floor_ratio": float(getattr(r, "window_to_floor_ratio", 0.0)),
            "window_area_m2": float(getattr(r, "window_area_m2", 0.0)),
            "floor_area_m2": float(getattr(r, "floor_area_m2", 0.0)),
            "avg_solar_score": float(getattr(r, "avg_solar_score", 0.0)),
        }
        checks.append(
            ProtocolCheck(
                code="daylight.window_to_floor_ratio",
                target_ref=_room_ref(getattr(r, "room_id"), level_index),
                passed=compliant,
                severity="error" if not compliant else "info",
                message=message,
                metric=metric,
            )
        )
        fix = getattr(r, "suggested_fix", "") or ""
        if not compliant and fix:
            suggestions.append(Suggestion(description=fix))
    checks_t = tuple(checks)
    return ProtocolReport(
        kind="daylighting",
        level_index=level_index,
        checks=checks_t,
        summary=ProtocolReport.summarize(checks_t),
        suggestions=tuple(suggestions),
    )


def accessibility_report_to_protocol(report: Any) -> ProtocolReport:
    """Convert an ``AccessibilityReport`` (Pydantic) into a ``ProtocolReport``."""
    level_index = getattr(report, "level_index", None)
    checks: list[ProtocolCheck] = []
    for chk in getattr(report, "checks", ()):  # AccessibilityCheck
        sev: Severity = "warn" if getattr(chk, "severity", "error") == "warning" else "error"
        target = None
        elem_id = getattr(chk, "element_id", None)
        if elem_id is not None:
            target = ElementRef(id=str(elem_id), kind="opening", level_index=level_index)
        checks.append(
            ProtocolCheck(
                code=f"accessibility.{getattr(chk, 'name', 'check').replace(' ', '_').lower()}",
                target_ref=target,
                passed=bool(getattr(chk, "passed", True)),
                severity=sev,
                message=str(getattr(chk, "detail", getattr(chk, "name", ""))),
            )
        )
    checks_t = tuple(checks)
    return ProtocolReport(
        kind="accessibility",
        level_index=level_index,
        checks=checks_t,
        summary=ProtocolReport.summarize(checks_t),
    )


def compliance_report_to_protocol(report: Any) -> ProtocolReport:
    """Convert a ``ComplianceReport`` (dataclass) into a ``ProtocolReport``."""
    checks: list[ProtocolCheck] = []
    for chk in getattr(report, "checks", ()):  # ComplianceCheck
        actual = getattr(chk, "actual", None)
        limit = getattr(chk, "limit", None)
        unit = getattr(chk, "unit", "")
        metric: dict[str, float] | None = None
        if isinstance(actual, (int, float)):
            metric = {"actual": float(actual)}
            if isinstance(limit, (int, float)):
                metric["limit"] = float(limit)
        message = f"{getattr(chk, 'name', '')}: {actual} {unit}"
        note = getattr(chk, "note", "")
        if note:
            message = f"{message} — {note}"
        checks.append(
            ProtocolCheck(
                code=f"compliance.{getattr(chk, 'name', 'check').replace(' ', '_').lower()}",
                passed=bool(getattr(chk, "compliant", True)),
                severity="error",
                message=message,
                metric=metric,
            )
        )
    checks_t = tuple(checks)
    return ProtocolReport(
        kind="compliance",
        checks=checks_t,
        summary=ProtocolReport.summarize(checks_t),
    )


def program_area_to_report(
    results: Iterable[Any],
    level_index: int | None = None,
) -> ProtocolReport:
    """Convert a list of ``ProgramAreaResult`` dataclasses into a ``ProtocolReport``."""
    checks: list[ProtocolCheck] = []
    for r in results:
        compliant = getattr(r, "compliant", None)
        program = getattr(r, "program", "")
        actual = float(getattr(r, "actual_m2", 0.0))
        target = getattr(r, "target_m2", None)
        deviation = getattr(r, "deviation_fraction", None)
        if compliant is None:
            severity: Severity = "info"
            passed = True
            message = f"{program}: actual {actual:.1f}m² (no target set)"
        else:
            passed = bool(compliant)
            severity = "error" if not passed else "info"
            target_str = f"{target:.1f}m²" if target is not None else "n/a"
            dev_str = f"{deviation * 100:.1f}%" if deviation is not None else "n/a"
            message = f"{program}: actual {actual:.1f}m² vs target {target_str} (Δ {dev_str})"
        metric = {"actual_m2": actual}
        if target is not None:
            metric["target_m2"] = float(target)
        if deviation is not None:
            metric["deviation_fraction"] = float(deviation)
        checks.append(
            ProtocolCheck(
                code=f"area.{program}".lower().replace(" ", "_") or "area.program",
                passed=passed,
                severity=severity,
                message=message,
                metric=metric,
            )
        )
    checks_t = tuple(checks)
    return ProtocolReport(
        kind="area",
        level_index=level_index,
        checks=checks_t,
        summary=ProtocolReport.summarize(checks_t),
    )
