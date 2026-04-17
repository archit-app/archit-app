# API Reference — Elements

```python
from archit_app import (
    Element,
    Wall, WallType,
    Room,
    Opening, OpeningKind, SwingGeometry, Frame,
    Column, ColumnShape,
    Staircase,
    Slab, SlabType,
    Ramp,
    Elevator, ElevatorDoor,
    Beam, BeamSection,
    Furniture, FurnitureCategory,
    TextAnnotation, DimensionLine, SectionMark,
    miter_join, butt_join, join_walls,
)
```

All elements are **immutable** Pydantic models. "Mutation" methods return new objects.

---

## Element (base class)

```python
class Element(BaseModel, frozen=True):
    id: UUID                        # auto-generated UUID
    tags: dict[str, Any] = {}       # arbitrary key/value metadata
    transform: Transform2D          # local-to-world affine transform
    layer: str = "default"          # drawing layer name
    crs: CoordinateSystem = WORLD   # coordinate space for this element
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `e.with_tag(key, value)` | `Element` | Copy with an added/updated tag |
| `e.without_tag(key)` | `Element` | Copy with a tag removed |
| `e.with_transform(t)` | `Element` | Copy with transform composed on top |
| `e.on_layer(name)` | `Element` | Copy assigned to a different layer |

---

## Wall

```python
class Wall(Element):
    geometry: Polygon2D | ArcCurve | BezierCurve | NURBSCurve
    thickness: float      # total wall thickness in meters (must be > 0)
    height: float         # floor-to-ceiling height in meters (must be > 0)
    wall_type: WallType = WallType.INTERIOR
    openings: tuple[Opening, ...] = ()
    material: str | None = None
```

When `geometry` is a `Polygon2D`, it represents the full wall face (box representation). When it is a curve, it represents the centre line and `thickness` defines the total width centred on the curve.

### WallType

```python
class WallType(str, Enum):
    EXTERIOR   = "exterior"
    INTERIOR   = "interior"
    CURTAIN    = "curtain"
    SHEAR      = "shear"
    PARTY      = "party"      # shared wall with neighbouring building
    RETAINING  = "retaining"
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `wall.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |
| `wall.add_opening(opening)` | `Wall` | New wall with the opening added |
| `wall.remove_opening(opening_id)` | `Wall` | New wall with the opening removed |

### Factory: `Wall.straight`

```python
Wall.straight(
    x1, y1, x2, y2,
    thickness: float = 0.2,
    height: float = 3.0,
    wall_type: WallType = WallType.INTERIOR,
    **kwargs,
) -> Wall
```

Creates a straight wall from two endpoints as a rectangular `Polygon2D` offset `thickness/2` on each side.

---

## Room

```python
class Room(Element):
    boundary: Polygon2D
    holes: tuple[Polygon2D, ...] = ()
    name: str = ""
    program: str = ""        # e.g. "bedroom", "kitchen", "corridor"
    level_index: int = 0
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `room.area` | `float` | Net floor area in m² (boundary minus holes) |
| `room.gross_area` | `float` | Boundary area ignoring holes |
| `room.perimeter` | `float` | Outer boundary perimeter in meters |
| `room.centroid` | `Point2D` | Centroid of the outer boundary |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `room.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |
| `room.contains_point(p)` | `bool` | True if point is inside room (excluding holes) |
| `room.add_hole(poly)` | `Room` | New room with an additional void |
| `room.with_name(name)` | `Room` | New room with updated name |
| `room.with_program(program)` | `Room` | New room with updated program |

---

## Opening

```python
class Opening(Element):
    kind: OpeningKind
    geometry: Polygon2D
    width: float           # nominal clear width in meters (> 0)
    height: float          # nominal clear height in meters (> 0)
    sill_height: float = 0.0   # floor-to-bottom of opening (≥ 0)
    swing: SwingGeometry | None = None
    frame: Frame | None = None
```

### OpeningKind

```python
class OpeningKind(str, Enum):
    DOOR         = "door"
    WINDOW       = "window"
    ARCHWAY      = "archway"
    PASS_THROUGH = "pass_through"
