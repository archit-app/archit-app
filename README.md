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
- **`CoordinateConverter`** — graph-based multi-CRS path-finding; `Point2D.to(target, conv)`; `build_default_converter()` for screen/image/world viewports
- **Full NURBS evaluator** — `NURBSCurve` uses the Cox–de Boor algorithm (exact rational evaluation, not linear interpolation); `clamped_uniform()` factory for smooth curves through endpoints; supports exact conic sections via rational weights
- Architectural elements: walls (straight, arc, spline), rooms, openings (doors/windows), columns, **staircases, slabs, ramps, elevators, beams**
- **Wall joining** — `miter_join()`, `butt_join()`, `join_walls()` for clean corner geometry
- **Structural grid** — named axes (A–H, 1–8), intersection queries, and point snapping
- Multi-level building structure: `Level → Building`, with elevators and a grid attached at building level
- **Land parcel model** — GPS coordinates, setbacks, buildable envelope, and an AI-agent context hook
- **Spatial analysis** (`archit_app.analysis`):
  - Room adjacency graph and connected components (networkx)
  - Egress path finding and compliance reporting
  - Area program validation against design targets
  - Zoning compliance checker (FAR, lot coverage, height, setbacks)
  - Daylighting and solar orientation report per room
  - Isovist (visibility polygon) from any viewpoint
- I/O: JSON (fully round-trippable), SVG, GeoJSON, **DXF round-trip** (read + write, optional), **IFC 4.x export** (optional, via `ifcopenshell`)
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

For IFC export (open BIM standard — Revit, ArchiCAD, FreeCAD compatible):

```bash
pip install "archit-app[ifc]"
```

For image and panorama support (coming in a future release):

```bash
pip install "archit-app[image]"
```

For graph-based analysis (room adjacency, egress path-finding):

```bash
pip install "archit-app[analysis]"
```

For all optional dependencies:

```bash
pip install "archit-app[io,ifc,image,analysis]"
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

### Define a land parcel and get agent context

```python
from archit_app import Land, Setbacks, ZoningInfo, Building

# 1. Define the parcel from GPS coordinates
land = Land.from_latlon([
    (37.7749, -122.4194),
    (37.7750, -122.4194),
    (37.7750, -122.4183),
    (37.7749, -122.4183),
], address="123 Main St, San Francisco, CA")

print(f"Lot area: {land.area_m2:.1f} m²")

# 2. Export a context dict — pass this to an AI agent to get zoning info
context = land.to_agent_context()
# {
#   "address": "123 Main St, San Francisco, CA",
#   "area_m2": 598.1,
#   "latlon_coords": [...],
#   "centroid_latlon": [...],
#   ...
# }

# 3. Enrich with zoning (manually or from an agent response)
land = (
    land
    .with_zoning(ZoningInfo(
        zone_code="RH-2",
        max_height_m=10.0,
        max_far=1.8,
        max_lot_coverage=0.6,
        allowed_uses=("residential",),
        source="SF Planning Code §207",
    ))
    .with_setbacks(Setbacks(front=3.0, back=6.0, left=1.5, right=1.5))
)

print(f"Buildable area: {land.buildable_area_m2:.1f} m²")
print(f"Max floor area: {land.max_floor_area_m2:.1f} m²")

# 4. Attach the land to a building
building = Building().with_land(land)
```

### DXF round-trip (read + write)

```python
# Requires: pip install "archit-app[io]"
from archit_app.io.dxf import (
    save_building_dxf, building_from_dxf,
    save_level_dxf, level_from_dxf,
)

# Export
save_building_dxf(building, "my_house.dxf")

# Import back — auto-detects archit-app's FP_* layer convention
restored = building_from_dxf("my_house.dxf")

# Import a single level, override defaults
level = level_from_dxf("floor_plan.dxf", wall_height=3.5, wall_thickness=0.25)

# Generic DXF with custom layer names
level = level_from_dxf(
    "autocad_drawing.dxf",
    layer_mapping={"A-WALL": "walls", "A-FLOR-PATT": "rooms"},
)
```

Recognised element types in `layer_mapping`: `"walls"`, `"rooms"`, `"openings"`, `"columns"`.

### Export to IFC 4.x

```python
# Requires: pip install "archit-app[ifc]"
from archit_app.io.ifc import building_to_ifc, save_building_ifc

# Get the ifcopenshell model object (for further manipulation)
model = building_to_ifc(building)
print(model.by_type("IfcWall"))       # list all exported walls
print(model.by_type("IfcSpace"))      # list all exported rooms
model.write("my_house.ifc")           # write to disk

# Or use the one-line convenience function
save_building_ifc(building, "my_house.ifc")
```

Exported to IFC: walls (`IfcWall`), rooms (`IfcSpace`), doors/windows (`IfcDoor`/`IfcWindow`),
columns (`IfcColumn`), slabs (`IfcSlab`), staircases (`IfcStair`) — all under the full
`IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey` hierarchy.
The IFC file can be opened in Revit, ArchiCAD, FreeCAD, and any other IFC 4-compliant viewer.

### Vertical circulation and structural elements

```python
import math
from archit_app import (
    Staircase, Slab, Ramp, Elevator, ElevatorDoor,
    Beam, BeamSection, Level, Building,
)

