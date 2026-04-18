"""
GeoJSON export for floorplan levels and buildings.

Exports architectural elements as GeoJSON FeatureCollections. Useful for
loading floorplans into GIS tools (QGIS, Mapbox, Leaflet, etc.) and for
spatial analysis.

All coordinates are in the CRS of the elements (default: meters in WORLD space).
If you need geographic coordinates (lat/lon), apply a geo-referencing transform
to the Building/Level before exporting.

Usage:
    from archit_app.io.geojson import level_to_geojson, building_to_geojson
    import json

    fc = level_to_geojson(my_level)
    print(json.dumps(fc, indent=2))
"""

from __future__ import annotations

import json
from typing import Any

from archit_app.building.building import Building
from archit_app.building.level import Level
from archit_app.elements.column import Column
from archit_app.elements.opening import Opening, OpeningKind
from archit_app.elements.room import Room
from archit_app.elements.wall import Wall, WallType
from archit_app.geometry.crs import WORLD
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D


# ---------------------------------------------------------------------------
# Geometry serializers
# ---------------------------------------------------------------------------


def _polygon_to_geojson_coords(poly: Polygon2D) -> list[list[list[float]]]:
    """
    Convert a Polygon2D to GeoJSON coordinate format:
    [ exterior_ring, hole_ring_1, hole_ring_2, ... ]

    Each ring is a list of [x, y] pairs with the first == last (closed).
    GeoJSON exterior rings are CCW; interior rings (holes) are CW.
    Shapely/our Polygon2D handles winding automatically.
    """
    exterior = [[p.x, p.y] for p in poly.exterior]
    # Close the ring
    exterior.append(exterior[0])

    rings = [exterior]
    for hole in poly.holes:
        hole_coords = [[p.x, p.y] for p in hole]
        hole_coords.append(hole_coords[0])
        rings.append(hole_coords)
    return rings


def _geom_to_geojson(geom, resolution: int = 32) -> dict[str, Any]:
    """Convert wall geometry to GeoJSON Polygon geometry."""
    if isinstance(geom, Polygon2D):
        return {
            "type": "Polygon",
            "coordinates": _polygon_to_geojson_coords(geom),
        }
    # Curves: approximate as polygon via polyline
    pts = geom.to_polyline(resolution)
    coords = [[p.x, p.y] for p in pts]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


# ---------------------------------------------------------------------------
# Feature builders
# ---------------------------------------------------------------------------


def _room_to_feature(room: Room, level_index: int | None = None) -> dict[str, Any]:
    coords = _polygon_to_geojson_coords(room.boundary)
    # Add hole polygons as interior rings
    for hole in room.holes:
        hole_coords = [[p.x, p.y] for p in hole.exterior]
        hole_coords.append(hole_coords[0])
        coords.append(hole_coords)

    props: dict[str, Any] = {
        "element_type": "room",
        "id": str(room.id),
        "name": room.name,
        "program": room.program,
        "area_m2": round(room.area, 4),
        "gross_area_m2": round(room.gross_area, 4),
        "layer": room.layer,
    }
    if level_index is not None:
        props["level_index"] = level_index
    props.update(room.tags)

    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": coords},
        "properties": props,
    }


def _wall_to_feature(wall: Wall, level_index: int | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "element_type": "wall",
        "id": str(wall.id),
        "wall_type": wall.wall_type.value,
        "thickness_m": wall.thickness,
        "height_m": wall.height,
        "material": wall.material,
        "opening_count": len(wall.openings),
        "layer": wall.layer,
    }
    if level_index is not None:
        props["level_index"] = level_index
    props.update(wall.tags)

    return {
        "type": "Feature",
        "geometry": _geom_to_geojson(wall.geometry),
        "properties": props,
    }


def _column_to_feature(col: Column, level_index: int | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "element_type": "column",
        "id": str(col.id),
        "shape": col.shape.value,
        "height_m": col.height,
        "material": col.material,
        "layer": col.layer,
    }
    if level_index is not None:
        props["level_index"] = level_index
    props.update(col.tags)

    return {
        "type": "Feature",
        "geometry": _geom_to_geojson(col.geometry),
        "properties": props,
    }


