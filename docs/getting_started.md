# Getting Started

## Installation

Install the core package:

```bash
pip install floorplan
```

Install with optional I/O extras (DXF and SVG via `ezdxf`/`svgwrite`):

```bash
pip install "floorplan[io]"
```

Install with image support (coming soon):

```bash
pip install "floorplan[image]"
```

Install with graph-based analysis (coming soon):

```bash
pip install "floorplan[analysis]"
```

Install everything:

```bash
pip install "floorplan[io,image,analysis]"
```

**Requirements:** Python 3.11+, pydantic ≥ 2.0, shapely ≥ 2.0, numpy ≥ 1.26

---

## A minimal floorplan

The simplest useful program: one room, four walls, a door, and one SVG export.

```python
from floorplan import (
    Wall, Room, Level, Building,
    Opening, Polygon2D, WORLD,
)
from floorplan.io.svg import save_level_svg

# Room boundary — 6 m × 4 m rectangle, lower-left at origin
boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
room = Room(boundary=boundary, name="Living Room", program="living")

# Four perimeter walls, 200 mm thick, 3 m high
walls = [
    Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0),  # south
    Wall.straight(6, 0, 6, 4, thickness=0.2, height=3.0),  # east
    Wall.straight(6, 4, 0, 4, thickness=0.2, height=3.0),  # north
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),  # west
]

# Punch a door into the south wall
door = Opening.door(x=2.5, y=0, width=0.9, height=2.1)
walls[0] = walls[0].add_opening(door)

# Assemble level and building
level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")
level = level.add_room(room)
for w in walls:
    level = level.add_wall(w)

building = Building().with_metadata(name="My House").add_level(level)

# Export
save_level_svg(level, "ground_floor.svg", pixels_per_meter=50)
print("Saved ground_floor.svg")
print(building)
```

---

## A multi-level building

```python
from floorplan import Level, Building, Wall, Room, Polygon2D, WORLD

def make_level(index: int, elevation: float) -> Level:
    boundary = Polygon2D.rectangle(0, 0, 10, 8, crs=WORLD)
    room = Room(boundary=boundary, name=f"Open Plan", level_index=index)
    north = Wall.straight(0, 8, 10, 8, thickness=0.3, height=3.0)
    south = Wall.straight(0, 0, 10, 0, thickness=0.3, height=3.0)
    east  = Wall.straight(10, 0, 10, 8, thickness=0.3, height=3.0)
    west  = Wall.straight(0, 0, 0, 8, thickness=0.3, height=3.0)
    lv = Level(index=index, elevation=elevation, floor_height=3.0)
    lv = lv.add_room(room).add_wall(north).add_wall(south).add_wall(east).add_wall(west)
    return lv

building = Building().with_metadata(name="Office Block", architect="A. Architect")
for i in range(5):
    building = building.add_level(make_level(i, elevation=i * 3.2))

print(building)
# Building(name='Office Block', levels=5, gross_area=400.0m²)
print(f"Total floors: {building.total_floors}")
```

---

## Saving and loading

```python
from floorplan.io.json_schema import save_building, load_building

save_building(building, "office_block.floorplan.json")
restored = load_building("office_block.floorplan.json")

assert restored.metadata.name == building.metadata.name
assert len(restored.levels) == len(building.levels)
```

---

## Working with curves

`floorplan` supports non-Manhattan geometry via arc and Bézier walls.

```python
from floorplan import ArcCurve, BezierCurve, Wall, Point2D, WORLD
import math

# A curved (arc) wall
arc_geom = ArcCurve(
    center=Point2D(x=5.0, y=5.0, crs=WORLD),
    radius=4.0,
    start_angle=0.0,
    end_angle=math.pi / 2,
    crs=WORLD,
)
arc_wall = Wall(geometry=arc_geom, thickness=0.2, height=3.0)

# A Bézier wall
bezier_geom = BezierCurve(
    control_points=(
        Point2D(x=0, y=0, crs=WORLD),
        Point2D(x=2, y=4, crs=WORLD),
        Point2D(x=6, y=4, crs=WORLD),
        Point2D(x=8, y=0, crs=WORLD),
    ),
    crs=WORLD,
)
bezier_wall = Wall(geometry=bezier_geom, thickness=0.15, height=2.8)
```

---

## Next steps

- [Core Concepts](concepts.md) — understand coordinate systems, immutability, and the element model
- [API Reference — Geometry](api/geometry.md)
- [API Reference — Elements](api/elements.md)
- [API Reference — I/O](api/io.md)
