"""
Visibility (isovist) analysis.

Computes the region visible from a viewpoint inside a level, accounting for
walls as opaque obstacles. The result is a Polygon2D representing the
"visibility polygon" or isovist.

Algorithm
---------
Ray-casting with configurable angular resolution:
  1. Build the union of all wall polygons on the level as obstacle geometry.
  2. For each of *resolution* evenly-spaced angles, cast a ray from the
     viewpoint to *max_range* meters.
  3. Clip each ray at its first intersection with any obstacle.
  4. Connect the clipped ray endpoints to form the isovist polygon.

No optional dependencies required (uses core Shapely).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

import shapely.geometry
import shapely.ops

from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


@dataclass
class IsovistResult:
    """Result of a single isovist computation."""

    viewpoint: Point2D
    isovist: Polygon2D          # visibility polygon
    area_m2: float              # visible area in m²
    max_range_m: float          # ray cast distance used
    resolution: int             # number of rays cast
    room_id: UUID | None        # room the viewpoint was found in (or None)


def compute_isovist(
    viewpoint: Point2D,
    level,
    resolution: int = 360,
    max_range: float = 50.0,
) -> IsovistResult | None:
    """
    Compute the visibility polygon (isovist) from *viewpoint*.

    Parameters
    ----------
    viewpoint : Point2D
        Observer position in world space.
    level : Level
        The floor containing the walls to treat as obstacles.
    resolution : int
        Number of rays to cast (angular precision = 360/resolution degrees).
        Higher values give smoother results; 360 is a good default.
    max_range : float
        Maximum ray length in meters (default 50 m).

    Returns
    -------
    IsovistResult | None
        None if there are no wall obstacles to cast against (the level is
        empty). The isovist polygon is clipped to *max_range* in all
        directions from the viewpoint.
    """
    vx, vy = viewpoint.x, viewpoint.y
    vp_shape = shapely.geometry.Point(vx, vy)

    # ---- build obstacle geometry --------------------------------------------
    obstacle = _build_obstacle(level)

    # ---- find which room the viewpoint is in --------------------------------
    room_id: UUID | None = None
    for room in level.rooms:
        if room.boundary._to_shapely().contains(vp_shape):
            room_id = room.id
            break

    # ---- ray casting --------------------------------------------------------
    angles = [2 * math.pi * i / resolution for i in range(resolution)]
    isovist_pts: list[tuple[float, float]] = []

    for angle in angles:
        dx = math.cos(angle) * max_range
        dy = math.sin(angle) * max_range
        ray = shapely.geometry.LineString([(vx, vy), (vx + dx, vy + dy)])

        if obstacle is not None and not obstacle.is_empty:
            hit = ray.intersection(obstacle)
            if hit.is_empty:
                isovist_pts.append((vx + dx, vy + dy))
            else:
                # Nearest point on the hit geometry to the viewpoint
                _, near = shapely.ops.nearest_points(vp_shape, hit)
                isovist_pts.append((near.x, near.y))
        else:
            isovist_pts.append((vx + dx, vy + dy))

    if len(isovist_pts) < 3:
        return None

    # ---- build and (if needed) repair the polygon ---------------------------
    poly = shapely.geometry.Polygon(isovist_pts)
    if not poly.is_valid:
        poly = poly.buffer(0)  # standard Shapely self-intersection fix
    if poly.is_empty or not isinstance(poly, shapely.geometry.Polygon):
        return None

    isovist_poly = Polygon2D._from_shapely(poly, viewpoint.crs)

    return IsovistResult(
        viewpoint=viewpoint,
        isovist=isovist_poly,
        area_m2=round(isovist_poly.area, 4),
        max_range_m=max_range,
        resolution=resolution,
        room_id=room_id,
    )


def visible_area_m2(viewpoint: Point2D, level, **kwargs) -> float:
    """
    Convenience wrapper — return visible area in m² from *viewpoint*.

    Returns 0.0 if the computation fails (empty level, degenerate geometry).
    """
    result = compute_isovist(viewpoint, level, **kwargs)
    return result.area_m2 if result is not None else 0.0


def mutual_visibility(
    point_a: Point2D,
    point_b: Point2D,
    level,
) -> bool:
    """
    Return True if *point_a* and *point_b* have an unobstructed line of sight
    on the given level (no wall polygon intersects the direct line between them).
    """
    obstacle = _build_obstacle(level)
    if obstacle is None or obstacle.is_empty:
        return True
    line = shapely.geometry.LineString([
        (point_a.x, point_a.y),
        (point_b.x, point_b.y),
    ])
    interior_intersection = line.difference(
        shapely.geometry.MultiPoint([(point_a.x, point_a.y), (point_b.x, point_b.y)])
    ).intersection(obstacle)
    return interior_intersection.is_empty


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_obstacle(level) -> shapely.geometry.base.BaseGeometry | None:
    """Union of all wall polygons on the level."""
    wall_polys = [
        w.geometry._to_shapely()
        for w in level.walls
        if isinstance(w.geometry, Polygon2D)
    ]
    if not wall_polys:
        return None
    result = wall_polys[0]
    for p in wall_polys[1:]:
        result = result.union(p)
    return result
