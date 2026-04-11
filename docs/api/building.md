# API Reference — Building

```python
from archit_app import (
    Level,
    Building, BuildingMetadata,
    SiteContext,
)
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

    walls:    tuple[Wall, ...]    = ()
    rooms:    tuple[Room, ...]    = ()
    openings: tuple[Opening, ...] = ()   # level-standalone openings
    columns:  tuple[Column, ...]  = ()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `level.bounding_box` | `BoundingBox2D \| None` | Union of all element bounding boxes; `None` if level is empty |

### Query methods

| Method | Returns | Description |
|--------|---------|-------------|
| `level.get_element_by_id(uuid)` | `Element \| None` | Search all collections for an element by UUID |

### Mutation methods

| Method | Returns | Description |
|--------|---------|-------------|
| `level.add_wall(wall)` | `Level` | New level with wall appended |
| `level.add_room(room)` | `Level` | New level with room appended |
| `level.add_opening(opening)` | `Level` | New level with opening appended |
| `level.add_column(column)` | `Level` | New level with column appended |
| `level.remove_element(uuid)` | `Level` | New level with the element removed from all collections |

**Example:**

```python
from archit_app import Level, Wall, Room, Polygon2D, WORLD

level = Level(index=0, elevation=0.0, floor_height=3.0, name="Ground Floor")

boundary = Polygon2D.rectangle(0, 0, 10, 8, crs=WORLD)
room = Room(boundary=boundary, name="Open Plan")

level = (
    level
    .add_room(room)
    .add_wall(Wall.straight(0, 0, 10, 0, thickness=0.25, height=3.0))
    .add_wall(Wall.straight(10, 0, 10, 8, thickness=0.25, height=3.0))
    .add_wall(Wall.straight(10, 8, 0, 8, thickness=0.25, height=3.0))
    .add_wall(Wall.straight(0, 8, 0, 0, thickness=0.25, height=3.0))
)
```

---

## Building

```python
class Building(BaseModel, frozen=True):
    metadata: BuildingMetadata = BuildingMetadata()
    levels: tuple[Level, ...] = ()    # kept sorted by Level.index
    site: SiteContext | None = None
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `building.total_floors` | `int` | Number of levels with `index >= 0` |
| `building.total_basements` | `int` | Number of levels with `index < 0` |
| `building.total_gross_area` | `float` | Sum of gross room areas across all levels (m²) |

### Query methods

| Method | Returns | Description |
|--------|---------|-------------|
| `building.get_level(index)` | `Level \| None` | Find a level by floor number |
| `building.get_element_by_id(uuid)` | `Element \| None` | Search all levels for an element by UUID |

### Mutation methods

| Method | Returns | Description |
|--------|---------|-------------|
| `building.add_level(level)` | `Building` | Add or replace a level; levels remain sorted by index |
| `building.remove_level(index)` | `Building` | Remove the level with the given index |
| `building.with_metadata(**kwargs)` | `Building` | Update metadata fields by keyword |
| `building.with_site(site)` | `Building` | Set the site context |

**Example:**

```python
from archit_app import Building, BuildingMetadata, SiteContext, Polygon2D, WORLD

site = SiteContext(
    boundary=Polygon2D.rectangle(-5, -5, 20, 18, crs=WORLD),
    north_angle=15.0,
    address="42 Architecture Lane",
)

building = (
    Building()
    .with_metadata(
        name="Tower A",
        project_number="2026-001",
        architect="Studio X",
        client="Client Corp",
        date="2026-04-05",
    )
    .with_site(site)
    .add_level(ground_level)
    .add_level(first_level)
)

print(building.total_floors)       # 2
print(building.total_gross_area)   # sum of all room areas
```

---

## BuildingMetadata

```python
class BuildingMetadata(BaseModel, frozen=True):
    name: str = ""
    project_number: str = ""
    architect: str = ""
    client: str = ""
    date: str = ""    # ISO 8601 date string, e.g. "2026-04-05"
```

Use `building.with_metadata(**kwargs)` to update; do not construct directly unless building from scratch.

---

## SiteContext

```python
class SiteContext(BaseModel, frozen=True):
    boundary: Polygon2D | None = None   # lot boundary polygon
    north_angle: float = 0.0            # degrees clockwise from world +Y to geographic north
    address: str = ""
    epsg_code: int | None = None        # EPSG code for the geographic CRS
```

`north_angle` defines the rotation between the building's world +Y axis and geographic north. A value of `0` means world +Y is geographic north. Positive values rotate clockwise.

**Example:**

```python
from archit_app import SiteContext, Polygon2D, WORLD

site = SiteContext(
    boundary=Polygon2D.rectangle(-2, -2, 14, 12, crs=WORLD),
    north_angle=22.5,   # building is rotated 22.5° from north
    address="1 Main Street",
    epsg_code=32633,    # UTM Zone 33N
)
```