```

### Factories

#### `Opening.door`

```python
Opening.door(x, y, width=0.9, height=2.1, wall_thickness=0.2, **kwargs) -> Opening
```

Standard rectangular door. `x, y` is the lower-left corner in world space. `sill_height` defaults to `0.0`.

#### `Opening.window`

```python
Opening.window(x, y, width=1.2, height=1.2, sill_height=0.9, wall_thickness=0.2, **kwargs) -> Opening
```

Standard rectangular window with a sill.

> **Note:** `Opening.archway()` and `Opening.pass_through()` factories are planned (P8 item 27) but not yet implemented.

---

## Column

```python
class Column(Element):
    geometry: Polygon2D
    height: float
    shape: ColumnShape = ColumnShape.CUSTOM
    material: str | None = None
```

### ColumnShape

```python
class ColumnShape(str, Enum):
    RECTANGULAR = "rectangular"
    CIRCULAR    = "circular"
    CUSTOM      = "custom"
```

### Factories

```python
Column.rectangular(x, y, width, depth, height=3.0, **kwargs) -> Column
Column.circular(center_x, center_y, diameter, height=3.0, resolution=32, **kwargs) -> Column
```

`x, y` is the lower-left corner for rectangular columns. `resolution` controls the polygon approximation for circular columns.

---

## Staircase

```python
class Staircase(Element):
    geometry: Polygon2D        # plan outline of the stair flight
    width: float               # stair width in meters
    rise_count: int            # number of risers
    rise_height: float         # height of each riser in meters
    run_depth: float           # horizontal depth of each tread in meters
    direction: float = 0.0     # flight bearing in radians (0 = +Y)
    bottom_level_index: int = 0
    top_level_index: int = 1
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `stair.total_rise` | `float` | `rise_count × rise_height` in meters |
| `stair.total_run` | `float` | `rise_count × run_depth` in meters |
| `stair.slope_angle` | `float` | Angle of flight in radians |

### Factory: `Staircase.straight`

```python
Staircase.straight(
    x, y,
    width: float,
    rise_count: int,
    rise_height: float = 0.175,
    run_depth: float = 0.28,
    direction: float = 0.0,
    bottom_level_index: int = 0,
    top_level_index: int = 1,
    **kwargs,
) -> Staircase
```

Creates a straight stair flight with its plan outline computed automatically.

**Example:**

```python
stair = Staircase.straight(
    x=0, y=0, width=1.2, rise_count=12,
    rise_height=0.175, run_depth=0.28,
    bottom_level_index=0, top_level_index=1,
)
print(f"Total rise: {stair.total_rise:.2f} m")   # 2.10 m
print(f"Slope: {math.degrees(stair.slope_angle):.1f}°")
```

---

## Slab

```python
class Slab(Element):
    geometry: Polygon2D        # outline of the slab in plan
    thickness: float           # slab thickness in meters
    elevation: float           # top face elevation above site datum
    slab_type: SlabType = SlabType.FLOOR
    holes: tuple[Polygon2D, ...] = ()   # penetrations (e.g. stair openings)
    material: str | None = None
```

### SlabType

```python
class SlabType(str, Enum):
    FLOOR   = "floor"
    CEILING = "ceiling"
    ROOF    = "roof"
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `slab.area` | `float` | Net slab area minus holes, m² |
| `slab.gross_area` | `float` | Outer boundary area, m² |
| `slab.perimeter` | `float` | Outer boundary perimeter, m |

### Factory: `Slab.rectangular`

```python
Slab.rectangular(
    x, y, width, depth,
    thickness: float = 0.2,
    elevation: float = 0.0,
    slab_type: SlabType = SlabType.FLOOR,
    **kwargs,
) -> Slab
```

---

## Ramp

```python
class Ramp(Element):
    geometry: Polygon2D        # plan outline
    width: float               # ramp width in meters
    length: float              # horizontal run length in meters
    slope_angle: float         # slope in radians (positive = uphill in direction)
    direction: float = 0.0     # bearing in radians (0 = +Y)
    bottom_level_index: int = 0
    top_level_index: int = 1
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `ramp.slope_percent` | `float` | Rise/run × 100 |
| `ramp.total_rise` | `float` | `length × tan(slope_angle)` in meters |

### Factory: `Ramp.straight`

```python
Ramp.straight(
    x, y, width, length,
    slope_angle: float,
    direction: float = 0.0,
    bottom_level_index: int = 0,
    top_level_index: int = 1,
    **kwargs,
) -> Ramp
```

**Example:**

```python
import math
ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                     slope_angle=math.radians(4.76))   # approx 1:12
print(f"Slope: {ramp.slope_percent:.1f}%")   # 8.3 %
```

---

## Elevator