def _opening_to_feature(opening: Opening, level_index: int | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "element_type": "opening",
        "id": str(opening.id),
        "kind": opening.kind.value,
        "width_m": opening.width,
        "height_m": opening.height,
        "sill_height_m": opening.sill_height,
        "layer": opening.layer,
    }
    if level_index is not None:
        props["level_index"] = level_index
    props.update(opening.tags)

    return {
        "type": "Feature",
        "geometry": _geom_to_geojson(opening.geometry),
        "properties": props,
    }


# ---------------------------------------------------------------------------
# Level and Building exporters
# ---------------------------------------------------------------------------


def level_to_geojson(
    level: Level,
    include: set[str] | None = None,
) -> dict[str, Any]:
    """
    Export a Level as a GeoJSON FeatureCollection.

    Args:
        level: the floor level to export
        include: set of element types to include. Options:
                 {"rooms", "walls", "columns", "openings"}
                 Defaults to all types.

    Returns:
        GeoJSON FeatureCollection dict
    """
    if include is None:
        include = {"rooms", "walls", "columns", "openings"}

    features: list[dict[str, Any]] = []
    idx = level.index

    if "rooms" in include:
        for room in level.rooms:
            features.append(_room_to_feature(room, idx))

    if "walls" in include:
        for wall in level.walls:
            features.append(_wall_to_feature(wall, idx))
            if "openings" in include:
                for opening in wall.openings:
                    features.append(_opening_to_feature(opening, idx))

    if "openings" in include:
        for opening in level.openings:
            features.append(_opening_to_feature(opening, idx))

    if "columns" in include:
        for col in level.columns:
            features.append(_column_to_feature(col, idx))

    return {
        "type": "FeatureCollection",
        "name": level.name or f"Level {level.index}",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }


def building_to_geojson(
    building: Building,
    include: set[str] | None = None,
) -> dict[str, Any]:
    """
    Export an entire Building as a single GeoJSON FeatureCollection.

    All levels are merged into one collection; each feature carries a
    'level_index' property to distinguish floors.
    """
    if include is None:
        include = {"rooms", "walls", "columns", "openings"}

    all_features: list[dict[str, Any]] = []
    for level in building.levels:
        fc = level_to_geojson(level, include=include)
        all_features.extend(fc["features"])

    return {
        "type": "FeatureCollection",
        "name": building.metadata.name or "Building",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": all_features,
    }


# ---------------------------------------------------------------------------
# GeoJSON import
# ---------------------------------------------------------------------------


def _coords_to_polygon(coords: list[list[list[float]]]) -> Polygon2D:
    """Convert GeoJSON Polygon coordinates (exterior + optional holes) to Polygon2D."""
    if not coords:
        raise ValueError("GeoJSON Polygon has no coordinate rings.")
    exterior_ring = coords[0]
    # GeoJSON rings are closed (first == last), so drop the last point.
    exterior_pts = tuple(
        Point2D(x=pt[0], y=pt[1], crs=WORLD)
        for pt in exterior_ring[:-1]
    )
    holes = []
    for ring in coords[1:]:
        hole_pts = tuple(
            Point2D(x=pt[0], y=pt[1], crs=WORLD)
            for pt in ring[:-1]
        )
        if hole_pts:
            holes.append(Polygon2D(exterior=hole_pts, crs=WORLD))
    return Polygon2D(exterior=exterior_pts, holes=tuple(holes), crs=WORLD)


def _feature_to_room(feature: dict[str, Any]) -> Room:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    poly = _coords_to_polygon(geom.get("coordinates", [[]]))
    return Room(
        boundary=poly,
        name=props.get("name", ""),
        program=props.get("program", ""),
        layer=props.get("layer", ""),
    )


