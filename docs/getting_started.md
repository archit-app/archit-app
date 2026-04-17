# Getting Started

## Installation

Install the core package:

```bash
pip install archit-app
```

Install with DXF support:

```bash
pip install "archit-app[io]"
```

Install with PNG raster export (Pillow):

```bash
pip install "archit-app[image]"
```

Install with PDF export (reportlab):

```bash
pip install "archit-app[pdf]"
```

Install with IFC export (ifcopenshell):

```bash
pip install "archit-app[ifc]"
```

Install with graph-based analysis (networkx):

```bash
pip install "archit-app[analysis]"
```

Install everything:

```bash
pip install "archit-app[io,image,pdf,ifc,analysis]"
```

**Requirements:** Python 3.11+, pydantic ≥ 2.0, shapely ≥ 2.0, numpy ≥ 1.26

---

## A minimal floorplan

One room, four walls, a door, and one SVG export.

```python
from archit_app import (
    Wall, Room, Level, Building,
    Opening, Polygon2D, WORLD,
)
from archit_app.io.svg import save_level_svg

boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
room = Room(boundary=boundary, name="Living Room", program="living")

walls = [
    Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0),  # south
    Wall.straight(6, 0, 6, 4, thickness=0.2, height=3.0),  # east
    Wall.straight(6, 4, 0, 4, thickness=0.2, height=3.0),  # north
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),  # west
]
door = Opening.door(x=2.5, y=0, width=0.9, height=2.1)
walls[0] = walls[0].add_opening(door)

level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
level = level.add_room(room)
for w in walls:
    level = level.add_wall(w)

building = Building().with_metadata(name="My House").add_level(level)

save_level_svg(level, "ground_floor.svg", pixels_per_meter=50)
print(building)
```

---

## Adding furniture and annotations

```python
from archit_app import Furniture, DimensionLine, TextAnnotation, SectionMark

level = (
    level
    .add_furniture(Furniture.queen_bed(x=1.0, y=0.5))
    .add_furniture(Furniture.wardrobe(x=4.5, y=0.2, width=1.2))
    .add_dimension(DimensionLine.horizontal(x1=0, x2=6, y=4.5))
    .add_text_annotation(TextAnnotation.room_label(room))
    .add_section_mark(SectionMark.horizontal(x1=0, x2=6, y=2.0, tag="A"))
)
```

---

## A multi-level building

```python
from archit_app import Level, Building, Wall, Room, Polygon2D, WORLD

def make_level(index: int, elevation: float) -> Level:
    boundary = Polygon2D.rectangle(0, 0, 10, 8, crs=WORLD)
    room = Room(boundary=boundary, name="Open Plan", level_index=index)
    lv = Level(index=index, elevation=elevation, floor_height=3.0)
    return (
        lv.add_room(room)
        .add_wall(Wall.straight(0, 0, 10, 0, thickness=0.3, height=3.0))
        .add_wall(Wall.straight(10, 0, 10, 8, thickness=0.3, height=3.0))
        .add_wall(Wall.straight(10, 8, 0, 8, thickness=0.3, height=3.0))
        .add_wall(Wall.straight(0, 8, 0, 0, thickness=0.3, height=3.0))
    )

building = Building().with_metadata(name="Office Block", architect="A. Architect")
for i in range(5):
    building = building.add_level(make_level(i, elevation=i * 3.2))

print(building)
# Building(name='Office Block', levels=5, gross_area=400.0m²)
```

---

## Saving and loading

```python
from archit_app.io.json_schema import save_building, load_building

save_building(building, "project.archit_app.json")
restored = load_building("project.archit_app.json")

assert restored.metadata.name == building.metadata.name
assert len(restored.levels) == len(building.levels)
```

---

## Vertical circulation and structure

```python
import math
from archit_app import Staircase, Slab, Ramp, Elevator, Beam, BeamSection

stair = Staircase.straight(
    x=0, y=0, width=1.2, rise_count=12,
    rise_height=0.175, run_depth=0.28,
    bottom_level_index=0, top_level_index=1,
)
print(f"Total rise: {stair.total_rise:.2f} m")

slab = Slab.rectangular(x=0, y=0, width=10, depth=8, thickness=0.2, elevation=0.0)

ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                     slope_angle=math.radians(4.76))

elevator = Elevator.rectangular(x=8, y=0, cab_width=1.1, cab_depth=1.4,
                                 bottom_level_index=0, top_level_index=3)

beam = Beam.straight(x1=0, y1=0, x2=6, y2=0, width=0.3, depth=0.5, elevation=3.5)

level = (
    Level(index=0, elevation=0.0, floor_height=3.0)
    .add_staircase(stair)
    .add_slab(slab)
    .add_ramp(ramp)
    .add_beam(beam)
)
building = Building().add_level(level).add_elevator(elevator)
```