# Staircase — 12 risers connecting ground floor to first floor
stair = Staircase.straight(
    x=6, y=0, width=1.2, rise_count=12,
    rise_height=0.175, run_depth=0.28,
    bottom_level_index=0, top_level_index=1,
)
print(f"Total rise: {stair.total_rise:.2f} m")   # 2.10 m

# Slab — 200 mm concrete floor deck
slab = Slab.rectangular(x=0, y=0, width=10, depth=8,
                         thickness=0.2, elevation=0.0)

# Ramp — 1:12 accessible ramp (≈ 4.8° slope)
ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                      slope_angle=math.radians(4.76),
                      bottom_level_index=0, top_level_index=1)

# Elevator — 1.1 × 1.4 m cab, 0 → 3
elevator = Elevator.rectangular(x=8, y=0, cab_width=1.1, cab_depth=1.4,
                                 bottom_level_index=0, top_level_index=3)

# Structural beam — 300 mm wide, 500 mm deep, top at 3.5 m
beam = Beam.straight(x1=0, y1=0, x2=6, y2=0,
                     width=0.3, depth=0.5, elevation=3.5,
                     section=BeamSection.RECTANGULAR)
print(f"Span: {beam.span:.1f} m, soffit: {beam.soffit_elevation:.2f} m")

# Assemble
ground = (
    Level(index=0, elevation=0.0, floor_height=3.0)
    .add_staircase(stair)
    .add_slab(slab)
    .add_ramp(ramp)
    .add_beam(beam)
)
building = Building().add_level(ground).add_elevator(elevator)
```

### Structural grid and wall joining

```python
from archit_app import StructuralGrid, Wall, join_walls, miter_join, Point2D, WORLD

# Create a 3 × 3 regular grid at 6 m spacing
grid = StructuralGrid.regular(
    x_spacing=6.0, y_spacing=6.0,
    x_count=3, y_count=3,
)

# Query intersections
pt = grid.intersection("2", "B")   # grid point at column 2, row B
print(pt)                           # Point2D(x=6.0, y=6.0, ...)

# Snap a point to the nearest grid intersection
p = Point2D(x=5.95, y=6.1, crs=WORLD)
snapped = grid.snap_to_grid(p, tolerance=0.2)

# Attach grid to a building
building = Building().with_grid(grid)

# Clean up wall corners with miter joins
wall_h = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
wall_v = Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0)

wall_h_trimmed, wall_v_trimmed = miter_join(wall_h, wall_v)

# Or join a whole room's worth of walls at once
walls = [
    Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0),
    Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0),
    Wall.straight(5, 4, 0, 4, thickness=0.2, height=3.0),
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),
]
joined_walls = join_walls(walls)
```

### NURBS curved walls

```python
import math
from archit_app import Point2D, WORLD
from archit_app.geometry.curve import NURBSCurve
from archit_app import Wall

# Smooth cubic curve through 5 control points (clamped — passes through endpoints)
ctrl = (
    Point2D(0, 0, crs=WORLD),
    Point2D(1, 2, crs=WORLD),
    Point2D(2, 0, crs=WORLD),
    Point2D(3, 2, crs=WORLD),
    Point2D(4, 0, crs=WORLD),
)
curve = NURBSCurve.clamped_uniform(ctrl, degree=3)

# Sample 64 points along the curve (exact, not linear interpolation)
polyline = curve.to_polyline(resolution=64)
print(f"Arc length ≈ {curve.length():.3f} m")

# Exact quarter-circle arc via rational NURBS (w = cos(π/4) on the middle point)
w = math.cos(math.pi / 4)
circle_pts = (
    Point2D(1, 0, crs=WORLD),
    Point2D(1, 1, crs=WORLD),
    Point2D(0, 1, crs=WORLD),
)
quarter_circle = NURBSCurve.clamped_uniform(circle_pts, degree=2, weights=(1.0, w, 1.0))

# Use a NURBS curve as wall geometry
wall = Wall(geometry=curve.to_polygon(resolution=32), thickness=0.2, height=3.0)
```

### Coordinate conversion

```python
from archit_app import build_default_converter, SCREEN, WORLD, IMAGE, Point2D

# Build the standard viewport converter (800×600 canvas, 50 px/m)
conv = build_default_converter(
    viewport_height_px=600.0,
    pixels_per_meter=50.0,
    canvas_origin_world=(0.0, 0.0),   # world coords of canvas bottom-left
)

# Convert a screen click to a world position
screen_click = Point2D(x=400.0, y=300.0, crs=SCREEN)
world_pos = screen_click.to(WORLD, conv)
print(world_pos)   # Point2D(x=8.0, y=6.0, crs='world')

# Round-trip back to screen
back = world_pos.to(SCREEN, conv)

