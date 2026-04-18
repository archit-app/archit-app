"""
Accessibility analysis.

Checks a Level for common accessibility requirements:

* Minimum door clear width (0.85 m default — ADA / BS 8300)
* Minimum corridor clear width (1.2 m default)
* Maximum ramp slope (1:12 ≈ 4.76° — ADA)
* Wheelchair turning circle fits in wet rooms (0.9 m radius)

All checks are non-destructive and return an ``AccessibilityReport``.

Usage::

    from archit_app.analysis.accessibility import check_accessibility

    report = check_accessibility(level)
    if not report.passed_all:
        for f in report.failures:
            print(f.detail)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from archit_app.building.level import Level


# ---------------------------------------------------------------------------
# Thresholds (all in SI units)
# ---------------------------------------------------------------------------

MIN_DOOR_WIDTH_M: float = 0.85       # ADA / BS 8300 minimum clear door width
MIN_CORRIDOR_WIDTH_M: float = 1.20   # minimum corridor clear width
MAX_RAMP_SLOPE_RAD: float = math.atan(1 / 12)  # 1:12 gradient ≈ 4.76°
WHEELCHAIR_RADIUS_M: float = 0.90    # turning circle radius

WET_ROOM_PROGRAMS = frozenset({"bathroom", "toilet", "wc", "ensuite",
                                "wet_room", "shower", "shower_room"})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AccessibilityCheck(BaseModel):
    """Result of a single accessibility check."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    detail: str
    severity: str = "error"       # "error" | "warning"
    element_id: UUID | None = None


class AccessibilityReport(BaseModel):
    """Aggregated accessibility report for one Level."""

    model_config = ConfigDict(frozen=True)

    level_index: int
    checks: tuple[AccessibilityCheck, ...] = ()

    @property
    def passed_all(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def failures(self) -> list[AccessibilityCheck]:
        return [c for c in self.checks if not c.passed]

    @property
    def errors(self) -> list[AccessibilityCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[AccessibilityCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    def summary(self) -> str:
        status = "PASS" if self.passed_all else "FAIL"
        lines = [f"Accessibility report — level {self.level_index} — {status}"]
        for c in self.checks:
            mark = "✓" if c.passed else ("✗" if c.severity == "error" else "⚠")
            lines.append(f"  [{mark}] {c.detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def _check_door_widths(
    level: "Level",
    min_width: float,
) -> list[AccessibilityCheck]:
    checks = []
    # Check openings attached to walls
    all_openings = list(level.openings)
    for wall in level.walls:
        all_openings.extend(wall.openings)

    from archit_app.elements.opening import OpeningKind
    for op in all_openings:
        if op.kind not in (OpeningKind.DOOR, OpeningKind.ARCHWAY):
            continue
        passed = op.width >= min_width
        checks.append(AccessibilityCheck(
            name="door_clear_width",
            passed=passed,
            severity="error",
            detail=(
                f"Door {str(op.id)[:8]}: clear width {op.width:.3f} m "
                f"{'≥' if passed else '<'} {min_width:.2f} m minimum."
            ),
            element_id=op.id,
        ))
    return checks


def _check_ramp_slopes(
    level: "Level",
    max_slope_rad: float,
) -> list[AccessibilityCheck]:
    checks = []
    for ramp in level.ramps:
        passed = ramp.slope_angle <= max_slope_rad
        slope_ratio = math.tan(ramp.slope_angle)
        checks.append(AccessibilityCheck(
            name="ramp_slope",
            passed=passed,
            severity="error",
            detail=(
                f"Ramp {str(ramp.id)[:8]}: slope 1:{1/slope_ratio:.1f} "
                f"({'≤' if passed else '>'} 1:12 maximum)."
            ),
            element_id=ramp.id,
        ))
    return checks


def _check_wet_room_turning_circle(
    level: "Level",
    radius: float,
) -> list[AccessibilityCheck]:
    """Check that wet rooms have enough floor area for a wheelchair turning circle."""
    import math
    min_area = math.pi * radius ** 2
    checks = []
    for room in level.rooms:
        if room.program.lower() not in WET_ROOM_PROGRAMS:
            continue
        passed = room.area >= min_area
        checks.append(AccessibilityCheck(
            name="wet_room_turning_circle",
            passed=passed,
            severity="warning",
            detail=(
                f"Room '{room.name or room.program}' {str(room.id)[:8]}: "
                f"area {room.area:.2f} m² "
                f"{'≥' if passed else '<'} {min_area:.2f} m² needed for "
                f"{radius:.2f} m turning radius."
            ),
            element_id=room.id,
        ))
    return checks


def _check_corridor_widths(
    level: "Level",
    min_width: float,
) -> list[AccessibilityCheck]:
    """
    Estimate corridor width from rooms with corridor-type programs.

    Uses the shorter bounding-box dimension as a proxy for clear width.
    """
    CORRIDOR_PROGRAMS = frozenset({"corridor", "hallway", "hall",
                                   "lobby", "circulation", "passage"})
    checks = []
    for room in level.rooms:
        if room.program.lower() not in CORRIDOR_PROGRAMS:
            continue
        bb = room.bounding_box()
        if bb is None:
            continue
        clear_width = min(bb.width, bb.height)
        passed = clear_width >= min_width
        checks.append(AccessibilityCheck(
            name="corridor_width",
            passed=passed,
            severity="error",
            detail=(
                f"Corridor '{room.name or room.program}' {str(room.id)[:8]}: "
                f"estimated clear width {clear_width:.3f} m "
                f"({'≥' if passed else '<'} {min_width:.2f} m minimum)."
            ),
            element_id=room.id,
        ))
    return checks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_accessibility(
    level: "Level",
    *,
    min_door_width_m: float = MIN_DOOR_WIDTH_M,
    min_corridor_width_m: float = MIN_CORRIDOR_WIDTH_M,
    max_ramp_slope_rad: float = MAX_RAMP_SLOPE_RAD,
    wheelchair_radius_m: float = WHEELCHAIR_RADIUS_M,
) -> AccessibilityReport:
    """
    Run all accessibility checks on ``level``.

    Parameters
    ----------
    level:
        The floor to analyse.
    min_door_width_m:
        Minimum clear door width in meters (default 0.85).
    min_corridor_width_m:
        Minimum corridor clear width in meters (default 1.2).
    max_ramp_slope_rad:
        Maximum ramp slope in radians (default atan(1/12) ≈ 4.76°).
    wheelchair_radius_m:
        Turning-circle radius for wet-room checks in meters (default 0.9).

    Returns
    -------
    AccessibilityReport
        Contains one ``AccessibilityCheck`` per element inspected.
    """
    all_checks: list[AccessibilityCheck] = []
    all_checks.extend(_check_door_widths(level, min_door_width_m))
    all_checks.extend(_check_ramp_slopes(level, max_ramp_slope_rad))
    all_checks.extend(_check_wet_room_turning_circle(level, wheelchair_radius_m))
    all_checks.extend(_check_corridor_widths(level, min_corridor_width_m))

    return AccessibilityReport(
        level_index=level.index,
        checks=tuple(all_checks),
    )
