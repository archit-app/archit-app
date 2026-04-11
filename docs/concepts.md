# Core Concepts

## Coordinate systems

`floorplan` uses a **Y-up, meters** world coordinate system — the standard architectural convention. This is intentional: architects think in Y-up. Screen and image coordinate systems are Y-down; the library handles the flip at export boundaries so geometry code never needs to think about it.

### The five spaces

| Singleton | Name         | Origin     | Y direction | Unit   | Typical use                       |
|-----------|--------------|------------|-------------|--------|-----------------------------------|
| `WORLD`   | `"world"`    | site datum | up          | meters | all architectural geometry        |
| `SCREEN`  | `"screen"`   | top-left   | down        | pixels | rendering, UI mouse events        |
| `IMAGE`   | `"image"`    | top-left   | down        | pixels | raster images, panoramas          |
| `WGS84`   | `"geographic"` | lat/lon  | up          | meters | GIS / site georeferencing         |

Import these singletons directly:

```python
from floorplan import WORLD, SCREEN, IMAGE, WGS84
```

### CRS tagging

Every `Point2D` and `Vector2D` carries its `CoordinateSystem`. Any arithmetic between two objects in different spaces raises `CRSMismatchError` immediately — before any wrong-answer bugs can propagate silently.

```python
from floorplan import Point2D, WORLD, SCREEN, CRSMismatchError

p_world  = Point2D(x=1.0, y=2.0, crs=WORLD)
p_screen = Point2D(x=100, y=200, crs=SCREEN)

p_world + p_screen   # raises CRSMismatchError
```

The error message tells you exactly which spaces clashed and that you need to convert explicitly.

### Custom coordinate systems

You can create your own CRS for local or project-specific spaces:

```python
from floorplan import CoordinateSystem, LengthUnit, YDirection

LOCAL = CoordinateSystem(
    name="apartment_3B",
    unit=LengthUnit.METERS,
    y_direction=YDirection.UP,
)
```

CRS identity is determined by `(name, unit, y_direction)`.

---

## Immutability

All models — geometry, elements, levels, and buildings — are **immutable** (Pydantic frozen models). You cannot modify an object in place. Every "mutation" method returns a new object:

```python
level = Level(index=0, elevation=0.0, floor_height=3.0)
level2 = level.add_wall(my_wall)   # returns a new Level; level is unchanged
```

This design makes undo/redo, history, and serialization straightforward, and eliminates an entire class of aliasing bugs.

### Functional update pattern

The standard pattern for building up objects:

```python
building = (
    Building()
    .with_metadata(name="Tower A", architect="Studio X")
    .add_level(ground_floor)
    .add_level(first_floor)
    .with_site(site_context)
)
```

Each call returns a new `Building`. The original is not modified.

---

## The Element model

All architectural objects (`Wall`, `Room`, `Opening`, `Column`) inherit from `Element`:

```
Element
├── id: UUID          — auto-generated, unique per object
├── tags: dict        — arbitrary key/value metadata
├── transform: Transform2D — local-to-world affine transform
├── layer: str        — drawing layer name
└── crs: CoordinateSystem  — coordinate space for this element
```

### Tags

Tags are free-form key/value metadata. Use them for material references, fire ratings, program codes, or any domain-specific attribute that doesn't belong in the core schema:

```python
wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
wall = wall.with_tag("material", "brick").with_tag("fire_rating", "REI 60")

print(wall.tags)
# {'material': 'brick', 'fire_rating': 'REI 60'}
```

### Layers

The `layer` field maps to drawing layers in DXF export and can be used for selective rendering. Default is `"default"`.

```python
wall = wall.on_layer("structural")
```

---

## Transform2D

`Transform2D` wraps a 3×3 homogeneous matrix for 2D affine transforms. It is immutable and composed with `@`:

```python
from floorplan import Transform2D
import math

t = (
    Transform2D.translate(2.0, 3.0)
    @ Transform2D.rotate(math.pi / 4)
    @ Transform2D.scale(1.5, 1.5)
)

# Apply to a Point2D
from floorplan import Point2D, WORLD
p = Point2D(x=1.0, y=0.0, crs=WORLD)
p2 = p.transformed(t)
```

Convention: `(T1 @ T2)` applies `T2` first, then `T1`. This matches the standard mathematical convention for function composition.

---

## Wall geometry types

Walls accept three geometry types as their centre-line or face representation:

| Type | Use |
|------|-----|
| `Polygon2D` | Straight wall represented as a rectangular polygon (most common) |
| `ArcCurve` | Curved wall following a circular arc |
| `BezierCurve` | Curved wall following a Bézier spline |
| `NURBSCurve` | Curved wall following a NURBS curve |

When a `Polygon2D` is used, it represents the full wall face (box). When a curve is used, it represents the wall centre line, and `thickness` defines the total wall width (centred on the curve).

The `Wall.straight()` factory automatically builds the correct `Polygon2D` from two endpoints.

---

## Polygon2D and holes

`Polygon2D` supports holes — arbitrary sub-polygons cut out of the boundary. This is used for:

- `Room.holes` — structural voids, columns, courtyards within a room
- Complex wall shapes with openings (for SVG export)

```python
from floorplan import Polygon2D, Point2D, WORLD

# A room with a service shaft void
outer = Polygon2D.rectangle(0, 0, 10, 8, crs=WORLD)
shaft = Polygon2D.rectangle(4, 3, 2, 2, crs=WORLD)
room = Room(boundary=outer, holes=(shaft,), name="Open Plan")

print(f"Net area: {room.area:.1f} m²")     # 80.0 - 4.0 = 76.0
print(f"Gross area: {room.gross_area:.1f} m²")  # 80.0
```

---

## Units

All values are stored in **meters** internally. Import and export functions accept a `unit` parameter (planned for future releases). Never store values in other units inside the model — convert at the boundary.

```python
from floorplan import LengthUnit

feet_value = 10.0
meters = LengthUnit.FEET.to_meters(feet_value)   # 3.048

meters_value = 3.0
feet = LengthUnit.FEET.from_meters(meters_value)  # 9.84...
```

---

## Building hierarchy

```
SiteContext           optional lot/geographic context
└── Building          metadata + ordered list of levels
    └── Level         one floor: index, elevation, floor_height
        ├── walls:    tuple[Wall, ...]
        ├── rooms:    tuple[Room, ...]
        ├── openings: tuple[Opening, ...]   (level-standalone)
        └── columns:  tuple[Column, ...]
```

`Level.index` is the floor number: 0 = ground floor, negative = basements, positive = upper floors. Levels inside a `Building` are kept sorted by index automatically.
