"""
Zoning compliance checker.

Compares a Building against its Land's ZoningInfo and produces a structured
report of pass/fail checks. No optional dependencies required.

Checks performed (when zoning data is available)
-------------------------------------------------
1. Floor Area Ratio (FAR)    — total_gross_area / lot_area ≤ max_far
2. Lot coverage              — ground_footprint_area / lot_area ≤ max_lot_coverage
3. Building height           — highest occupied elevation ≤ max_height_m
4. Footprint within lot      — ground floor rooms sit inside lot boundary
5. Footprint within setbacks — ground floor rooms sit inside buildable envelope
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ComplianceCheck:
    """A single pass/fail check with context."""

    name: str
    actual: float | str
    limit: float | str | None
    unit: str
    compliant: bool
    note: str = ""

    def __str__(self) -> str:
        status = "PASS" if self.compliant else "FAIL"
        lim = f" (limit: {self.limit} {self.unit})" if self.limit is not None else ""
        return f"[{status}] {self.name}: {self.actual} {self.unit}{lim}"


@dataclass
class ComplianceReport:
    """Full compliance report for a building against its land."""

    checks: list[ComplianceCheck] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        """True only if every check passes."""
        return all(c.compliant for c in self.checks)

    @property
    def failed_checks(self) -> list[ComplianceCheck]:
        return [c for c in self.checks if not c.compliant]

    def summary(self) -> str:
        lines = [f"Compliance report — {'PASS' if self.compliant else 'FAIL'}"]
        for check in self.checks:
            lines.append(f"  {check}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"ComplianceReport(checks={len(self.checks)}, "
            f"failed={len(self.failed_checks)}, "
            f"compliant={self.compliant})"
        )


def check_compliance(building, land) -> ComplianceReport:
    """
    Check a Building against its Land's zoning regulations.

    The building does not need to be attached to the land (i.e., you can pass
    any building and any land). If the land has no ``ZoningInfo``, only the
    geometric checks (footprint within lot/setbacks) are performed.

    Parameters
    ----------
    building : Building
    land : Land

    Returns
    -------
    ComplianceReport
    """
    report = ComplianceReport()
    zoning = land.zoning
    lot_area = land.area_m2 or 0.0

    # ---- 1. Total gross floor area & FAR -----------------------------------
    total_gfa = sum(
        sum(r.gross_area for r in level.rooms)
        for level in building.levels
    )
    actual_far = total_gfa / lot_area if lot_area > 0 else 0.0

    if zoning is not None and zoning.max_far is not None:
        report.checks.append(ComplianceCheck(
            name="Floor Area Ratio (FAR)",
            actual=round(actual_far, 3),
            limit=zoning.max_far,
            unit="",
            compliant=actual_far <= zoning.max_far,
            note=f"Total GFA {total_gfa:.1f} m² / lot {lot_area:.1f} m²",
        ))

    # ---- 2. Lot coverage ----------------------------------------------------
    ground_footprint = _building_footprint(building)
    footprint_area = ground_footprint.area if ground_footprint is not None else 0.0
    coverage = footprint_area / lot_area if lot_area > 0 else 0.0

    if zoning is not None and zoning.max_lot_coverage is not None:
        report.checks.append(ComplianceCheck(
            name="Lot coverage",
            actual=round(coverage, 4),
            limit=zoning.max_lot_coverage,
            unit="fraction",
            compliant=coverage <= zoning.max_lot_coverage,
            note=f"Ground footprint {footprint_area:.1f} m² / lot {lot_area:.1f} m²",
        ))

    # ---- 3. Building height -------------------------------------------------
    actual_height = _building_height(building)

    if zoning is not None and zoning.max_height_m is not None:
        report.checks.append(ComplianceCheck(
            name="Building height",
            actual=round(actual_height, 2),
            limit=zoning.max_height_m,
            unit="m",
            compliant=actual_height <= zoning.max_height_m,
        ))

    # ---- 4. Footprint within lot boundary -----------------------------------
    if ground_footprint is not None and land.boundary is not None:
        lot_shape = land.boundary._to_shapely()
        within_lot = ground_footprint.within(lot_shape.buffer(0.01))  # 1 cm tolerance
        report.checks.append(ComplianceCheck(
            name="Footprint within lot boundary",
            actual="yes" if within_lot else "no",
            limit="yes",
            unit="",
            compliant=within_lot,
        ))

        # ---- 5. Footprint within buildable envelope (setbacks) --------------
        buildable = land.buildable_boundary
        if buildable is not None:
            buildable_shape = buildable._to_shapely()
            within_setbacks = ground_footprint.within(buildable_shape.buffer(0.01))
            max_sb = land.setbacks.max_setback
            report.checks.append(ComplianceCheck(
                name="Footprint within setback envelope",
                actual="yes" if within_setbacks else "no",
                limit="yes",
                unit="",
                compliant=within_setbacks,
                note=f"Max setback {max_sb:.1f} m applied as uniform buffer",
            ))

    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _building_footprint(building):
    """
    Return the union of all room boundaries on the ground level (index 0) as
    a Shapely geometry, or None if no rooms exist on the ground floor.
    """
    ground = building.get_level(0)
    if ground is None or not ground.rooms:
        # Fall back to the lowest available level
        if not building.levels:
            return None
        ground = sorted(building.levels, key=lambda lv: lv.index)[0]
    if not ground.rooms:
        return None

    polys = [room.boundary._to_shapely() for room in ground.rooms]
    union = polys[0]
    for p in polys[1:]:
        union = union.union(p)
    return union


def _building_height(building) -> float:
    """
    Return the highest elevation reached by any level's top face in meters.

    height = max(level.elevation + level.floor_height)
    """
    if not building.levels:
        return 0.0
    return max(lv.elevation + lv.floor_height for lv in building.levels)
