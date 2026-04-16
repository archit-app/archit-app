"""
DXF read/write for floorplan levels and buildings.

Requires the optional dependency: pip install archit-app[io]

Export layer convention:
  - Rooms      → "FP_ROOMS"      (hatch + boundary polyline)
  - Walls      → "FP_WALLS"      (solid hatch + boundary polyline)
  - Openings   → "FP_OPENINGS"   (boundary polyline)
  - Columns    → "FP_COLUMNS"    (solid hatch + boundary polyline)

For multi-level buildings, layer names are prefixed: "L00_FP_WALLS", etc.

Import reads LWPOLYLINE entities and reconstructs Level / Building objects.
For round-trip fidelity, the importer recognises the "FP_*" layer convention.
For generic DXF files, use the ``layer_mapping`` parameter to specify which
DXF layer names map to which element type.

Usage::

    # Export
    from archit_app.io.dxf import building_to_dxf, save_building_dxf
    doc = building_to_dxf(my_building)
    doc.saveas("my_building.dxf")

    # Import
    from archit_app.io.dxf import building_from_dxf, level_from_dxf
    building = building_from_dxf("my_building.dxf")
    level    = level_from_dxf("floor_plan.dxf")

    # Generic DXF with custom layer names
    level = level_from_dxf(
        "drawing.dxf",
        layer_mapping={"A-WALL": "walls", "A-ROOM": "rooms"},
    )
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Sequence

from archit_app.building.building import Building, BuildingMetadata
from archit_app.building.level import Level
from archit_app.elements.column import Column
from archit_app.elements.opening import Opening, OpeningKind
from archit_app.elements.room import Room
from archit_app.elements.wall import Wall, WallType
from archit_app.geometry.crs import WORLD
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

# DXF ACI color codes
_COLOR = {
    "rooms": 4,       # cyan
    "walls": 252,     # near-black
    "openings": 3,    # green
    "columns": 1,     # red
}


def _require_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        raise ImportError(
            "ezdxf is required for DXF export. "
            "Install it with: pip install archit-app[io]"
        )


def _poly_coords(poly: Polygon2D) -> list[tuple[float, float]]:
    """Extract exterior ring as list of (x, y) tuples."""
    return [(p.x, p.y) for p in poly.exterior]


def _geom_coords(geom, resolution: int = 32) -> list[tuple[float, float]]:
    """Get (x, y) boundary coords from any wall geometry."""
    if isinstance(geom, Polygon2D):
        return _poly_coords(geom)
    pts = geom.to_polyline(resolution)
    return [(p.x, p.y) for p in pts]


def _add_lwpolyline(msp, coords: list[tuple[float, float]], layer: str, color: int, closed: bool = True):
    """Add a closed LWPolyline to modelspace."""
    if len(coords) < 2:
        return
    pline = msp.add_lwpolyline(coords, dxfattribs={"layer": layer, "color": color})
    pline.close(closed)


def _add_hatch(msp, coords: list[tuple[float, float]], holes: list[list[tuple[float, float]]], layer: str, color: int):
    """Add a solid hatch polygon (with optional holes) to modelspace."""
    if len(coords) < 3:
        return
    hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
    hatch.set_pattern_fill("SOLID")

    # Close the exterior ring if needed
    ext = list(coords)
    if ext[0] != ext[-1]:
        ext.append(ext[0])

    # ezdxf ≥ 1.0 uses hatch.paths.add_polyline_path();
    # older versions used the edit_boundary() context manager.
    paths_api = getattr(hatch, "paths", None)
    if paths_api is not None:
        paths_api.add_polyline_path(ext, is_closed=True)
        for hole in holes:
            h = list(hole)
            if h[0] != h[-1]:
                h.append(h[0])
            paths_api.add_polyline_path(h, is_closed=True)
    else:
        with hatch.edit_boundary() as b:
            b.add_polyline_path(ext, is_closed=True)
            for hole in holes:
                h = list(hole)
                if h[0] != h[-1]:
                    h.append(h[0])
                b.add_polyline_path(h, is_closed=True)


def _layer_name(prefix: str, element_type: str) -> str:
    return f"{prefix}FP_{element_type.upper()}"


def _export_level(level: Level, msp, prefix: str = "") -> None:
    """Write all elements of a level to the given modelspace."""

    # --- Rooms ---
    room_layer = _layer_name(prefix, "ROOMS")
    for room in level.rooms:
        coords = _poly_coords(room.boundary)
        holes = [[(p.x, p.y) for p in h.exterior] for h in room.holes]
        _add_hatch(msp, coords, holes, room_layer, _COLOR["rooms"])
        _add_lwpolyline(msp, coords, room_layer, _COLOR["rooms"])

    # --- Walls ---
    wall_layer = _layer_name(prefix, "WALLS")
    for wall in level.walls:
        coords = _geom_coords(wall.geometry)
        _add_hatch(msp, coords, [], wall_layer, _COLOR["walls"])
        _add_lwpolyline(msp, coords, wall_layer, _COLOR["walls"])

        # Openings as cutouts drawn on opening layer
        opening_layer = _layer_name(prefix, "OPENINGS")
        for opening in wall.openings:
            oc = _poly_coords(opening.geometry)
            _add_lwpolyline(msp, oc, opening_layer, _COLOR["openings"])

    # --- Level-level openings ---
    opening_layer = _layer_name(prefix, "OPENINGS")
    for opening in level.openings:
        oc = _poly_coords(opening.geometry)
        _add_lwpolyline(msp, oc, opening_layer, _COLOR["openings"])

    # --- Columns ---
    col_layer = _layer_name(prefix, "COLUMNS")
    for col in level.columns:
        coords = _poly_coords(col.geometry)
        _add_hatch(msp, coords, [], col_layer, _COLOR["columns"])
        _add_lwpolyline(msp, coords, col_layer, _COLOR["columns"])


def level_to_dxf(level: Level):
    """
    Export a single Level to a DXF document.

    Returns:
        ezdxf.document.Drawing object — call .saveas(path) to write to disk.
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6  # meters (6 = meters in DXF standard)

    # Define layers
    for layer_suffix, color in [
        ("FP_ROOMS", _COLOR["rooms"]),
        ("FP_WALLS", _COLOR["walls"]),
        ("FP_OPENINGS", _COLOR["openings"]),
        ("FP_COLUMNS", _COLOR["columns"]),
    ]:
        doc.layers.add(layer_suffix, color=color)

    msp = doc.modelspace()
    _export_level(level, msp, prefix="")
    return doc


