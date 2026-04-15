"""
Area program validation.

Compares actual floor areas (by program type) against a design target and
reports deviations. No optional dependencies required — uses only core Shapely
and standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AreaTarget:
    """
    Design target for a single program type.

    program:            Program label (e.g. "bedroom", "office", "corridor").
    target_m2:          Target net area in m².
    tolerance_fraction: Acceptable deviation as a fraction of *target_m2*
                        (default 0.10 = ±10%). Both over and under count as
                        non-compliant.
    """

    program: str
    target_m2: float
    tolerance_fraction: float = 0.10


@dataclass
class ProgramAreaResult:
    """Result entry for a single program type."""

    program: str
    rooms: list = field(default_factory=list)  # list of Room objects
    actual_m2: float = 0.0
    target_m2: float | None = None
    deviation_fraction: float | None = None   # (actual - target) / target
    compliant: bool | None = None             # None when no target was given


def area_by_program(building) -> dict[str, float]:
    """
    Return total net floor area in m² for each program type across all levels.

    Parameters
    ----------
    building : Building

    Returns
    -------
    dict[str, float]
        ``{program: total_net_area_m2, ...}`` sorted by program name.
    """
    totals: dict[str, float] = {}
    for level in building.levels:
        for room in level.rooms:
            totals[room.program] = totals.get(room.program, 0.0) + room.area
    return dict(sorted(totals.items()))


def area_by_program_per_level(building) -> dict[int, dict[str, float]]:
    """
    Return net area per program type, broken down by level index.

    Returns
    -------
    dict[int, dict[str, float]]
        ``{level_index: {program: net_area_m2, ...}, ...}``
    """
    result: dict[int, dict[str, float]] = {}
    for level in building.levels:
        per_level: dict[str, float] = {}
        for room in level.rooms:
            per_level[room.program] = per_level.get(room.program, 0.0) + room.area
        result[level.index] = dict(sorted(per_level.items()))
    return result


def area_report(
    building,
    targets: list[AreaTarget],
) -> list[ProgramAreaResult]:
    """
    Compare actual areas by program type against design targets.

    Programs not mentioned in *targets* are still included in the output
    with ``target_m2=None`` and ``compliant=None``.

    Parameters
    ----------
    building : Building
        The building to analyse.
    targets : list[AreaTarget]
        Desired areas per program. Duplicate program labels are summed.

    Returns
    -------
    list[ProgramAreaResult]
        One entry per unique program found in the building, sorted by program.
    """
    # Collect rooms by program
    rooms_by_program: dict[str, list] = {}
    for level in building.levels:
        for room in level.rooms:
            rooms_by_program.setdefault(room.program, []).append(room)

    # Build target lookup (sum duplicates)
    target_map: dict[str, AreaTarget] = {}
    for t in targets:
        if t.program in target_map:
            existing = target_map[t.program]
            target_map[t.program] = AreaTarget(
                program=t.program,
                target_m2=existing.target_m2 + t.target_m2,
                tolerance_fraction=max(existing.tolerance_fraction, t.tolerance_fraction),
            )
        else:
            target_map[t.program] = t

    # Build results for all programs present in the building
    results: list[ProgramAreaResult] = []
    for program in sorted(rooms_by_program):
        rooms = rooms_by_program[program]
        actual = sum(r.area for r in rooms)
        t = target_map.get(program)

        if t is None:
            results.append(ProgramAreaResult(
                program=program,
                rooms=rooms,
                actual_m2=round(actual, 4),
            ))
        else:
            dev = (actual - t.target_m2) / t.target_m2 if t.target_m2 > 0 else None
            compliant = dev is not None and abs(dev) <= t.tolerance_fraction
            results.append(ProgramAreaResult(
                program=program,
                rooms=rooms,
                actual_m2=round(actual, 4),
                target_m2=t.target_m2,
                deviation_fraction=round(dev, 4) if dev is not None else None,
                compliant=compliant,
            ))

    # Include targets for programs not yet in the building
    for program, t in sorted(target_map.items()):
        if program not in rooms_by_program:
            results.append(ProgramAreaResult(
                program=program,
                rooms=[],
                actual_m2=0.0,
                target_m2=t.target_m2,
                deviation_fraction=-1.0,  # 100% deficit
                compliant=False,
            ))

    return sorted(results, key=lambda r: r.program)


def total_gross_area(building) -> float:
    """Total gross floor area across all levels in m²."""
    return sum(
        sum(r.gross_area for r in level.rooms)
        for level in building.levels
    )


def total_net_area(building) -> float:
    """Total net floor area (after subtracting room holes) across all levels in m²."""
    return sum(
        sum(r.area for r in level.rooms)
        for level in building.levels
    )