```python
class Elevator(Element):
    shaft_geometry: Polygon2D      # shaft outline in plan
    cab_width: float               # interior cab width in meters
    cab_depth: float               # interior cab depth in meters
    bottom_level_index: int = 0
    top_level_index: int = 1
    doors: tuple[ElevatorDoor, ...] = ()
```

### ElevatorDoor

```python
class ElevatorDoor(Element):
    level_index: int
    geometry: Polygon2D
    width: float
    height: float = 2.1
```

### Factory: `Elevator.rectangular`

```python
Elevator.rectangular(
    x, y,
    cab_width: float = 1.1,
    cab_depth: float = 1.4,
    shaft_clearance: float = 0.15,
    bottom_level_index: int = 0,
    top_level_index: int = 1,
    **kwargs,
) -> Elevator
```

Creates an elevator with a rectangular shaft outline enlarged by `shaft_clearance` on each side.

---

## Beam

```python
class Beam(Element):
    geometry: Polygon2D        # plan outline (footprint)
    width: float               # beam width in meters
    depth: float               # beam depth (structural depth) in meters
    elevation: float           # top face elevation above site datum
    section: BeamSection = BeamSection.RECTANGULAR
    material: str | None = None
```

### BeamSection

```python
class BeamSection(str, Enum):
    RECTANGULAR = "rectangular"
    I_SECTION   = "i_section"
    T_SECTION   = "t_section"
    CIRCULAR    = "circular"
    CUSTOM      = "custom"
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `beam.span` | `float` | Centre-line length in meters |
| `beam.soffit_elevation` | `float` | `elevation - depth` |

### Factory: `Beam.straight`

```python
Beam.straight(
    x1, y1, x2, y2,
    width: float = 0.3,
    depth: float = 0.5,
    elevation: float = 3.0,
    section: BeamSection = BeamSection.RECTANGULAR,
    **kwargs,
) -> Beam
```

---

## Furniture

```python
class Furniture(Element):
    footprint: Polygon2D
    label: str = ""
    category: FurnitureCategory = FurnitureCategory.OTHER
    width: float = 0.0
    depth: float = 0.0
    height: float | None = None
```

### FurnitureCategory

```python
class FurnitureCategory(str, Enum):
    SOFA, ARMCHAIR, DINING_CHAIR, OFFICE_CHAIR,
    DINING_TABLE, COFFEE_TABLE, DESK, BED,
    WARDROBE, BOOKSHELF, TV_UNIT,
    KITCHEN_COUNTER, KITCHEN_ISLAND,
    BATHTUB, SHOWER, TOILET, SINK, WASHING_MACHINE,
    STORAGE, OTHER
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `f.footprint_area` | `float` | Plan area in m² |

### `bounding_box() → BoundingBox2D`

### Factories (named)

All factories take `x, y` (lower-left corner) plus optional `label`, `height`, `**kwargs`.

| Factory | Defaults (w × d) |
|---------|-----------------|
| `Furniture.sofa(x, y)` | 2.0 × 0.9 m |
| `Furniture.armchair(x, y)` | 0.85 × 0.85 m |
| `Furniture.dining_chair(x, y)` | 0.45 × 0.45 m |
| `Furniture.office_chair(x, y)` | circular, ∅ 0.6 m |
| `Furniture.dining_table(x, y, seats=4)` | 1.6 × 0.9 m (4) / 2.4 × 0.9 m (6+) |
| `Furniture.coffee_table(x, y)` | 1.2 × 0.6 m |
| `Furniture.round_table(x, y, diameter=1.0)` | circular |
| `Furniture.desk(x, y)` | 1.4 × 0.7 m |
| `Furniture.single_bed(x, y)` | 0.9 × 2.0 m |
| `Furniture.double_bed(x, y)` | 1.4 × 2.0 m |
| `Furniture.queen_bed(x, y)` | 1.6 × 2.0 m |
| `Furniture.king_bed(x, y)` | 1.8 × 2.0 m |
| `Furniture.wardrobe(x, y, width=1.2)` | width × 0.6 m |
| `Furniture.bookshelf(x, y, width=0.9)` | width × 0.3 m |
| `Furniture.tv_unit(x, y, width=1.5)` | width × 0.45 m |
| `Furniture.kitchen_counter(x, y, width=2.4)` | width × 0.6 m |
| `Furniture.kitchen_island(x, y)` | 1.2 × 0.9 m |
| `Furniture.bathtub(x, y)` | 1.7 × 0.75 m |
| `Furniture.shower(x, y)` | 0.9 × 0.9 m |
| `Furniture.toilet(x, y)` | 0.37 × 0.72 m |
| `Furniture.sink(x, y)` | 0.6 × 0.5 m |
| `Furniture.washing_machine(x, y)` | 0.6 × 0.6 m |

