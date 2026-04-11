# API Reference — Elements

```python
from floorplan import (
    Element,
    Wall, WallType,
    Room,
    Opening, OpeningKind, SwingGeometry, Frame,
    Column, ColumnShape,
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

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `wall.length` | `float` | Approximate wall length along centre line |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `wall.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |
| `wall.add_opening(opening)` | `Wall` | New wall with the opening added |
| `wall.remove_opening(opening_id)` | `Wall` | New wall with the opening removed |

### Factory: `Wall.straight`

```python
Wall.straight(
    x1: float, y1: float,
    x2: float, y2: float,
    thickness: float = 0.2,
    height: float = 3.0,
    wall_type: WallType = WallType.INTERIOR,
    **kwargs,
) -> Wall
```

Creates a straight wall from two endpoints. Automatically builds the correct rectangular `Polygon2D` by offsetting `thickness / 2` on each side of the centre line.

**Example:**

```python
wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
```

---

## Room

```python
class Room(Element):
    boundary: Polygon2D
    holes: tuple[Polygon2D, ...] = ()  # voids within the room
    name: str = ""
    program: str = ""        # e.g. "bedroom", "kitchen", "corridor"
    level_index: int = 0     # which Level this room belongs to
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `room.area` | `float` | Net floor area in m² (boundary minus holes) |
| `room.gross_area` | `float` | Boundary area in m², ignoring holes |
| `room.perimeter` | `float` | Outer boundary perimeter in meters |
| `room.centroid` | `Point2D` | Centroid of the outer boundary |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `room.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |
| `room.contains_point(p)` | `bool` | True if point is inside room (not inside holes) |
| `room.add_hole(poly)` | `Room` | New room with an additional void |
| `room.with_name(name)` | `Room` | New room with updated name |
| `room.with_program(program)` | `Room` | New room with updated program |

**Example:**

```python
from floorplan import Room, Polygon2D, WORLD

boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
shaft    = Polygon2D.rectangle(2, 1, 1, 1, crs=WORLD)

room = Room(boundary=boundary, name="Office", program="open_office")
room = room.add_hole(shaft)

print(f"Net area: {room.area:.1f} m²")   # 24.0 - 1.0 = 23.0
```

---

## Opening

```python
class Opening(Element):
    kind: OpeningKind
    geometry: Polygon2D    # hole shape in wall-local coordinates
    width: float           # nominal clear opening width in meters (must be > 0)
    height: float          # nominal clear opening height in meters (must be > 0)
    sill_height: float = 0.0   # floor-to-bottom of opening, meters (≥ 0)
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

### SwingGeometry

```python
class SwingGeometry(Element):
    arc: ArcCurve
    side: Literal["left", "right"] = "left"
```

Door swing arc geometry. Rendered as a dashed arc in SVG export.

### Frame

```python
class Frame(Element):
    width: float = 0.05    # frame reveal width in meters
    depth: float = 0.0     # frame projection from wall face
    material: str | None = None
```

### Factories

#### `Opening.door`

```python
Opening.door(
    x: float, y: float,
    width: float = 0.9,
    height: float = 2.1,
    wall_thickness: float = 0.2,
    **kwargs,
) -> Opening
```

Convenience factory for a standard rectangular door. `x, y` is the lower-left corner in world space.

#### `Opening.window`

```python
Opening.window(
    x: float, y: float,
    width: float = 1.2,
    height: float = 1.2,
    sill_height: float = 0.9,
    wall_thickness: float = 0.2,
    **kwargs,
) -> Opening
```

Convenience factory for a standard rectangular window.

**Example:**

```python
door   = Opening.door(x=2.0, y=0.0, width=0.9, height=2.1)
window = Opening.window(x=4.0, y=0.0, width=1.2, height=1.2, sill_height=0.9)

wall = Wall.straight(0, 0, 8, 0, thickness=0.2, height=3.0)
wall = wall.add_opening(door).add_opening(window)
```

---

## Column

```python
class Column(Element):
    geometry: Polygon2D    # cross-section polygon in world space
    height: float          # column height in meters
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

The `shape` field is a semantic hint for rendering and export. The actual geometry is always a `Polygon2D` (circles are approximated as regular polygons).

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `col.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |

### Factories

#### `Column.rectangular`

```python
Column.rectangular(
    x: float, y: float,
    width: float, depth: float,
    height: float = 3.0,
    crs: CoordinateSystem = WORLD,
    **kwargs,
) -> Column
```

Creates a rectangular column. `x, y` is the lower-left corner.

#### `Column.circular`

```python
Column.circular(
    center_x: float, center_y: float,
    diameter: float,
    height: float = 3.0,
    resolution: int = 32,
    crs: CoordinateSystem = WORLD,
    **kwargs,
) -> Column
```

Creates a circular column approximated as a regular polygon with `resolution` sides.

**Example:**

```python
col_rect = Column.rectangular(x=4.0, y=4.0, width=0.4, depth=0.4, height=4.0)
col_circ = Column.circular(center_x=8.0, center_y=4.0, diameter=0.5, height=4.0)
```
