"""
Room-from-walls auto-detection.

Given a collection of Wall elements, detect the enclosed polygon regions
they form and return them as Room or Polygon2D objects.

This is particularly useful when importing DXF files that contain only
wall geometry — the importer gives you walls, and this module finds rooms.

Uses Shapely's ``polygonize`` function on the wall centre-lines / outlines.

Usage::

    from archit_app.analysis.roomfinder import find_rooms, rooms_from_walls

    # Low-level: returns Polygon2D objects
    polygons = find_rooms(level.walls, min_area=1.0)

    # High-level: returns Room elements ready to add to the level
    rooms = rooms_from_walls(level.walls, level_index=0, program="unknown")
    for room in rooms:
        level = level.add_room(room)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archit_app.elements.room import Room
    from archit_app.elements.wall import Wall
    from archit_app.geometry.polygon import Polygon2D


def _wall_to_shapely(wall: "Wall"):
    """Convert a wall's geometry to a Shapely geometry for polygonization."""
    from archit_app.geometry.curve import ArcCurve, BezierCurve, NURBSCurve
    from archit_app.geometry.polygon import Polygon2D as P2D

    geom = wall.geometry

    if isinstance(geom, P2D):
        # Use Shapely polygon directly
        return geom._to_shapely()

    elif isinstance(geom, (ArcCurve, BezierCurve, NURBSCurve)):
        # Tessellate the curve centre-line into a LineString
        from shapely.geometry import LineString
        pts = geom.to_polyline(resolution=32)
        if len(pts) < 2:
            return None
        return LineString([(p.x, p.y) for p in pts])

    return None


def find_rooms(
    walls: "list[Wall] | tuple[Wall, ...]",
    *,
    min_area: float = 0.5,
) -> "list[Polygon2D]":
    """
    Detect enclosed polygon regions formed by ``walls``.

    Parameters
    ----------
    walls:
        Collection of Wall elements to analyse.
    min_area:
        Minimum polygon area in m² (smaller regions are discarded).

    Returns
    -------
    list[Polygon2D]
        Detected room outlines, largest first.
    """
    try:
        from shapely.ops import polygonize, unary_union
    except ImportError as e:
        raise ImportError(
            "shapely is required for room detection. "
            "It should be installed with archit-app by default."
        ) from e

    from archit_app.geometry.crs import WORLD
    from archit_app.geometry.point import Point2D
    from archit_app.geometry.polygon import Polygon2D

    if not walls:
        return []

    # Collect Shapely geometries from walls
    shapely_geoms = []
    for wall in walls:
        sg = _wall_to_shapely(wall)
        if sg is not None:
            shapely_geoms.append(sg)

    if not shapely_geoms:
        return []

    # Polygonize: finds all enclosed regions formed by the line/polygon boundaries
    all_lines = unary_union(shapely_geoms)
    candidates = list(polygonize(all_lines))

    # Also try with polygon boundaries (exterior rings)
    boundary_lines = []
    for sg in shapely_geoms:
        try:
            boundary_lines.append(sg.boundary)
        except Exception:
            pass
    if boundary_lines:
        boundary_union = unary_union(boundary_lines)
        candidates.extend(polygonize(boundary_union))

    # Deduplicate and filter by area
    seen_wkb: set[bytes] = set()
    results: list[Polygon2D] = []
    for candidate in candidates:
        if candidate.area < min_area:
            continue
        try:
            wkb = candidate.wkb
        except Exception:
            wkb = None
        if wkb is not None and wkb in seen_wkb:
            continue
        if wkb is not None:
            seen_wkb.add(wkb)

        # Convert shapely polygon → Polygon2D
        try:
            coords = list(candidate.exterior.coords)[:-1]  # drop closing duplicate
            pts = tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in coords)
            if len(pts) < 3:
                continue

            holes = []
            for interior in candidate.interiors:
                hole_coords = list(interior.coords)[:-1]
                hole_pts = tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in hole_coords)
                if len(hole_pts) >= 3:
                    holes.append(hole_pts)

            poly = Polygon2D(exterior=pts, holes=tuple(holes))
            results.append(poly)
        except Exception:
            continue

    # Sort largest first
    results.sort(key=lambda p: p.area, reverse=True)
    return results


def rooms_from_walls(
    walls: "list[Wall] | tuple[Wall, ...]",
    *,
    level_index: int = 0,
    program: str = "unknown",
    min_area: float = 0.5,
) -> "list[Room]":
    """
    Detect rooms from walls and wrap each polygon in a Room element.

    Parameters
    ----------
    walls:
        Wall elements to polygonize.
    level_index:
        Floor index assigned to created Room objects.
    program:
        Program string assigned to all created rooms (e.g. ``"unknown"``).
    min_area:
        Minimum room area in m².

    Returns
    -------
    list[Room]
        Detected rooms, largest first.
    """
    from archit_app.elements.room import Room

    polygons = find_rooms(walls, min_area=min_area)
    rooms = []
    for i, poly in enumerate(polygons):
        room = Room(
            boundary=poly,
            name=f"Room {i + 1}",
            program=program,
            level_index=level_index,
        )
        rooms.append(room)
    return rooms