**Example:**

```python
bed   = Furniture.queen_bed(x=1.0, y=0.5)
desk  = Furniture.desk(x=3.5, y=0.5)
chair = Furniture.office_chair(x=3.7, y=1.2)

level = level.add_furniture(bed).add_furniture(desk).add_furniture(chair)
```

---

## TextAnnotation

```python
class TextAnnotation(Element):
    position: Point2D
    text: str
    rotation: float = 0.0          # radians counter-clockwise
    size: float = 0.25             # approximate text height in meters
    anchor: Literal["center", "left", "right", "top", "bottom"] = "center"
```

### Factories

```python
TextAnnotation.note(x, y, text, *, rotation=0.0, size=0.2, **kwargs) -> TextAnnotation
TextAnnotation.room_label(room, **kwargs) -> TextAnnotation
```

`room_label()` positions the annotation at the room centroid with `"{name}\n{area:.1f} m²"`.

---

## DimensionLine

```python
class DimensionLine(Element):
    start: Point2D
    end: Point2D
    offset: float = 0.5            # perpendicular offset of the dim line from the measured points
    label_override: str | None = None
    decimal_places: int = 2
    unit_suffix: str = "m"
```

### Computed properties

| Property | Type | Description |
|----------|------|-------------|
| `measured_distance` | `float` | `start.distance_to(end)` in meters |
| `label` | `str` | Auto-formatted distance or `label_override` |
| `midpoint` | `Point2D` | Midpoint of the measured segment |
| `direction` | `Vector2D` | Unit vector from start to end |
| `normal` | `Vector2D` | CCW perpendicular to direction |
| `dimension_line_start` | `Point2D` | Dim line endpoint above/beside `start` |
| `dimension_line_end` | `Point2D` | Dim line endpoint above/beside `end` |
| `label_position` | `Point2D` | Midpoint of the dimension line |

### Factories

```python
DimensionLine.between(start, end, offset=0.5, **kwargs) -> DimensionLine
DimensionLine.horizontal(x1, x2, y, offset=0.5, **kwargs) -> DimensionLine
DimensionLine.vertical(y1, y2, x, offset=0.5, **kwargs) -> DimensionLine
```

**Example:**

```python
dim = DimensionLine.horizontal(x1=0, x2=6, y=4.5)
print(dim.label)   # "6.00 m"
```

---

## SectionMark

```python
class SectionMark(Element):
    start: Point2D
    end: Point2D
    tag: str = "A"
    view_direction: Literal["left", "right", "both"] = "both"
    reference: str = ""            # sheet/view reference e.g. "A-101"
```

### Computed properties

| Property | Type | Description |
|----------|------|-------------|
| `length` | `float` | Cut line length in meters |
| `midpoint` | `Point2D` | Midpoint of the cut line |
| `cut_line` | `Segment2D` | Directed segment from start to end |
| `direction` | `Vector2D` | Unit vector along cut line |
| `view_vector` | `Vector2D` | Direction the viewer is looking (perpendicular to cut) |

### Factories

```python
SectionMark.horizontal(x1, x2, y, tag="A", view_direction="both", **kwargs) -> SectionMark
SectionMark.vertical(y1, y2, x, tag="A", view_direction="both", **kwargs) -> SectionMark
```

---

## Wall joining utilities

```python
from archit_app import miter_join, butt_join, join_walls
```

All three functions work only with `Polygon2D`-geometry walls (not curve walls).

### `miter_join(wall_a, wall_b) → tuple[Wall, Wall]`

Clips both walls at the angle-bisector through their shared endpoint. Both walls are shortened.

### `butt_join(wall_a, wall_b) → tuple[Wall, Wall]`

Trims `wall_b` to abut `wall_a` cleanly. `wall_a` is unchanged.

### `join_walls(walls) → list[Wall]`

Applies `miter_join` to every endpoint-sharing pair in the list. Returns the joined list.

**Example:**

```python
walls = [
    Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0),
    Wall.straight(6, 0, 6, 4, thickness=0.2, height=3.0),
    Wall.straight(6, 4, 0, 4, thickness=0.2, height=3.0),
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),
]
joined = join_walls(walls)
```