# IMAGE → WORLD works too — resolved via BFS through SCREEN
import numpy as np
world_pts = conv.convert(np.array([[400.0, 300.0]]), IMAGE, WORLD)

# Extend with custom spaces: register any transform and multi-hop paths
# are found automatically
from archit_app import CoordinateConverter, WGS84
conv.register(WORLD, WGS84, some_georeference_transform)
# Now IMAGE → WGS84 resolves as IMAGE → SCREEN → WORLD → WGS84
```

### Spatial analysis

```python
from archit_app.analysis.topology import build_adjacency_graph, connected_components
from archit_app.analysis.circulation import egress_report
from archit_app.analysis.area import area_by_program, area_report, AreaTarget
from archit_app.analysis.compliance import check_compliance
from archit_app.analysis.daylighting import daylight_report
from archit_app.analysis.visibility import compute_isovist, mutual_visibility

# --- Room adjacency graph (requires pip install archit-app[analysis]) ---
G = build_adjacency_graph(ground)
# G.nodes[room.id] = {room, centroid, area_m2, program, level_index}
# G.edges[a, b]    = {shared_length_m, distance_m, opening_ids}

components = connected_components(G)   # list of connected room groups

# --- Egress compliance ---
exit_ids = {stair_room.id, lobby_room.id}
report = egress_report(ground, exit_ids=exit_ids, max_distance_m=30.0)
# [{"room_id", "egress_distance_m", "path", "compliant"}, ...]

# --- Area program validation ---
totals = area_by_program(building)
# {"bedroom": 32.0, "kitchen": 8.0, ...}

results = area_report(building, targets=[
    AreaTarget(program="bedroom", target_m2=30.0, tolerance_fraction=0.10),
    AreaTarget(program="kitchen", target_m2=10.0),
])
# [ProgramAreaResult(program, actual_m2, target_m2, deviation_fraction, compliant), ...]

# --- Zoning compliance ---
compliance = check_compliance(building, land)
print(compliance.summary())
# Compliance report — PASS
#   [PASS] Floor Area Ratio (FAR): 0.16  (limit: 0.5)
#   [PASS] Building height: 3.0 m  (limit: 10.0 m)
#   [PASS] Footprint within lot boundary: yes
#   [PASS] Footprint within setback envelope: yes

# --- Daylighting ---
daylight = daylight_report(ground, north_angle_deg=15.0)
for r in daylight:
    print(f"{r.room_name}: WFR={r.window_to_floor_ratio:.2f}, "
          f"solar_score={r.avg_solar_score:.2f}")

# --- Isovist (visibility polygon) ---
from archit_app import Point2D, WORLD
vp = Point2D(x=5.0, y=3.0, crs=WORLD)
result = compute_isovist(vp, ground, resolution=360, max_range=20.0)
print(f"Visible area: {result.area_m2:.1f} m²")

# Line-of-sight check
can_see = mutual_visibility(Point2D(x=2, y=2, crs=WORLD),
                             Point2D(x=8, y=2, crs=WORLD), ground)
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
├── geometry/     Layer 1 — CRS, points, vectors, transforms, polygons, curves,
│                            CoordinateConverter, build_default_converter
├── elements/     Layer 2 — Wall, Room, Opening, Column, Staircase, Slab,
│                            Ramp, Elevator, Beam, wall_join utilities
├── building/     Layer 3 — Land, Setbacks, ZoningInfo, Level, Building,
│                            SiteContext, StructuralGrid
├── analysis/     Layer 6 — topology, circulation, area, compliance,
│                            daylighting, visibility
├── io/           Layer 5 — JSON, SVG, GeoJSON, DXF (read+write), IFC export
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
| Layer 2 — Elements (core) | Done | Wall, Room, Opening, Column |
| Layer 2 — Elements (vertical circulation) | Done | Staircase, Ramp, Elevator |
| Layer 2 — Elements (structural) | Done | Slab, Beam, StructuralGrid |
| Layer 2 — Wall joining | Done | `miter_join`, `butt_join`, `join_walls` |
| Layer 3 — Building | Done | Level, Building, SiteContext, Land, Setbacks, ZoningInfo |
| Layer 5 — I/O | Done | JSON, SVG, GeoJSON, DXF, IFC 4.x |
| Layer 6 — Analysis | Done | Topology graph, egress, area validation, zoning compliance, daylighting, isovist |
| CoordinateConverter | Done | Graph-based multi-CRS path-finding converter; `Point2D.to()` |
| NURBS evaluator | Done | Full Cox–de Boor evaluation; `clamped_uniform()` factory; exact conic sections |
| IFC export | Done | IFC 4.x write via ifcopenshell; walls, rooms, doors, columns, slabs, stairs |
| DXF import | Planned | Round-trip DXF support |
| PDF / raster export | Planned | Print-ready output at specified DPI/scale |
| Layer 4 — Image | Planned | Panorama, rectification, camera calibration |

---

## Contributing

Contributions are welcome. See [CONTRIBUTING](docs/contributing.md) for setup instructions and coding standards.

---

## License

MIT
