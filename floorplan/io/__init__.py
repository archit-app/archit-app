"""
I/O layer for the floorplan package.

Available formats:
  - JSON  (canonical, fully round-trippable)   floorplan.io.json_schema
  - SVG   (2D rendering, no extra deps)        floorplan.io.svg
  - GeoJSON (GIS export, no extra deps)        floorplan.io.geojson
  - DXF   (AutoCAD, requires ezdxf)            floorplan.io.dxf

Quick access:
"""

from floorplan.io.json_schema import (
    building_to_json,
    building_from_json,
    building_to_dict,
    building_from_dict,
    save_building,
    load_building,
)
from floorplan.io.svg import (
    level_to_svg,
    building_to_svg_pages,
    save_level_svg,
    save_building_svgs,
)
from floorplan.io.geojson import (
    level_to_geojson,
    building_to_geojson,
    level_to_geojson_str,
    building_to_geojson_str,
    save_level_geojson,
    save_building_geojson,
)

__all__ = [
    # JSON
    "building_to_json",
    "building_from_json",
    "building_to_dict",
    "building_from_dict",
    "save_building",
    "load_building",
    # SVG
    "level_to_svg",
    "building_to_svg_pages",
    "save_level_svg",
    "save_building_svgs",
    # GeoJSON
    "level_to_geojson",
    "building_to_geojson",
    "level_to_geojson_str",
    "building_to_geojson_str",
    "save_level_geojson",
    "save_building_geojson",
    # DXF (imported separately to avoid hard dependency)
    # from floorplan.io.dxf import save_building_dxf
]
