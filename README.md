<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo/archit-app-dark.svg">
  <img src="logo/archit-app-light.svg" alt="archit-app" width="360">
</picture>

A general-purpose, extensible Python library for architectural floorplan design and analysis.

```
pip install archit-app
```

[![PyPI](https://img.shields.io/pypi/v/archit-app.svg)](https://pypi.org/project/archit-app/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What's new in 0.5.0

- **Typed error hierarchy** (`ArchitError`, `OverlapError`, `OutOfBoundsError`, `ElementNotFoundError`, `GeometryError`, `SessionError`) — structured `code` / `element_id` / `hint`.
- **Structured `validate(building)`** in `archit_app.analysis.validate` — `list[Finding]` with severity, code, message, and a paste-ready `fix_hint`.
- **`Opening.swing_arc()`** and **`Opening.glazing_lines()`** — door-swing and window-glazing geometry derived in the geometry layer; every renderer agrees.
- **Polished SVG / PDF exports** — title block, scale bar, north arrow, room labels with areas, exterior dimension chains, dashed swing arcs, glazing lines, all in the brand palette (Void / Vellum / Blueprint / Datum).
- **Per-Level Shapely cache** + new batch mutators (`Level.add_openings`, `add_columns`, `add_beams`, `add_slabs`, `add_ramps`, `Building.add_levels`, `replace_levels`).
- **Lazy heavy imports** — `import archit_app` no longer pulls `numpy` or `shapely` at module load.

See [`CHANGELOG.md`](CHANGELOG.md) for the full list.

---

## Overview

`archit_app` provides a clean, layered data model for working with architectural floorplans in Python. It supports non-Manhattan shapes, curved walls, multi-level buildings, and exports to SVG, DXF, GeoJSON, IFC, PNG, PDF, and a canonical JSON format — all built on immutable, type-safe objects.

**Highlights**

- **Geometry primitives with CRS tagging** — `Point2D`, `Vector2D`, `Polygon2D`, `Segment2D`, `Ray2D`, `Line2D`, `Polyline2D`, `Transform2D`. Mixing spaces raises an error immediately.
- **`CoordinateConverter`** — graph-based multi-CRS path-finding; `Point2D.to(target, conv)`.
- **Full NURBS evaluator** — Cox–de Boor; `clamped_uniform()` factory; exact conic sections via rational weights.
- **Architectural elements** — walls (straight / arc / spline), rooms, openings, columns, staircases, slabs, ramps, elevators, beams, furniture (20 categories, 19 SVG symbols), annotations (text / dimension / section mark), structural grid, wall joining (`miter_join`, `butt_join`, `join_walls`).
- **Multi-level buildings** — `Level → Building`, with elevators and a structural grid attached at the building level.
- **Land parcel model** — GPS coordinates, setbacks, buildable envelope, AI-agent context hook.
- **Spatial analysis** — adjacency graph, egress, area validation, zoning compliance, daylighting, isovist.
- **Floorplan Agent Protocol v1.0.0** — versioned, strict-Pydantic inter-agent message layer (`FloorplanSnapshot`, `AgentHandoff`, `MutationEnvelope`, `ProtocolReport`).
- **I/O** — JSON, SVG, GeoJSON, DXF round-trip, IFC 4.x round-trip, PNG raster, PDF (multi-page).
- **Layer registry, unit conversion, element transforms, structured validation, spatial index, plugin registry.**
- Immutable Pydantic models throughout — every "mutation" returns a new object.

---

## Installation

```bash
pip install archit-app                                # core
pip install "archit-app[io]"                          # + DXF / SVG export
pip install "archit-app[ifc]"                         # + IFC 4.x export
pip install "archit-app[image]"                       # + PNG raster
pip install "archit-app[pdf]"                         # + multi-page PDF
pip install "archit-app[analysis]"                    # + graph analysis
pip install "archit-app[io,ifc,image,pdf,analysis]"   # everything
```

**Requirements:** Python 3.11+, `pydantic ≥ 2.0`, `shapely ≥ 2.0`, `numpy ≥ 1.26`.

---

## Quick start

```python
from archit_app import (
    Wall, Room, Level, Building, Opening, Column,
    Polygon2D, WORLD,
)

# Room + walls
boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
living   = Room(boundary=boundary, name="Living Room", program="living")

walls = [
    Wall.straight(0, 4, 6, 4, thickness=0.2, height=3.0),
    Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0),
    Wall.straight(0, 0, 0, 4, thickness=0.2, height=3.0),
]
walls[2] = walls[2].add_opening(Opening.door(x=0, y=1.5, width=0.9, height=2.1))

# Level + Building
ground = (
    Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
    .add_room(living)
    .add_walls(walls)
    .add_column(Column.rectangular(x=2.8, y=1.8, width=0.3, depth=0.3, height=3.0))
)
building = (
    Building()
    .with_metadata(name="My House", architect="A. Architect")
    .add_level(ground)
)

# Export
from archit_app.io.svg import save_level_svg
save_level_svg(ground, "ground_floor.svg", pixels_per_meter=50)
```

For the rest — DXF / PDF / IFC / NURBS / structural grid / agent protocol / spatial analysis / unit conversion — see [`docs/cookbook.md`](docs/cookbook.md).

---

## Coordinate system

Y-up, meters world coordinates — the standard for architecture. Screen and image layers are Y-down; the library handles the flip at export time.

| Space    | Origin     | Y direction | Unit   | Use                       |
|----------|------------|-------------|--------|---------------------------|
| `WORLD`  | site datum | up          | meters | all architectural geometry |
| `SCREEN` | top-left   | down        | pixels | rendering, UI events       |
| `IMAGE`  | top-left   | down        | pixels | raster images, panoramas   |
| `WGS84`  | lat/lon    | up          | meters | GIS / site georeferencing  |

Every `Point2D` and `Vector2D` carries its CRS. Arithmetic between mismatched spaces raises `CRSMismatchError` immediately.

---

## Architecture

```
archit_app/
├── geometry/    Layer 1 — CRS, points, vectors, transforms, polygons, curves, lines
├── elements/    Layer 2 — Wall, Room, Opening, Column, Staircase, Slab, Ramp, Elevator,
│                          Beam, Furniture, annotations, wall_join utilities
├── building/    Layer 3 — Land, Level, Building, BuildingMetadata, StructuralGrid,
│                          Layer registry, ValidationReport, spatial_index
├── analysis/    Layer 6 — topology, circulation, area, compliance, daylighting,
│                          visibility, validate (structured findings)
├── protocol/    Layer 7 — Floorplan Agent Protocol v1.0.0
├── io/          Layer 5 — JSON, SVG, GeoJSON, DXF, IFC, PNG, PDF
├── core/                  Plugin/extension registry + typed error hierarchy
└── units.py               Unit conversion (`parse_dimension`, to/from feet/inches/mm/cm)
```

All models are **immutable**. Every "mutation" method returns a new object.

---

## Documentation

- [Getting Started](docs/getting_started.md) — installation, quick start, basic examples
- [Core Concepts](docs/concepts.md) — coordinate systems, immutability, the element model
- [Cookbook](docs/cookbook.md) — recipes for every export format, agent protocol, analysis, transforms
- [Roadmap](docs/roadmap.md) — capability matrix
- [Changelog](CHANGELOG.md) — version-tagged history
- API Reference — [Geometry](docs/api/geometry.md) · [Elements](docs/api/elements.md) · [Building](docs/api/building.md) · [I/O](docs/api/io.md) · [Agent Protocol](docs/api/protocol.md) · [Registry](docs/api/registry.md)
- [Contributing](docs/contributing.md)

---

## Brand colors

| Token | Hex | Use |
|-------|-----|-----|
| **Void** | `#0C1018` | Night sky — deep shadows, primary text on light |
| **Vellum** | `#E8EDF5` | Tracing paper — primary text on dark, light fills |
| **Blueprint** | `#3B82F6` | Technical lines — accents, links |
| **Datum** | `#F59E0B` | Reference point — icon handles, highlights |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](docs/contributing.md) for setup and coding standards.

## License

MIT
