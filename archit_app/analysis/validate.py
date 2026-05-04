"""
Structured building validation.

Runs a battery of geometric and topological checks against a Building and
returns a flat list of :class:`Finding` objects that the UI can render as a
checklist and the agents can act on.

Each check returns one or more ``Finding`` records carrying a stable ``code``
identifier (e.g. ``"orphan_wall"``, ``"room_overlap"``), a human-readable
``message``, and an optional ``fix_hint`` the agent can paste-act on.

Checks performed
----------------
* ``orphan_wall``        — walls not bordering any room on their level
* ``room_overlap``       — pair of rooms whose interiors intersect
* ``missing_perimeter``  — room with no walls along its boundary
* ``zero_length_wall``   — wall with zero or near-zero centre-line length
* ``orphan_opening``     — opening whose host wall is no longer on the level
* ``level_walls_no_rooms`` — level has walls but no rooms
* ``level_rooms_no_walls`` — level has rooms but no walls
* ``duplicate_wall``     — collinear walls with overlapping segments

Usage
-----
::

    from archit_app.analysis.validate import validate

    findings = validate(building)
    for f in findings:
        print(f.severity, f.code, f.message)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from archit_app.building.building import Building


# ---------------------------------------------------------------------------
# Constants / tolerances
# ---------------------------------------------------------------------------

_ZERO_LEN_TOL_M: float = 0.01           # walls shorter than 1 cm are zero-length
_ROOM_OVERLAP_TOL_M2: float = 0.01      # 100 cm² overlap counts as real
_PERIMETER_BUFFER_M: float = 0.35       # same default as Level.walls_for_room
_DUPLICATE_ANGLE_TOL_RAD: float = math.radians(2.0)
_DUPLICATE_PERP_TOL_M: float = 0.05     # 5 cm perpendicular distance
_DUPLICATE_OVERLAP_TOL_M: float = 0.05  # 5 cm collinear overlap


Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Finding:
    """A single structured validation finding.

    severity      one of ``"info"``, ``"warning"``, ``"error"``
    code          stable machine identifier (e.g. ``"orphan_wall"``)
    element_id    UUID-as-string of the offending element, if any
    level_index   level the finding applies to, if any
    message       human-readable description
    fix_hint      optional one-liner the agent (or user) can act on
    """

    severity: Severity
    code: str
    element_id: str | None
    level_index: int | None
    message: str
    fix_hint: str | None = None

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "element_id": self.element_id,
            "level_index": self.level_index,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(building: "Building") -> list[Finding]:
    """Run all structured checks against ``building`` and return the findings.

    The returned list is in declaration order (level by level, then by check
    family). Callers that want a deterministic order should sort by
    ``(level_index or -1, severity, code)``.
    """
    findings: list[Finding] = []

    for level in building.levels:
        findings.extend(_check_zero_length_walls(level))
        findings.extend(_check_orphan_openings(level))
        findings.extend(_check_level_balance(level))
        findings.extend(_check_room_overlaps(level))
        findings.extend(_check_orphan_walls(level))
        findings.extend(_check_missing_perimeter(level))
        findings.extend(_check_duplicate_walls(level))

    return findings


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_zero_length_walls(level) -> list[Finding]:
    """Walls whose centre line is zero or near-zero length."""
    out: list[Finding] = []
    for wall in level.walls:
        try:
            length = float(wall.length)
        except Exception:
            continue
        if length < _ZERO_LEN_TOL_M:
            out.append(Finding(
                severity="error",
                code="zero_length_wall",
                element_id=str(wall.id),
                level_index=level.index,
                message=(
                    f"Wall {str(wall.id)[:8]} on level {level.index} has near-zero "
                    f"length ({length:.4f} m)."
                ),
                fix_hint=(
                    "Remove the wall and re-add it with distinct start/end "
                    "endpoints (>= 0.01 m apart)."
                ),
            ))
    return out


def _check_orphan_openings(level) -> list[Finding]:
    """Openings on the level whose host wall is no longer present.

    Only matters for openings stored directly on the level (``level.openings``).
    Openings nested inside ``Wall.openings`` are intrinsically attached.
    """
    out: list[Finding] = []
    wall_ids = {w.id for w in level.walls}
    for op in level.openings:
        host = getattr(op, "host_wall_id", None) or getattr(op, "wall_id", None)
        if host is None:
            continue
        if host in wall_ids:
            continue
        out.append(Finding(
            severity="error",
            code="orphan_opening",
            element_id=str(op.id),
            level_index=level.index,
            message=(
                f"Opening {str(op.id)[:8]} on level {level.index} references "
                f"host wall {str(host)[:8]} which no longer exists."
            ),
            fix_hint=(
                "Either remove the opening or re-attach it to an existing wall "
                "via add_opening_to_wall."
            ),
        ))
    return out


def _check_level_balance(level) -> list[Finding]:
    """Level has rooms but no walls (or vice versa)."""
    out: list[Finding] = []
    if level.walls and not level.rooms:
        out.append(Finding(
            severity="warning",
            code="level_walls_no_rooms",
            element_id=None,
            level_index=level.index,
            message=(
                f"Level {level.index} has {len(level.walls)} wall(s) but no rooms."
            ),
            fix_hint=(
                "Add rooms with add_rooms_batch so wall placement has spatial "
                "context, or remove the orphan walls."
            ),
        ))
    if level.rooms and not level.walls:
        out.append(Finding(
            severity="warning",
            code="level_rooms_no_walls",
            element_id=None,
            level_index=level.index,
            message=(
                f"Level {level.index} has {len(level.rooms)} room(s) but no walls."
            ),
            fix_hint=(
                "Use add_walls_batch to enclose each room's perimeter — a room "
                "without walls cannot host openings or be exported correctly."
            ),
        ))
    return out


def _check_room_overlaps(level) -> list[Finding]:
    """Pairs of rooms whose interiors intersect by more than the tolerance."""
    out: list[Finding] = []
    rooms = list(level.rooms)
    if len(rooms) < 2:
        return out

    # Pre-compute Shapely polygons once per room.
    polys = []
    for room in rooms:
        try:
            polys.append(room.boundary._to_shapely())
        except Exception:
            polys.append(None)

    for i in range(len(rooms)):
        if polys[i] is None:
            continue
        for j in range(i + 1, len(rooms)):
            if polys[j] is None:
                continue
            try:
                overlap = polys[i].intersection(polys[j]).area
            except Exception:
                continue
            if overlap <= _ROOM_OVERLAP_TOL_M2:
                continue
            ra, rb = rooms[i], rooms[j]
            out.append(Finding(
                severity="error",
                code="room_overlap",
                element_id=str(ra.id),
                level_index=level.index,
                message=(
                    f"Rooms '{ra.name or ra.program or str(ra.id)[:8]}' and "
                    f"'{rb.name or rb.program or str(rb.id)[:8]}' on level "
                    f"{level.index} overlap by {overlap:.3f} m²."
                ),
                fix_hint=(
                    "Edit one room's boundary_points to remove the overlap, or "
                    "merge the two rooms if they should be one space."
                ),
            ))
    return out


def _check_orphan_walls(level) -> list[Finding]:
    """Walls whose bounding box does not touch any room (expanded by tolerance).

    Mirrors the buffered-intersection logic used by ``Level.walls_for_room`` so
    the two checks agree on what 'bordering a room' means.
    """
    out: list[Finding] = []
    if not level.walls or not level.rooms:
        return out

    try:
        from shapely.geometry import box as shp_box
        from shapely.geometry import Polygon as ShpPolygon
        from shapely.ops import unary_union
    except ImportError:
        return out

    # Build one buffered union of all room boundaries on the level.
    room_shapes = []
    for room in level.rooms:
        try:
            pts = room.boundary.exterior
            poly = ShpPolygon([(p.x, p.y) for p in pts])
            if poly.is_valid and poly.area > 0:
                room_shapes.append(poly)
        except Exception:
            continue
    if not room_shapes:
        return out
    try:
        envelope = unary_union(room_shapes).buffer(_PERIMETER_BUFFER_M)
    except Exception:
        return out

    for wall in level.walls:
        bb = wall.bounding_box()
        if bb is None:
            continue
        wall_box = shp_box(
            bb.min_corner.x, bb.min_corner.y,
            bb.max_corner.x, bb.max_corner.y,
        )
        try:
            if envelope.intersects(wall_box):
                continue
        except Exception:
            continue
        out.append(Finding(
            severity="warning",
            code="orphan_wall",
            element_id=str(wall.id),
            level_index=level.index,
            message=(
                f"Wall {str(wall.id)[:8]} on level {level.index} does not border "
                f"any room (>{_PERIMETER_BUFFER_M:.2f} m from every room boundary)."
            ),
            fix_hint=(
                "Remove the wall or move it onto a room boundary — orphan walls "
                "won't be matched by walls_for_room and can't host openings."
            ),
        ))
    return out


def _check_missing_perimeter(level) -> list[Finding]:
    """Rooms with no walls along their boundary.

    Uses :meth:`Level.walls_for_room` so the definition of 'a wall on the
    boundary' stays consistent with how the rest of the codebase resolves it.
    """
    out: list[Finding] = []
    if not level.rooms or not level.walls:
        return out

    for room in level.rooms:
        try:
            walls = level.walls_for_room(room.id, tolerance_m=_PERIMETER_BUFFER_M)
        except (KeyError, ImportError):
            continue
        except Exception:
            continue
        if walls:
            continue
        out.append(Finding(
            severity="error",
            code="missing_perimeter",
            element_id=str(room.id),
            level_index=level.index,
            message=(
                f"Room '{room.name or room.program or str(room.id)[:8]}' on "
                f"level {level.index} has no enclosing walls."
            ),
            fix_hint=(
                "Use add_walls_batch with the room's boundary_points to enclose "
                "it before placing openings or running compliance checks."
            ),
        ))
    return out


def _check_duplicate_walls(level) -> list[Finding]:
    """Pairs of walls that are collinear and overlap along the same line.

    Compares straight (polygon-based) walls only — curved walls are skipped.
    A pair is flagged when:

    * direction vectors are parallel within ``_DUPLICATE_ANGLE_TOL_RAD``,
    * perpendicular distance between centre lines is within
      ``_DUPLICATE_PERP_TOL_M``, and
    * the projected segments overlap by more than ``_DUPLICATE_OVERLAP_TOL_M``.
    """
    out: list[Finding] = []
    walls = list(level.walls)
    if len(walls) < 2:
        return out

    segments: list[tuple] = []
    for w in walls:
        sp = getattr(w, "start_point", None)
        ep = getattr(w, "end_point", None)
        if sp is None or ep is None:
            segments.append(None)
            continue
        dx, dy = ep[0] - sp[0], ep[1] - sp[1]
        length = math.hypot(dx, dy)
        if length < _ZERO_LEN_TOL_M:
            segments.append(None)
            continue
        ux, uy = dx / length, dy / length
        segments.append((sp, ep, ux, uy, length))

    seen: set[tuple[int, int]] = set()
    for i in range(len(walls)):
        seg_i = segments[i]
        if seg_i is None:
            continue
        sp_i, ep_i, ux_i, uy_i, len_i = seg_i
        for j in range(i + 1, len(walls)):
            seg_j = segments[j]
            if seg_j is None:
                continue
            sp_j, ep_j, ux_j, uy_j, _ = seg_j

            # Parallelism: |cross product of unit vectors| ~ sin(theta)
            cross = abs(ux_i * uy_j - uy_i * ux_j)
            if cross > math.sin(_DUPLICATE_ANGLE_TOL_RAD):
                continue

            # Perpendicular distance from sp_j to wall i's centre line.
            wx, wy = sp_j[0] - sp_i[0], sp_j[1] - sp_i[1]
            perp = abs(wx * (-uy_i) + wy * ux_i)
            if perp > _DUPLICATE_PERP_TOL_M:
                continue

            # Project both endpoints of j onto wall i's centre line and check
            # overlap with [0, len_i].
            t0 = wx * ux_i + wy * uy_i
            ex, ey = ep_j[0] - sp_i[0], ep_j[1] - sp_i[1]
            t1 = ex * ux_i + ey * uy_i
            lo, hi = (t0, t1) if t0 <= t1 else (t1, t0)
            overlap = min(hi, len_i) - max(lo, 0.0)
            if overlap <= _DUPLICATE_OVERLAP_TOL_M:
                continue

            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            wa, wb = walls[i], walls[j]
            out.append(Finding(
                severity="warning",
                code="duplicate_wall",
                element_id=str(wa.id),
                level_index=level.index,
                message=(
                    f"Walls {str(wa.id)[:8]} and {str(wb.id)[:8]} on level "
                    f"{level.index} are collinear and overlap by ~{overlap:.2f} m."
                ),
                fix_hint=(
                    "Delete one of the duplicate walls, or trim them so the "
                    "shared segment is covered exactly once."
                ),
            ))
    return out