def _feature_to_wall(feature: dict[str, Any]) -> Wall | None:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if geom.get("type") != "Polygon":
        return None
    poly = _coords_to_polygon(geom.get("coordinates", [[]]))
    try:
        wall_type = WallType(props.get("wall_type", "interior"))
    except ValueError:
        wall_type = WallType.INTERIOR
    return Wall(
        geometry=poly,
        thickness=float(props.get("thickness_m", 0.2)),
        height=float(props.get("height_m", 3.0)),
        wall_type=wall_type,
        material=props.get("material"),
        layer=props.get("layer", ""),
    )


def _feature_to_column(feature: dict[str, Any]) -> Column | None:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if geom.get("type") != "Polygon":
        return None
    from archit_app.elements.column import ColumnShape
    poly = _coords_to_polygon(geom.get("coordinates", [[]]))
    try:
        shape = ColumnShape(props.get("shape", "rectangular"))
    except ValueError:
        shape = ColumnShape.RECTANGULAR
    return Column(
        geometry=poly,
        height=float(props.get("height_m", 3.0)),
        shape=shape,
        material=props.get("material"),
        layer=props.get("layer", ""),
    )


def _feature_to_opening(feature: dict[str, Any]) -> Opening | None:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if geom.get("type") != "Polygon":
        return None
    poly = _coords_to_polygon(geom.get("coordinates", [[]]))
    try:
        kind = OpeningKind(props.get("kind", "door"))
    except ValueError:
        kind = OpeningKind.DOOR
    return Opening(
        geometry=poly,
        kind=kind,
        width=float(props.get("width_m", 0.9)),
        height=float(props.get("height_m", 2.1)),
        sill_height=float(props.get("sill_height_m", 0.0)),
        layer=props.get("layer", ""),
    )


def level_from_geojson(
    data: dict[str, Any],
    *,
    index: int = 0,
    elevation: float = 0.0,
    floor_height: float = 3.0,
    name: str = "",
) -> Level:
    """Reconstruct a :class:`Level` from a GeoJSON FeatureCollection.

    Reads the FeatureCollection produced by :func:`level_to_geojson` and
    converts features back to their corresponding element types via the
    ``properties.element_type`` field.

    Parameters
    ----------
    data:
        Parsed GeoJSON dict (a FeatureCollection).
    index:
        Level index to assign to the returned Level.
    elevation:
        Elevation in meters to assign.
    floor_height:
        Floor-to-ceiling height in meters.
    name:
        Optional name for the level.

    Returns
    -------
    Level
        A Level populated with rooms, walls, columns, and openings.
    """
    if not isinstance(data, dict):
        raise TypeError(f"Expected a dict, got {type(data).__name__}")
    if data.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON data must be a FeatureCollection.")

    level = Level(index=index, elevation=elevation, floor_height=floor_height, name=name)

    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        element_type = props.get("element_type", "")

        try:
            if element_type == "room":
                level = level.add_room(_feature_to_room(feature))
            elif element_type == "wall":
                wall = _feature_to_wall(feature)
                if wall is not None:
                    level = level.add_wall(wall)
            elif element_type == "column":
                col = _feature_to_column(feature)
                if col is not None:
                    level = level.add_column(col)
            elif element_type == "opening":
                op = _feature_to_opening(feature)
                if op is not None:
                    level = level.add_opening(op)
        except Exception:
            # Skip malformed features without crashing
            pass

    return level


def level_from_geojson_str(s: str, **kwargs) -> Level:
    """Parse a GeoJSON string and return a Level.

    See :func:`level_from_geojson` for parameter documentation.
    """
    return level_from_geojson(json.loads(s), **kwargs)


def level_to_geojson_str(level: Level, indent: int = 2, **kwargs) -> str:
    return json.dumps(level_to_geojson(level, **kwargs), indent=indent, ensure_ascii=False)


def building_to_geojson_str(building: Building, indent: int = 2, **kwargs) -> str:
    return json.dumps(building_to_geojson(building, **kwargs), indent=indent, ensure_ascii=False)


def save_level_geojson(level: Level, path: str, **kwargs) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(level_to_geojson_str(level, **kwargs))


def save_building_geojson(building: Building, path: str, **kwargs) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(building_to_geojson_str(building, **kwargs))
