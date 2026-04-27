"""
Daylighting and solar orientation analysis.

Estimates the solar exposure of each room on a level based on the orientation
of its adjacent windows. No optional dependencies required.

Methodology
-----------
For each room:
  1. Find all WINDOW openings on walls that are spatially adjacent to the room.
  2. For each window, derive the parent wall's normal direction from its polygon.
  3. Convert the normal to a compass bearing relative to geographic north.
  4. Compute a solar score using a cosine model:
       score = max(0, cos(angle_from_south_rad))
     This gives 1.0 for south-facing (max gain, northern hemisphere), 0.0 for
     east/west, and 0.0 for north-facing windows.

Limitations
-----------
- Only considers direct solar orientation, not shading from adjacent buildings.
- Uses the wall polygon's centre-line direction; valid for straight walls.
- "South" is determined from ``north_angle_deg`` (degrees clockwise from +Y
  to geographic north).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from uuid import UUID

import shapely.geometry

from archit_app.elements.opening import OpeningKind
from archit_app.geometry.polygon import Polygon2D

# Proximity threshold for linking a window to a room boundary (meters)
_WINDOW_ROOM_BUFFER_M = 0.5


@dataclass
class WindowSolarResult:
    """Solar result for a single window opening."""

    opening_id: UUID
    wall_normal_angle_deg: float    # math convention: 0=+X, 90=+Y
    compass_bearing_deg: float      # 0=N, 90=E, 180=S, 270=W
    cardinal: str                   # "N", "NE", "E", "SE", "S", "SW", "W", "NW"
    solar_score: float              # 0 (north) … 1 (south), northern hemisphere
    width_m: float


_MIN_WFR = 0.10  # minimum window-to-floor ratio per standard requirements


@dataclass
class RoomDaylightResult:
    """Daylighting result for a single room."""

    room_id: UUID
    room_name: str
    program: str
    floor_area_m2: float
    window_area_m2: float
    window_to_floor_ratio: float    # window area / floor area
    windows: list[WindowSolarResult] = field(default_factory=list)
    avg_solar_score: float = 0.0    # area-weighted mean solar score across windows
    compliant: bool = True          # True if WFR ≥ minimum standard
    issue: str = ""                 # human-readable description when non-compliant
    suggested_fix: str = ""         # actionable fix suggestion


def daylight_report(
    level,
    north_angle_deg: float = 0.0,
    window_room_buffer_m: float = _WINDOW_ROOM_BUFFER_M,
) -> list[RoomDaylightResult]:
    """
    Compute a daylighting report for every room on a level.

    Parameters
    ----------
    level : Level
        The floor to analyse.
    north_angle_deg : float
        Degrees clockwise from world +Y axis to geographic north.
        (0.0 means world +Y is true north.)
    window_room_buffer_m : float
        How close (in meters) a window centroid must be to a room boundary
        to be attributed to that room.

    Returns
    -------
    list[RoomDaylightResult]
        One entry per room, sorted by room name.
    """
    # Collect all (window, wall_normal_angle_deg, width) from level walls
    window_records: list[tuple[object, float, float, float, float]] = []
    for wall in level.walls:
        normal_angle = _wall_normal_angle_deg(wall)
        if normal_angle is None:
            continue
        for opening in wall.openings:
            if opening.kind != OpeningKind.WINDOW:
                continue
            c = opening.geometry.centroid
            window_records.append((opening, c.x, c.y, normal_angle, opening.width))

    # Build room shapes
    room_shapes = {room.id: room.boundary._to_shapely() for room in level.rooms}

    results: list[RoomDaylightResult] = []
    for room in sorted(level.rooms, key=lambda r: r.name):
        shape = room_shapes[room.id]

        matched_windows: list[WindowSolarResult] = []
        for opening, ox, oy, normal_deg, win_width in window_records:
            pt = shapely.geometry.Point(ox, oy)
            if shape.exterior.distance(pt) <= window_room_buffer_m:
                compass = _normal_to_compass(normal_deg, north_angle_deg)
                score = _solar_score(compass)
                cardinal = _compass_to_cardinal(compass)
                matched_windows.append(WindowSolarResult(
                    opening_id=opening.id,
                    wall_normal_angle_deg=round(normal_deg, 1),
                    compass_bearing_deg=round(compass, 1),
                    cardinal=cardinal,
                    solar_score=round(score, 3),
                    width_m=win_width,
                ))

        total_window_area = sum(w.width_m for w in matched_windows)  # width as proxy for area
        floor_area = room.area
        wfr = total_window_area / floor_area if floor_area > 0 else 0.0

        # Area-weighted solar score
        if matched_windows:
            total_width = sum(w.width_m for w in matched_windows)
            avg_score = (
                sum(w.solar_score * w.width_m for w in matched_windows) / total_width
                if total_width > 0 else 0.0
            )
        else:
            avg_score = 0.0

        compliant = wfr >= _MIN_WFR
        if not compliant:
            needed_m2 = round(_MIN_WFR * floor_area - total_window_area, 2)
            issue = (
                f"'{room.name or room.program}' WFR={wfr:.2%} is below the "
                f"{_MIN_WFR:.0%} minimum (needs {needed_m2}m² more window area)."
            )
            fix = (
                f"Add {needed_m2}m² of window area to an exterior wall of "
                f"'{room.name or room.program}'. Prefer south-facing walls for solar gain."
            )
        else:
            issue = ""
            fix = ""

        results.append(RoomDaylightResult(
            room_id=room.id,
            room_name=room.name,
            program=room.program,
            floor_area_m2=round(floor_area, 4),
            window_area_m2=round(total_window_area, 4),
            window_to_floor_ratio=round(wfr, 4),
            windows=matched_windows,
            avg_solar_score=round(avg_score, 3),
            compliant=compliant,
            issue=issue,
            suggested_fix=fix,
        ))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wall_normal_angle_deg(wall) -> float | None:
    """
    Compute the wall's left-hand normal angle in degrees (math convention).

    For a 4-vertex Polygon2D wall, the centreline runs from the midpoint of
    the start pair to the midpoint of the end pair. The left-hand normal is
    the direction perpendicular to this, rotated 90° CCW.

    Returns None for non-Polygon2D or non-rectangular walls.
    """
    if not isinstance(wall.geometry, Polygon2D):
        return None
    pts = wall.geometry.exterior
    if len(pts) != 4:
        return None

    sx = (pts[0].x + pts[3].x) / 2
    sy = (pts[0].y + pts[3].y) / 2
    ex = (pts[1].x + pts[2].x) / 2
    ey = (pts[1].y + pts[2].y) / 2

    dx, dy = ex - sx, ey - sy
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-10:
        return None

    # Left-hand normal (CCW 90°): (-dy, dx)
    nx, ny = -dy / length, dx / length
    return math.degrees(math.atan2(ny, nx)) % 360


def _normal_to_compass(normal_angle_deg: float, north_angle_deg: float) -> float:
    """
    Convert a math-convention angle (0=+X, 90=+Y) to a compass bearing
    (0=N, 90=E, 180=S, 270=W), accounting for the north rotation.

    north_angle_deg: degrees clockwise from world +Y to geographic north.
    """
    # In math convention, north direction = (90 - north_angle_deg)
    # Bearing = clockwise angle from north = (math_north_angle - normal_angle_deg)
    north_math = 90.0 - north_angle_deg
    bearing = (north_math - normal_angle_deg) % 360
    return bearing


def _solar_score(compass_bearing_deg: float) -> float:
    """
    Solar score for a surface with the given compass bearing (northern hemisphere).

    score = max(0, cos(angle_from_south))
    South (180°) → 1.0, East/West (90°/270°) → 0.0, North (0°/360°) → 0.0
    """
    # Simple: distance from 180° (south), no modular wrap needed for [0, 360]
    angle_from_south = abs(compass_bearing_deg - 180.0)
    return max(0.0, math.cos(math.radians(angle_from_south)))


def _compass_to_cardinal(bearing: float) -> str:
    cardinals = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((bearing + 22.5) / 45) % 8
    return cardinals[idx]