def building_to_dxf(building: Building):
    """
    Export an entire Building to a DXF document.

    Each level gets its own set of layers prefixed by level index:
      L00_FP_WALLS, L01_FP_WALLS, etc.

    Returns:
        ezdxf.document.Drawing object
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.new(dxfversion="R2010")
    doc.header["$INSUNITS"] = 6  # meters

    msp = doc.modelspace()

    for level in building.levels:
        prefix = f"L{level.index:02d}_"
        for suffix, color in [
            ("FP_ROOMS", _COLOR["rooms"]),
            ("FP_WALLS", _COLOR["walls"]),
            ("FP_OPENINGS", _COLOR["openings"]),
            ("FP_COLUMNS", _COLOR["columns"]),
        ]:
            layer_name = f"{prefix}FP_{suffix.split('_', 1)[-1]}"
            if layer_name not in doc.layers:
                lyr = doc.layers.add(layer_name, color=color)
                # Offset each level slightly in Z for 3D stacking visibility
                # (DXF layer elevation is set per entity, not per layer)

        _export_level(level, msp, prefix=prefix)

    # Add a metadata block comment
    if building.metadata.name:
        doc.header["$PROJECTNAME"] = building.metadata.name

    return doc


def save_level_dxf(level: Level, path: str) -> None:
    """Write a Level to a DXF file."""
    doc = level_to_dxf(level)
    doc.saveas(path)


def save_building_dxf(building: Building, path: str) -> None:
    """Write a Building to a DXF file."""
    doc = building_to_dxf(building)
    doc.saveas(path)


# ---------------------------------------------------------------------------
# DXF import
# ---------------------------------------------------------------------------

# Layer suffixes used by the exporter
_SUFFIX_ROOMS    = "FP_ROOMS"
_SUFFIX_WALLS    = "FP_WALLS"
_SUFFIX_OPENINGS = "FP_OPENINGS"
_SUFFIX_COLUMNS  = "FP_COLUMNS"

# Canonical element-type keys
_TYPE_ROOMS    = "rooms"
_TYPE_WALLS    = "walls"
_TYPE_OPENINGS = "openings"
_TYPE_COLUMNS  = "columns"

_SUFFIX_TO_TYPE: dict[str, str] = {
    _SUFFIX_ROOMS:    _TYPE_ROOMS,
    _SUFFIX_WALLS:    _TYPE_WALLS,
    _SUFFIX_OPENINGS: _TYPE_OPENINGS,
    _SUFFIX_COLUMNS:  _TYPE_COLUMNS,
}

# Regex: optional level prefix "L{dd}_" followed by FP_* suffix
_LAYER_RE = re.compile(
    r"^(?:(L\d+)_)?(" + "|".join(_SUFFIX_TO_TYPE.keys()) + r")$",
    re.IGNORECASE,
)


def _lwpolyline_to_polygon(entity) -> Polygon2D | None:
    """
    Convert an ezdxf LWPolyline entity to a Polygon2D in WORLD coordinates.

    Returns None when the polyline has fewer than 3 vertices.
    """
    pts = [(v[0], v[1]) for v in entity.get_points()]
    if len(pts) < 3:
        return None
    points = tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in pts)
    try:
        return Polygon2D(exterior=points, crs=WORLD)
    except Exception:
        return None


def _collect_polygons(doc) -> dict[str, list[Polygon2D]]:
    """
    Scan all LWPOLYLINE entities in *doc* and group their polygons by
    canonical element type + level prefix.

    The returned dict key is ``"{level_prefix}:{element_type}"`` where
    *level_prefix* is ``"L00"``, ``"L01"``, … or the empty string ``""``
    for single-level files without a prefix.
    """
    groups: dict[str, list[Polygon2D]] = defaultdict(list)

    for entity in doc.modelspace().query("LWPOLYLINE"):
        layer_name: str = entity.dxf.layer.strip()
        m = _LAYER_RE.match(layer_name)
        if m is None:
            continue
        level_prefix = (m.group(1) or "").upper()   # e.g. "L00" or ""
        elem_type = _SUFFIX_TO_TYPE[m.group(2).upper()]
        key = f"{level_prefix}:{elem_type}"
        poly = _lwpolyline_to_polygon(entity)
        if poly is not None:
            groups[key].append(poly)

    return dict(groups)


def _polygons_to_level(
    polys_by_type: dict[str, list[Polygon2D]],
    *,
    level_index: int = 0,
    level_elevation: float = 0.0,
    level_floor_height: float = 3.0,
    wall_height: float = 3.0,
    wall_thickness: float = 0.2,
    column_height: float = 3.0,
) -> Level:
    """Build a Level from pre-bucketed polygon lists."""
    level = Level(
        index=level_index,
        elevation=level_elevation,
        floor_height=level_floor_height,
    )

    for poly in polys_by_type.get(_TYPE_WALLS, []):
        wall = Wall(
            geometry=poly,
            thickness=wall_thickness,
            height=wall_height,
            wall_type=WallType.INTERIOR,
        )
        level = level.add_wall(wall)

    for poly in polys_by_type.get(_TYPE_ROOMS, []):
        room = Room(boundary=poly, level_index=level_index)
        level = level.add_room(room)

    for poly in polys_by_type.get(_TYPE_COLUMNS, []):
        col = Column(geometry=poly, height=column_height)
        level = level.add_column(col)

    for poly in polys_by_type.get(_TYPE_OPENINGS, []):
        bb = poly.bounding_box()
        width  = max(bb.width, 1e-3)
        height = max(bb.height, 1e-3)
        opening = Opening(
            kind=OpeningKind.DOOR,
            geometry=poly,
            width=width,
            height=wall_height,
            sill_height=0.0,
        )
        level = level.add_opening(opening)

    return level


def _parse_level_index(prefix: str) -> int:
    """Convert e.g. "L02" → 2."""
    digits = re.sub(r"[^0-9]", "", prefix)
    return int(digits) if digits else 0


def level_from_dxf(
    path: str,
    *,
    layer_mapping: dict[str, str] | None = None,
    level_index: int = 0,
    level_elevation: float = 0.0,
    level_floor_height: float = 3.0,
    wall_height: float = 3.0,
    wall_thickness: float = 0.2,
    column_height: float = 3.0,
) -> Level:
    """
    Import a single Level from a DXF file.

    The importer reads LWPOLYLINE entities and maps them to element types using
    the ``FP_*`` layer convention produced by :func:`level_to_dxf`.

    For generic DXF files that use different layer names, pass a
    ``layer_mapping`` dict that maps DXF layer names to one of the canonical
    keys ``"walls"``, ``"rooms"``, ``"openings"``, or ``"columns"``:

    .. code-block:: python

        level = level_from_dxf(
            "drawing.dxf",
            layer_mapping={"A-WALL": "walls", "A-FLOR-PATT": "rooms"},
        )

    Parameters
    ----------
    path:
        Path to the DXF file.
    layer_mapping:
        Optional dict mapping DXF layer names → element type keys.
        When provided, these mappings supplement (and override) the automatic
        ``FP_*`` detection.
    level_index:
        Floor index assigned to the imported level (default 0).
    level_elevation:
        Elevation of this level in meters (default 0.0).
    level_floor_height:
        Floor-to-ceiling height in meters (default 3.0).
    wall_height, wall_thickness, column_height:
        Defaults applied to all imported elements (DXF stores no height data).

    Returns
    -------
    Level
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.readfile(path)

    groups: dict[str, list[Polygon2D]] = defaultdict(list)

    for entity in doc.modelspace().query("LWPOLYLINE"):
        layer_name: str = entity.dxf.layer.strip()

        # 1. Try automatic FP_* recognition
        m = _LAYER_RE.match(layer_name)
        if m:
            elem_type = _SUFFIX_TO_TYPE[m.group(2).upper()]
            poly = _lwpolyline_to_polygon(entity)
            if poly is not None:
                groups[elem_type].append(poly)
            continue

        # 2. Try user-supplied layer_mapping
        if layer_mapping and layer_name in layer_mapping:
            elem_type = layer_mapping[layer_name].lower()
            if elem_type in (_TYPE_ROOMS, _TYPE_WALLS, _TYPE_OPENINGS, _TYPE_COLUMNS):
                poly = _lwpolyline_to_polygon(entity)
                if poly is not None:
                    groups[elem_type].append(poly)

    return _polygons_to_level(
        dict(groups),
        level_index=level_index,
        level_elevation=level_elevation,
        level_floor_height=level_floor_height,
        wall_height=wall_height,
        wall_thickness=wall_thickness,
        column_height=column_height,
    )