---

## Land parcel and zoning

```python
from archit_app import Land, Setbacks, ZoningInfo

land = (
    Land.from_latlon([
        (37.7749, -122.4194),
        (37.7750, -122.4194),
        (37.7750, -122.4183),
        (37.7749, -122.4183),
    ], address="123 Main St, San Francisco, CA")
    .with_setbacks(Setbacks(front=3.0, back=6.0, left=1.5, right=1.5))
    .with_zoning(ZoningInfo(
        zone_code="RH-2",
        max_height_m=10.0,
        max_far=1.8,
        max_lot_coverage=0.6,
        allowed_uses=("residential",),
    ))
)

print(f"Lot area: {land.area_m2:.1f} m²")
print(f"Buildable area: {land.buildable_area_m2:.1f} m²")
print(f"Max GFA: {land.max_floor_area_m2:.1f} m²")

# Pass to an AI agent
context = land.to_agent_context()

# Attach to building
building = Building().with_land(land)
```

---

## Structural grid and wall joining

```python
from archit_app import StructuralGrid, Wall, join_walls, Point2D, WORLD

grid = StructuralGrid.regular(x_spacing=6.0, y_spacing=6.0, x_count=3, y_count=3)
pt = grid.intersection("2", "B")    # Point2D(x=6.0, y=6.0)

p = Point2D(x=5.95, y=6.1, crs=WORLD)
snapped = grid.snap_to_grid(p, tolerance=0.2)

walls = [
    Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0),
    Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0),
    Wall.straight(5, 4, 0, 4, thickness=0.2, height=3.0),
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),
]
joined = join_walls(walls)
```

---

## Spatial analysis

```python
from archit_app.analysis.topology import build_adjacency_graph
from archit_app.analysis.circulation import egress_report
from archit_app.analysis.area import area_report, AreaTarget
from archit_app.analysis.compliance import check_compliance
from archit_app.analysis.daylighting import daylight_report
from archit_app.analysis.visibility import compute_isovist

G = build_adjacency_graph(level)       # requires archit-app[analysis]
report = egress_report(level, exit_ids={stair.id})
results = area_report(building, targets=[AreaTarget(program="bedroom", target_m2=30.0)])
compliance = check_compliance(building, land)
daylight = daylight_report(level, north_angle_deg=15.0)

from archit_app import Point2D, WORLD
isovist = compute_isovist(Point2D(x=3.0, y=2.0, crs=WORLD), level)
print(f"Visible area: {isovist.area_m2:.1f} m²")
```

---

## Coordinate conversion

```python
from archit_app import build_default_converter, SCREEN, WORLD, Point2D

conv = build_default_converter(viewport_height_px=600, pixels_per_meter=50)

click = Point2D(x=400, y=300, crs=SCREEN)
world_pt = click.to(WORLD, conv)
```

---

## Working with curves

```python
import math
from archit_app import ArcCurve, BezierCurve, Wall, Point2D, WORLD
from archit_app.geometry.curve import NURBSCurve

# Arc wall
arc = ArcCurve(center=Point2D(x=5, y=5, crs=WORLD), radius=4.0,
               start_angle=0.0, end_angle=math.pi / 2, crs=WORLD)
arc_wall = Wall(geometry=arc, thickness=0.2, height=3.0)

# Cubic NURBS wall
ctrl = tuple(Point2D(x=i, y=math.sin(i), crs=WORLD) for i in range(5))
curve = NURBSCurve.clamped_uniform(ctrl, degree=3)
```

---

## Next steps

- [Core Concepts](concepts.md) — coordinate systems, immutability, the element model
- [API Reference — Geometry](api/geometry.md)
- [API Reference — Elements](api/elements.md)
- [API Reference — Building](api/building.md)
- [API Reference — I/O](api/io.md)
