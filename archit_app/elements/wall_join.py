"""
Wall joining utilities.

Provides miter and butt join operations for Wall pairs that share a corner
endpoint on their centrelines. These functions are pure — they return new
Wall instances and do not mutate the originals.

Only walls whose geometry is a Polygon2D (i.e. created with Wall.straight())
are currently supported. Curve-geometry walls return None unchanged.

Join types
----------
miter_join(wall_a, wall_b) → both walls clipped at the angle bisector plane.
butt_join(wall_a, wall_b)  → wall_b is trimmed to butt against wall_a's face;
                              wall_a is unchanged.
join_walls(walls)          → apply miter_join to all pairs that share an endpoint.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Sequence

from archit_app.elements.wall import Wall
from archit_app.geometry.polygon import Polygon2D

if TYPE_CHECKING:  # pragma: no cover - typing only
    import shapely.geometry  # noqa: F401


# Lazy shapely import so `import archit_app` doesn't pull shapely on cold paths.
_shapely_geom_module: Any = None


def _shapely_geom() -> Any:
    global _shapely_geom_module
    if _shapely_geom_module is None:
        import shapely.geometry as _sg

        _shapely_geom_module = _sg
    return _shapely_geom_module


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _centerline(wall: Wall) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """
    Extract (start, end) centreline endpoints from a box-polygon wall.

    A straight wall polygon has 4 vertices ordered:
      0: start-left, 1: end-left, 2: end-right, 3: start-right
    The centreline endpoints are midpoints of the start pair and end pair.

    Returns None for non-Polygon2D or non-rectangular geometries.
    """
    if not isinstance(wall.geometry, Polygon2D):
        return None
    pts = wall.geometry.exterior
    if len(pts) != 4:
        return None
    start = ((pts[0].x + pts[3].x) / 2, (pts[0].y + pts[3].y) / 2)
    end = ((pts[1].x + pts[2].x) / 2, (pts[1].y + pts[2].y) / 2)
    return start, end


def _shared_endpoint(
    wall_a: Wall,
    wall_b: Wall,
    tolerance: float,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]] | None:
    """
    Find a shared endpoint between the two walls' centrelines.

    Returns (shared_pt, dir_a_away, dir_b_away) where dir_x_away is the
    unit vector pointing from the shared point toward the other endpoint.
    Returns None if no endpoint is within tolerance.
    """
    cl_a = _centerline(wall_a)
    cl_b = _centerline(wall_b)
    if cl_a is None or cl_b is None:
        return None

    start_a, end_a = cl_a
    start_b, end_b = cl_b

    candidates = [
        (start_a, end_a, start_b, end_b),
        (start_a, end_a, end_b, start_b),
        (end_a, start_a, start_b, end_b),
        (end_a, start_a, end_b, start_b),
    ]

    for p_a, other_a, p_b, other_b in candidates:
        dx, dy = p_a[0] - p_b[0], p_a[1] - p_b[1]
        if math.sqrt(dx * dx + dy * dy) <= tolerance:
            shared = p_a
            da = (other_a[0] - shared[0], other_a[1] - shared[1])
            db = (other_b[0] - shared[0], other_b[1] - shared[1])
            mag_a = math.sqrt(da[0] ** 2 + da[1] ** 2)
            mag_b = math.sqrt(db[0] ** 2 + db[1] ** 2)
            if mag_a < 1e-10 or mag_b < 1e-10:
                continue
            return shared, (da[0] / mag_a, da[1] / mag_a), (db[0] / mag_b, db[1] / mag_b)

    return None


def _half_plane_polygon(
    px: float,
    py: float,
    nx: float,
    ny: float,
    big: float = 1e6,
) -> Any:
    """
    Return a large polygon covering the half-plane {x : (x-P)·n >= 0}.

    n = (nx, ny) is the inward normal of the clipping plane through P=(px,py).
    """
    shapely_geometry = _shapely_geom()
    tx, ty = -ny, nx          # tangent along the clip line
    return shapely_geometry.Polygon([
        (px + nx * big + tx * big, py + ny * big + ty * big),
        (px + nx * big - tx * big, py + ny * big - ty * big),
        (px - tx * big,            py - ty * big),
        (px + tx * big,            py + ty * big),
    ])


def _clip_wall_polygon(wall: Wall, clip: Any) -> Wall:
    """Intersect wall's Polygon2D geometry with a Shapely polygon and return a new Wall."""
    shapely_geometry = _shapely_geom()
    shp = wall.geometry._to_shapely()
    clipped = shp.intersection(clip)
    if clipped.is_empty or not isinstance(clipped, shapely_geometry.Polygon):
        return wall   # fallback: return original if result is degenerate
    new_geom = Polygon2D._from_shapely(clipped, wall.geometry.crs)
    return wall.model_copy(update={"geometry": new_geom})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def miter_join(
    wall_a: Wall,
    wall_b: Wall,
    tolerance: float = 0.01,
) -> tuple[Wall, Wall] | None:
    """
    Compute a miter join between two walls sharing a corner endpoint.

    Both walls are clipped at the angle-bisector plane through the shared
    point.  Each wall keeps the half that extends away from the corner.

    Returns (wall_a_trimmed, wall_b_trimmed) or None if:
    - no shared endpoint is found within *tolerance*, or
    - either wall uses non-Polygon2D geometry, or
    - the walls are anti-parallel (180° join — no trim needed).
    """
    result = _shared_endpoint(wall_a, wall_b, tolerance)
    if result is None:
        return None

    shared, dir_a, dir_b = result

    # Bisector: points into the open half that contains both wall bodies
    bx = dir_a[0] + dir_b[0]
    by = dir_a[1] + dir_b[1]
    mag = math.sqrt(bx * bx + by * by)
    if mag < 1e-10:
        return None   # anti-parallel walls — 180° join, nothing to trim

    bx, by = bx / mag, by / mag
    clip = _half_plane_polygon(shared[0], shared[1], bx, by)

    return _clip_wall_polygon(wall_a, clip), _clip_wall_polygon(wall_b, clip)


def butt_join(
    wall_a: Wall,
    wall_b: Wall,
    tolerance: float = 0.01,
) -> tuple[Wall, Wall] | None:
    """
    Compute a butt join: wall_b is trimmed to abut wall_a's face; wall_a is unchanged.

    The clip plane for wall_b is perpendicular to wall_b's centreline and
    passes through the shared endpoint — i.e. wall_b simply stops at the
    shared point rather than being mitered.

    Returns (wall_a, wall_b_trimmed) or None if no shared endpoint is found.
    """
    result = _shared_endpoint(wall_a, wall_b, tolerance)
    if result is None:
        return None

    shared, _dir_a, dir_b = result

    # Clip wall_b at the plane perpendicular to its own direction at the shared point
    clip = _half_plane_polygon(shared[0], shared[1], dir_b[0], dir_b[1])

    return wall_a, _clip_wall_polygon(wall_b, clip)


def join_walls(
    walls: Sequence[Wall],
    tolerance: float = 0.01,
) -> tuple[Wall, ...]:
    """
    Apply miter joins to all pairs of walls in *walls* that share a corner endpoint.

    Iterates over every unique pair; the first matching join found for each
    wall replaces it.  This is O(n²) — suitable for typical room-scale
    collections (tens of walls); not for very large building-scale sets.

    Returns a new tuple of walls with joins applied.
    """
    result = list(walls)
    n = len(result)

    for i in range(n):
        for j in range(i + 1, n):
            joined = miter_join(result[i], result[j], tolerance=tolerance)
            if joined is not None:
                result[i], result[j] = joined

    return tuple(result)
