<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo/archit-app-dark.svg">
  <img src="logo/archit-app-light.svg" alt="archit-app" width="360">
</picture>

A general-purpose, extensible Python library for architectural floorplan design and analysis.

```
pip install archit-app
```

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

`archit_app` provides a clean, layered data model for working with architectural floorplans in Python. It supports non-Manhattan shapes, curve walls, multi-level buildings, and exports to SVG, DXF, GeoJSON, and a canonical JSON format — all built on immutable, type-safe objects.

**Key features:**

- Geometry primitives with coordinate system (CRS) tagging — mixing spaces raises an error immediately
- Architectural elements: walls (straight, arc, spline), rooms, openings (doors/windows), columns
- Multi-level building structure: `Level → Building → SiteContext`
- I/O: JSON (fully round-trippable), SVG, GeoJSON, DXF (optional)
- Plugin registry for extending the library without touching core code
- Immutable Pydantic models throughout — every "mutation" returns a new object

---

## Installation

```bash
pip install archit-app
```

For DXF and SVG export support:

```bash
pip install "archit-app[io]"
```

For image and panorama support (coming in a future release):

```bash
pip install "archit-app[image]"
```

For graph-based analysis (coming in a future release):

```bash
pip install "archit-app[analysis]"
```

For all optional dependencies:

```bash
pip install "archit-app[io,image,analysis]"
```

**Requirements:** Python 3.11+, pydantic ≥ 2.0, shapely ≥ 2.0, numpy ≥ 1.26

---

## Quick Start

```python
from archit_app import (
    Wall, Room, Level, Building, BuildingMetadata,
    Opening, Column, Point2D, Polygon2D, WORLD,
)

# 1. Create a room
boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
living_room = Room(boundary=boundary, name="Living Room", program="living")

# 2. Create walls
north_wall = Wall.straight(0, 4, 6, 4, thickness=0.2, height=3.0)
south_wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
west_wall  = Wall.straight(0, 0, 0, 4, thickness=0.2, height=3.0)

# Add a door to the west wall
door = Opening.door(x=0, y=1.5, width=0.9, height=2.1)
west_wall = west_wall.add_opening(door)

# 3. Add a structural column
col = Column.rectangular(x=2.8, y=1.8, width=0.3, depth=0.3, height=3.0)

# 4. Assemble a level
ground = (
    Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
    .add_room(living_room)
    .add_wall(north_wall)
    .add_wall(south_wall)
    .add_wall(west_wall)
    .add_column(col)
)

# 5. Build the building
building = (
    Building()
    .with_metadata(name="My House", architect="A. Architect")
    .add_level(ground)
)

print(building)
# Building(name='My House', levels=1, gross_area=24.0m²)
```

### Export to SVG

```python
from archit_app.io.svg import level_to_svg, save_level_svg

svg_str = level_to_svg(ground, pixels_per_meter=50)
save_level_svg(ground, "ground_floor.svg", pixels_per_meter=50)
```

### Export to JSON and reload

```python
from archit_app.io.json_schema import save_building, load_building

save_building(building, "my_house.archit_app.json")
restored = load_building("my_house.archit_app.json")
```

### Export to GeoJSON

```python
from archit_app.io.geojson import level_to_geojson
import json

fc = level_to_geojson(ground)
print(json.dumps(fc, indent=2))
```

### Export to DXF

```python
# Requires: pip install "archit-app[io]"
from archit_app.io.dxf import save_building_dxf

save_building_dxf(building, "my_house.dxf")
```

---

## Coordinate System

`archit_app` uses a **Y-up, meters** world coordinate system — the standard for architecture. Screen and image layers are Y-down; the library handles the flip at export time so your geometry code never sees it.

| Space    | Origin    | Y direction | Unit   | Use                       |
|----------|-----------|-------------|--------|---------------------------|
| `WORLD`  | site datum | up         | meters | all architectural geometry |
| `SCREEN` | top-left   | down        | pixels | rendering, UI events       |
| `IMAGE`  | top-left   | down        | pixels | raster images, panoramas   |
| `WGS84`  | lat/lon    | up          | meters | GIS / site georeferencing  |

Every `Point2D` and `Vector2D` carries its CRS. Arithmetic between mismatched spaces raises `CRSMismatchError` immediately.

---

## Architecture

The library is structured in layers:

```
archit_app/
├── geometry/     Layer 1 — CRS, points, vectors, transforms, polygons, curves
├── elements/     Layer 2 — Wall, Room, Opening, Column (all Element subclasses)
├── building/     Layer 3 — Level, Building, SiteContext
├── io/           Layer 5 — JSON, SVG, GeoJSON, DXF
├── core/         Registry — plugin/extension system
└── utils/        Unit helpers
```

All models are **immutable**. Every "mutation" method (e.g. `level.add_wall(w)`, `wall.add_opening(o)`) returns a new object.

---

## Documentation

Full API reference and guides are in the [`docs/`](docs/) directory:

- [Getting Started](docs/getting_started.md)
- [Core Concepts](docs/concepts.md)
- [API Reference — Geometry](docs/api/geometry.md)
- [API Reference — Elements](docs/api/elements.md)
- [API Reference — Building](docs/api/building.md)
- [API Reference — I/O](docs/api/io.md)
- [API Reference — Registry](docs/api/registry.md)
- [Contributing](docs/contributing.md)

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Layer 1 — Geometry | Done | CRS, Point, Vector, BBox, Polygon, Curve, Transform |
| Layer 2 — Elements | Done | Wall, Room, Opening, Column |
| Layer 3 — Building | Done | Level, Building, SiteContext |
| Layer 5 — I/O | Done | JSON, SVG, GeoJSON, DXF |
| Layer 4 — Image | Planned | Panorama, rectification, camera calibration |
| Layer 6 — Analysis | Planned | Topology graph, area, circulation, visibility |
| Layer 7 — Rendering | Planned | Matplotlib interactive, advanced SVG |
| IFC export | Planned | IFC 4.x via ifcopenshell |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](docs/contributing.md) for setup instructions and coding standards.

---

## License

MIT
