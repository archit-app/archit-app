# API Reference — Building

```python
from archit_app import (
    Level,
    Building, BuildingMetadata,
    Land, Setbacks, ZoningInfo,
    StructuralGrid, GridAxis,
)
# SiteContext is a backward-compatible alias for Land
from archit_app.building.site import SiteContext
```

All building objects are **immutable** Pydantic models. "Mutation" methods return new objects.

---

## Level

```python
class Level(BaseModel, frozen=True):
    index: int             # floor number: 0=ground, <0=basement, >0=upper
    elevation: float       # height of slab above site datum, meters
    floor_height: float    # floor-to-ceiling height, meters
    name: str = ""

    walls:            tuple[Wall, ...]            = ()
    rooms:            tuple[Room, ...]            = ()
    openings:         tuple[Opening, ...]         = ()
    columns:          tuple[Column, ...]          = ()
    staircases:       tuple[Staircase, ...]       = ()
    slabs:            tuple[Slab, ...]            = ()
    ramps:            tuple[Ramp, ...]            = ()
    beams:            tuple[Beam, ...]            = ()
    furniture:        tuple[Furniture, ...]       = ()
    text_annotations: tuple[TextAnnotation, ...]  = ()
    dimensions:       tuple[DimensionLine, ...]   = ()
    section_marks:    tuple[SectionMark, ...]     = ()
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `level.bounding_box()` | `BoundingBox2D \| None` | Union of all element bounding boxes; `None` if empty |
| `level.get_element_by_id(uuid)` | `Element \| None` | Search all collections for element by UUID |
| `level.remove_element(uuid)` | `Level` | New level with the element removed from all collections |
| `level.add_wall(wall)` | `Level` | Append a wall |
| `level.add_room(room)` | `Level` | Append a room |
| `level.add_opening(opening)` | `Level` | Append a standalone opening |
| `level.add_column(column)` | `Level` | Append a column |
| `level.add_staircase(stair)` | `Level` | Append a staircase |
| `level.add_slab(slab)` | `Level` | Append a slab |
| `level.add_ramp(ramp)` | `Level` | Append a ramp |
| `level.add_beam(beam)` | `Level` | Append a beam |
| `level.add_furniture(item)` | `Level` | Append a furniture item |
| `level.add_text_annotation(ann)` | `Level` | Append a text annotation |
| `level.add_dimension(dim)` | `Level` | Append a dimension line |
| `level.add_section_mark(mark)` | `Level` | Append a section mark |

**Example:**

```python
from archit_app import Level, Wall, Room, Furniture, DimensionLine, Polygon2D, WORLD

level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")

boundary = Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD)
room = Room(boundary=boundary, name="Bedroom", program="bedroom")

level = (
    level
    .add_room(room)
    .add_wall(Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0))
    .add_furniture(Furniture.queen_bed(x=1.0, y=0.5))
    .add_dimension(DimensionLine.horizontal(x1=0, x2=6, y=4.5))
)
```

---

## Building

```python
class Building(BaseModel, frozen=True):
    metadata: BuildingMetadata = BuildingMetadata()
    levels: tuple[Level, ...] = ()    # kept sorted by Level.index
    land: Land | None = None
    elevators: tuple[Elevator, ...] = ()
    grid: StructuralGrid | None = None
```

`building.site` is a backward-compatible `@property` returning `self.land`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `building.total_floors` | `int` | Levels with `index >= 0` |
| `building.total_basements` | `int` | Levels with `index < 0` |
| `building.total_gross_area` | `float` | Sum of gross room areas across all levels (m²) |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `building.get_level(index)` | `Level \| None` | Find a level by floor number |
| `building.get_element_by_id(uuid)` | `Element \| None` | Search all levels |
| `building.add_level(level)` | `Building` | Add or replace; levels remain sorted |
| `building.remove_level(index)` | `Building` | Remove the level at that index |
| `building.with_metadata(**kwargs)` | `Building` | Update metadata fields |
| `building.with_land(land)` | `Building` | Set the land parcel |
| `building.with_site(land)` | `Building` | Backward-compat alias for `with_land` |
| `building.add_elevator(elev)` | `Building` | Append an elevator |
| `building.remove_elevator(id)` | `Building` | Remove elevator by UUID |
| `building.with_grid(grid)` | `Building` | Set the structural grid |

**Example:**

```python
from archit_app import Building, Land, ZoningInfo, Setbacks, Polygon2D, WORLD

land = Land(
    boundary=Polygon2D.rectangle(-5, -5, 20, 18, crs=WORLD),
    north_angle=15.0,
    address="42 Architecture Lane",
)