def building_from_dxf(
    path: str,
    *,
    wall_height: float = 3.0,
    wall_thickness: float = 0.2,
    column_height: float = 3.0,
    floor_height: float = 3.0,
    floor_elevation_step: float = 3.0,
) -> Building:
    """
    Import a multi-level Building from a DXF file.

    Levels are detected from the ``L{dd}_FP_*`` layer name prefix produced by
    :func:`building_to_dxf`.  A DXF that has no level prefix (i.e. was
    exported by :func:`level_to_dxf`) is imported as a single-level building.

    Parameters
    ----------
    path:
        Path to the DXF file.
    wall_height, wall_thickness, column_height:
        Defaults applied when height data is absent in the DXF.
    floor_height:
        Floor-to-ceiling height assigned to every imported level.
    floor_elevation_step:
        Vertical distance between consecutive levels in meters (default 3.0).

    Returns
    -------
    Building
    """
    ezdxf = _require_ezdxf()
    doc = ezdxf.readfile(path)

    # Collect polygons grouped by "(level_prefix, element_type)"
    # level_prefix is "" for un-prefixed layers
    by_level: dict[str, dict[str, list[Polygon2D]]] = defaultdict(lambda: defaultdict(list))

    for entity in doc.modelspace().query("LWPOLYLINE"):
        layer_name: str = entity.dxf.layer.strip()
        m = _LAYER_RE.match(layer_name)
        if m is None:
            continue
        level_prefix = (m.group(1) or "").upper()
        elem_type = _SUFFIX_TO_TYPE[m.group(2).upper()]
        poly = _lwpolyline_to_polygon(entity)
        if poly is not None:
            by_level[level_prefix][elem_type].append(poly)

    if not by_level:
        # Empty DXF — return a building with no levels
        name = doc.header.get("$PROJECTNAME", "")
        return Building(metadata=BuildingMetadata(name=name))

    # Sort level prefixes: "" first, then L00 < L01 < …
    def _sort_key(prefix: str) -> int:
        return -1 if prefix == "" else _parse_level_index(prefix)

    sorted_prefixes = sorted(by_level.keys(), key=_sort_key)

    levels: list[Level] = []
    for i, prefix in enumerate(sorted_prefixes):
        idx = _parse_level_index(prefix) if prefix else i
        elevation = idx * floor_elevation_step
        level = _polygons_to_level(
            dict(by_level[prefix]),
            level_index=idx,
            level_elevation=elevation,
            level_floor_height=floor_height,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            column_height=column_height,
        )
        levels.append(level)

    name = doc.header.get("$PROJECTNAME", "")
    return Building(
        metadata=BuildingMetadata(name=name),
        levels=tuple(levels),
    )