building = (
    Building()
    .with_metadata(name="Tower A", project_number="2026-001", architect="Studio X")
    .with_land(land)
    .add_level(ground_level)
    .add_level(first_level)
)
```

---

## BuildingMetadata

```python
class BuildingMetadata(BaseModel, frozen=True):
    name: str = ""
    project_number: str = ""
    architect: str = ""
    client: str = ""
    date: str = ""    # ISO 8601 date string
```

---

## Land

The canonical site/parcel model. `SiteContext` is a backward-compatible alias.

```python
class Land(BaseModel, frozen=True):
    boundary: Polygon2D | None = None  # lot boundary polygon (optional)
    north_angle: float = 0.0           # degrees clockwise from world +Y to north
    address: str = ""
    epsg_code: int | None = None
    elevation_m: float = 0.0           # site elevation above sea level
    setbacks: Setbacks | None = None
    zoning: ZoningInfo | None = None
```

### Properties

All boundary-derived properties return `None` when `boundary` is `None`.

| Property | Type | Description |
|----------|------|-------------|
| `land.has_boundary` | `bool` | True if `boundary` is set |
| `land.area_m2` | `float \| None` | Lot area in m² |
| `land.perimeter_m` | `float \| None` | Lot perimeter in meters |
| `land.centroid` | `Point2D \| None` | Lot centroid |
| `land.buildable_boundary` | `Polygon2D \| None` | Boundary inset by setbacks |
| `land.buildable_area_m2` | `float \| None` | Area of buildable envelope |
| `land.max_floor_area_m2` | `float \| None` | `buildable_area × zoning.max_far` |
| `land.max_footprint_m2` | `float \| None` | `buildable_area × zoning.max_lot_coverage` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `land.with_setbacks(setbacks)` | `Land` | New land with setbacks |
| `land.with_zoning(zoning)` | `Land` | New land with zoning info |
| `land.to_agent_context()` | `dict` | JSON-serializable dict for AI agent prompts |

### Factories

```python
Land.minimal(
    north_angle=0.0,
    address="",
    epsg_code=None,
    elevation_m=0.0,
) -> Land
```

No boundary — useful when only orientation or address is known.

```python
Land.from_latlon(
    coords: list[tuple[float, float]],   # [(lat, lon), ...]
    address="",
    north_angle=0.0,
    epsg_code=None,
) -> Land
```

Converts GPS lat/lon coordinates to metric world-space polygon using a local Mercator projection.

**Example:**

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
print(f"Max GFA: {land.max_floor_area_m2:.1f} m²")
```

---

## Setbacks

```python
class Setbacks(BaseModel, frozen=True):
    front: float = 0.0    # meters from front lot line
    back: float = 0.0
    left: float = 0.0
    right: float = 0.0
```

---

## ZoningInfo

```python
class ZoningInfo(BaseModel, frozen=True):
    zone_code: str = ""
    max_height_m: float | None = None
    max_far: float | None = None          # floor area ratio
    max_lot_coverage: float | None = None # fraction 0–1
    allowed_uses: tuple[str, ...] = ()
    source: str = ""
```

---

## StructuralGrid

```python
class StructuralGrid(BaseModel, frozen=True):
    x_axes: tuple[GridAxis, ...] = ()   # vertical reference lines
    y_axes: tuple[GridAxis, ...] = ()   # horizontal reference lines
```

### GridAxis

```python
class GridAxis(BaseModel, frozen=True):
    name: str
    position: float        # offset along the perpendicular axis in meters
    length: float          # axis line length in meters
    direction: float = 0.0 # bearing in radians
```

### StructuralGrid methods

| Method | Returns | Description |
|--------|---------|-------------|
| `grid.intersection(x_name, y_name)` | `Point2D` | World-space point at named grid intersection |
| `grid.snap_to_grid(point, tolerance)` | `Point2D` | Snap to nearest intersection within tolerance |
| `grid.nearest_intersection(point)` | `Point2D` | Closest grid intersection, no tolerance limit |

### Factory: `StructuralGrid.regular`

```python
StructuralGrid.regular(
    x_spacing: float,
    y_spacing: float,
    x_count: int,
    y_count: int,
    x_labels: list[str] | None = None,   # defaults to "1", "2", ...
    y_labels: list[str] | None = None,   # defaults to "A", "B", ...
    origin_x: float = 0.0,
    origin_y: float = 0.0,
) -> StructuralGrid
```

Generates a regular orthogonal grid.

**Example:**

```python
from archit_app import StructuralGrid, Point2D, WORLD

grid = StructuralGrid.regular(x_spacing=6.0, y_spacing=6.0, x_count=4, y_count=3)

pt = grid.intersection("2", "B")   # Point2D at (6.0, 6.0)
print(pt)

p = Point2D(x=5.95, y=6.1, crs=WORLD)
snapped = grid.snap_to_grid(p, tolerance=0.2)

building = Building().with_grid(grid)
```
