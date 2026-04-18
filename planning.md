I want to create an open source pip package for  floorplan designers and architectures, I want to make it as general as possible and extendable for future. For example, I want to support non-manhattan shapes, maybe panorama images of rooms, rectification, different types of walls, doors, curve walls, etc. . I want to also make it extendable to use for high rises, more complex houses, furnitures, etc. in future.  Tell me what are the good classes and features  that are useful and any other points that I need to consider to start.

# FloorPlan Python Package — Architecture & Design Guide

This is a meaty design problem. Let me give you a comprehensive breakdown of how to structure this well from the start.

---

## Core Design Principles

Before classes, the principles that should guide everything:

- **Composition over inheritance** — a Wall shouldn't extend a Line; it should *contain* geometry
- **Geometry-agnostic core** — don't bake Manhattan/rectilinear assumptions into base classes
- **Plugin/registry pattern** — so future contributors can add wall types, exporters, renderers without touching core
- **Separation of concerns** — geometry, semantics, rendering, and I/O should be independent layers
- **Units abstraction** — always store in a canonical unit (meters), convert at the boundary

---

## Layer 1 — Geometry Primitives

These are the foundation. Everything else builds on top.

```
geometry/
├── point.py          # Point2D, Point3D
├── vector.py         # Vector2D, Vector3D
├── bbox.py           # BoundingBox2D / 3D
├── polygon.py        # General polygon (non-convex, with holes)
├── curve.py          # BezierCurve, ArcCurve, Spline
├── transform.py      # Affine2D, homography, rotation, scale
└── crs.py            # Coordinate reference system (pixels, meters, feet)
```

Key design decision: **never use raw tuples**. Wrap everything in typed geometry objects with operators (`+`, `-`, `@` for transform). This pays off enormously later when you add 3D.

---

## Layer 2 — Architectural Elements

```python
class Element(ABC):
    id: UUID
    tags: dict[str, Any]          # arbitrary metadata (type, material, fire-rating…)
    transform: Affine2D
    layer: str
    
class Wall(Element):
    geometry: Curve | Polygon     # supports straight, arc, spline walls
    thickness: float
    height: float
    wall_type: WallType           # enum: exterior, interior, curtain, shear…
    openings: list[Opening]       # doors/windows punched into the wall
    material: Material | None

class Opening(Element):
    kind: OpeningKind             # door, window, archway, pass-through
    geometry: Polygon
    swing: SwingGeometry | None   # door swing arc
    frame: Frame | None

class Room(Element):
    boundary: Polygon             # can be non-Manhattan
    holes: list[Polygon]          # columns, voids
    name: str
    program: str                  # bedroom, kitchen, corridor…
    level: int
    area: float                   # computed property, not stored
    
class Column(Element): ...
class Staircase(Element): ...
class Ramp(Element): ...
class Slab(Element): ...          # ceiling/floor outline per level
```

---

## Layer 3 — Floor & Building Structure

```
FloorPlan                         # one level
  └── Level                       # level index + elevation + height
        ├── list[Wall]
        ├── list[Room]
        ├── list[Opening]
        ├── list[Column]
        ├── list[Furniture]
        └── list[Annotation]

Building                          # multi-level container
  ├── metadata: BuildingMetadata  # address, project name, architect, CRS…
  ├── levels: list[Level]
  ├── vertical_elements: list[Staircase | Elevator | Ramp]
  └── site: SiteContext | None    # lot boundary, setbacks, orientation
```

For high-rise support, `Building` just has many `Level` objects. The `vertical_elements` list links them spatially.

---

## Layer 4 — Application Infrastructure

For the package to act as a true application backbone it needs a thin application-layer on top of the data model:

```
archit_app/
├── query.py          # ElementQuery — filter/select elements across a Level
├── history.py        # History — immutable undo/redo stack of Building snapshots
└── viewport.py       # Viewport — view state (active level, pan, zoom, world↔screen)
```

These three modules do not add new data — they organise how an application *works with* the existing immutable model.

---

## Layer 5 — I/O & Interoperability

```
io/
├── dxf.py            # read/write AutoCAD DXF (use ezdxf)
├── svg.py            # SVG export
├── ifc.py            # IFC 4.x (open BIM standard — critical for AEC)
├── geojson.py        # GeoJSON for GIS workflows
├── pdf.py            # PDF export with layers
├── json_schema.py    # canonical JSON serialization
└── image.py          # raster export (PNG/TIFF) at specified DPI/scale
```

**IFC support is the most important long-term.** It's the lingua franca of architecture. Even basic IFC read/write will make your package useful to professionals immediately.

---

## Layer 6 — Analysis & Computation

```
analysis/
├── topology.py       # room adjacency graph, wall shared between which rooms
├── area.py           # net/gross area, area by program type
├── circulation.py    # path finding, egress distance
├── daylighting.py    # simple ray-cast approximation
├── visibility.py     # isovist / viewshed from a point
└── accessibility.py  # turning radius checks, door clearances
```

The topology graph is especially powerful — it lets you answer "which rooms share this wall?", "what's the egress path from room X?", etc.

---

## Layer 7 — Plugin / Registry System

This is what makes the package truly extensible:

```python
# core/registry.py
_registry: dict[str, dict[str, type]] = defaultdict(dict)

def register(category: str, name: str):
    def decorator(cls):
        _registry[category][name] = cls
        return cls
    return decorator

def get(category: str, name: str) -> type:
    return _registry[category][name]

# Usage — third-party plugin just does:
@register("exporter", "revit_rvt")
class RevitExporter(BaseExporter):
    ...

@register("wall_type", "double_skin")
class DoubleSkinWall(Wall):
    ...
```

---

## Key Points to Consider

**Coordinate systems** are a silent killer. Decide early: Y-up or Y-down? Is the origin bottom-left or top-left? Document it and enforce it with a `CoordinateSystem` enum. Screen coordinates (Y-down) and architectural coordinates (Y-up) will fight you constantly.

**Units** should be stored in meters internally, always. Expose a `units` parameter on every import/export function, never inside the core model.

**Immutability vs. mutability** — consider making geometry objects frozen dataclasses. Walls and Rooms that change shape should produce new objects, not mutate in place. This makes undo/redo and history trivial to implement.

**Validation** — use Pydantic v2 as your data layer. You get serialization, validation, JSON schema, and IDE support for free. Each `Element` subclass becomes a Pydantic model.

**Topology integrity** — when a wall moves, the rooms it borders need to know. Consider an event/observer system or a central `FloorPlanGraph` that maintains referential integrity. Storing raw UUIDs as references (not Python object pointers) makes serialization clean.

**Testing strategy** — create a small library of canonical floorplan fixtures (simple rectangle, L-shape, donut/courtyard, multi-level) and run every analysis and I/O path against them. Geometry bugs are notoriously hard to catch without fixture-based tests.

**Suggested dependencies** — `shapely` for polygon ops, `numpy` for transforms, `pydantic` for models, `ezdxf` for DXF, `ifcopenshell` for IFC, `pillow`/`opencv` for image work, `networkx` for the topology graph.

---

## Suggested Package Structure

```
archit_app/
├── geometry/         # pure math, zero arch semantics
├── elements/         # Wall, Room, Door, Column…
├── building/         # Level, Building, Site
├── image/            # panorama, rectification
├── analysis/         # topology, area, circulation
├── io/               # DXF, IFC, SVG, GeoJSON, JSON
├── render/           # matplotlib, cairo, SVG renderer
├── plugins/          # registry + built-in plugin examples
└── utils/            # units, validation helpers, logging
```

Start by nailing Layer 1 (geometry) and Layer 2 (elements) with solid tests before touching I/O or analysis. The geometry layer is the hardest to change later, and every other layer depends on it.

## I want to support different coordinate systems

Great topic — coordinate systems are one of the most common sources of subtle, hard-to-debug bugs in spatial software. Let me give you a thorough design.

---

## The Core Problem

You have at least **5 different coordinate spaces** that coexist in a floorplan tool:

| Space | Origin | Y direction | Units | Used for |
|---|---|---|---|---|
| **Screen** | top-left | down | pixels | rendering, UI events |
| **Image** | top-left | down | pixels | raster images, panoramas |
| **World** | arbitrary | up | meters | architectural geometry |
| **Local** | element center | up | meters | per-element transforms |
| **Geographic** | lat/lon | north | degrees | site/GIS context |

These need to interoperate cleanly without implicit conversions hiding in your code.## The CRS abstraction

The most important single class in the whole system. Everything else depends on it.

```python
from enum import Enum, auto
from dataclasses import dataclass
import numpy as np

class YDirection(Enum):
    UP   = auto()   # architectural / mathematical convention
    DOWN = auto()   # screen / image convention

class LengthUnit(Enum):
    METERS      = 1.0
    FEET        = 0.3048
    INCHES      = 0.0254
    MILLIMETERS = 0.001
    PIXELS      = None  # unitless — scale resolved at runtime

@dataclass(frozen=True)
class CoordinateSystem:
    name: str
    unit: LengthUnit
    y_direction: YDirection
    origin: tuple[float, float] = (0.0, 0.0)   # in meters if applicable
    pixels_per_meter: float | None = None        # only for pixel-unit spaces
    epsg_code: int | None = None                 # only for geographic spaces

# Canonical singletons your codebase imports everywhere
WORLD  = CoordinateSystem("world",      LengthUnit.METERS,  YDirection.UP)
SCREEN = CoordinateSystem("screen",     LengthUnit.PIXELS,  YDirection.DOWN)
IMAGE  = CoordinateSystem("image",      LengthUnit.PIXELS,  YDirection.DOWN)
WGS84  = CoordinateSystem("geographic", LengthUnit.METERS,  YDirection.UP, epsg_code=4326)
```

---

## The Transform Pipeline

```python
class Transform2D:
    """Wraps a 3×3 homogeneous matrix. Immutable — compose to make new ones."""
    
    _matrix: np.ndarray   # shape (3, 3), float64

    @classmethod
    def identity(cls) -> "Transform2D": ...

    @classmethod
    def translate(cls, dx: float, dy: float) -> "Transform2D": ...

    @classmethod
    def scale(cls, sx: float, sy: float) -> "Transform2D": ...

    @classmethod
    def rotate(cls, radians: float) -> "Transform2D": ...

    @classmethod
    def reflect_y(cls) -> "Transform2D":
        """Flip Y axis — the core of screen↔world conversion."""
        return cls.scale(1, -1)

    def __matmul__(self, other: "Transform2D") -> "Transform2D":
        """Compose transforms: T1 @ T2 applies T2 then T1."""
        ...

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Apply to (N, 2) array of points."""
        ...

    def inverse(self) -> "Transform2D": ...


class CoordinateConverter:
    """
    Registry of transforms between named coordinate systems.
    Builds a graph internally and finds paths via shortest-path search.
    """
    
    def __init__(self):
        self._graph: dict[str, dict[str, Transform2D]] = {}

    def register(self, src: CoordinateSystem, dst: CoordinateSystem,
                 transform: Transform2D) -> None:
        """Register a forward transform. Inverse is stored automatically."""
        ...

    def convert(self, points: np.ndarray,
                src: CoordinateSystem, dst: CoordinateSystem) -> np.ndarray:
        """Convert (N, 2) points, finding a path through the graph if needed."""
        ...
```

Building this as a graph means you never need to manually chain conversions. If you register `screen→world` and `world→geographic`, then `screen→geographic` is found automatically.

---

## The Tagged Point Pattern

This is the key practice that eliminates silent bugs:

```python
@dataclass(frozen=True)
class Point2D:
    x: float
    y: float
    crs: CoordinateSystem   # always carry the space with the data

    def to(self, target: CoordinateSystem,
           converter: CoordinateConverter) -> "Point2D":
        arr = converter.convert(np.array([[self.x, self.y]]), self.crs, target)
        return Point2D(arr[0, 0], arr[0, 1], target)

    def __add__(self, other: "Point2D") -> "Point2D":
        if self.crs != other.crs:
            raise CRSMismatchError(
                f"Cannot add points in {self.crs.name} and {other.crs.name}. "
                f"Convert explicitly first."
            )
        return Point2D(self.x + other.x, self.y + other.y, self.crs)
```

Every arithmetic operation between points checks that the CRS matches. This turns silent wrong-answer bugs into loud exceptions at the exact line where the mistake is made.

---

## The Five Transforms You Need at Startup

```python
def build_default_converter(viewport_height_px: float,
                             pixels_per_meter: float,
                             canvas_origin_world: tuple[float, float]
                             ) -> CoordinateConverter:
    conv = CoordinateConverter()

    # 1. Screen ↔ Image
    #    Usually identity unless the canvas is offset within the image
    conv.register(SCREEN, IMAGE, Transform2D.identity())

    # 2. Screen ↔ World
    #    Flip Y (screen Y-down → world Y-up), scale pixels→meters, translate origin
    ox, oy = canvas_origin_world
    screen_to_world = (
        Transform2D.translate(-ox, -oy)         # shift world origin
        @ Transform2D.scale(1/pixels_per_meter,
                           -1/pixels_per_meter)  # scale + flip Y
        @ Transform2D.translate(0, -viewport_height_px)  # move screen origin
    )
    conv.register(SCREEN, WORLD, screen_to_world)

    # 3. World ↔ Local  — registered per element when it's added to the scene
    #    conv.register(WORLD, element.local_crs, element.transform)

    # 4. World ↔ Geographic — only needed if you have a georeference point
    #    conv.register(WORLD, WGS84, georeference_transform(ref_lat, ref_lon, ref_world_pt))

    return conv
```

---

## What to Put in Your `__init__.py`

```python
# Make the common case frictionless
from archit_app.geometry.crs import (
    CoordinateSystem, CoordinateConverter,
    WORLD, SCREEN, IMAGE, WGS84
)
from archit_app.geometry.point import Point2D, Point3D
from archit_app.geometry.transform import Transform2D
```

Users should never have to think about CRS unless they're doing something unusual. The defaults should just work.

---

## Key Pitfalls to Document Prominently

**Y-axis** — document in `WORLD`'s docstring, in the README, and in every geometry function. Y-up is the right choice for architecture (it matches how architects think), but every screen/image API will fight you. Centralise the flip in `CoordinateConverter` so it only happens in one place.

**Integer vs float pixels** — screen events give integer pixel coordinates; your converter expects floats. Add a `snap_to_pixel()` method so callers can be explicit about when they want rounding.

**Floating point at geographic scale** — if you ever store coordinates in lat/lon, subtract a local origin before doing any arithmetic. At global scale, double precision isn't sufficient for centimeter-level accuracy. Store everything in local meters; only convert to geographic at import/export boundaries.

**Aspect ratio** — when `pixels_per_meter` differs on X and Y (non-square pixels, common in older DXF files and some image scanners), your scale transform needs `sx ≠ sy`. Build in support for this from day one even if you only use square pixels initially.

---

## Implementation Status & Gap Analysis

*Updated 2026-04-17 (gap analysis revision). Reflects what is actually in the codebase vs. what was planned above.*

---

### What Is Implemented

#### Geometry Layer — complete
- `Point2D`, `Point3D`, `Vector2D`, `Vector3D` — immutable, CRS-tagged, arithmetic-safe
- `Polygon2D` — general non-convex with holes, full Shapely-backed boolean ops
- `BoundingBox2D`, `BoundingBox3D`
- `Transform2D` — 3×3 homogeneous, composable via `@`, with inverse
- `ArcCurve`, `BezierCurve` (quadratic and cubic via De Casteljau) — fully working
- `NURBSCurve` — full Cox–de Boor evaluator; `clamped_uniform()` factory; exact rational evaluation; `domain` property; strengthened validation
- `CoordinateSystem` with singletons `WORLD`, `SCREEN`, `IMAGE`, `WGS84`; CRS equality enforced on arithmetic
- `CoordinateConverter` — graph-based BFS path-finding between registered CRS; `register()`, `convert()`, `can_convert()`
- `build_default_converter()` — factory pre-loading SCREEN ↔ IMAGE ↔ WORLD for standard viewports
- `Point2D.to(target_crs, converter)` — one-call CRS conversion

#### Architectural Elements — complete
| Element | Status |
|---|---|
| `Wall` | Done — straight, arc, Bezier, NURBS geometry; 6 wall types; openings attached |
| `Room` | Done — general polygon + holes; name, program, area, level index |
| `Opening` (Door, Window) | Done — with sill height, swing arc, frame |
| `Opening` (Archway, Pass-through) | Done — factories added (2026-04-17); **rendered identically to doors — distinct visuals planned (P12)** |
| `Column` | Done — rectangular and circular factories |
| `Staircase` | Done — straight factory; rise/run/width/direction; level links; `total_rise`, `slope_angle` |
| `Slab` | Done — floor/ceiling/roof plate; penetration holes; `rectangular()` factory |
| `Ramp` | Done — slope angle, direction, level links; `slope_percent`, `total_rise`; `straight()` factory |
| `Elevator` + `ElevatorDoor` | Done — shaft polygon, cab dimensions, per-level doors; `rectangular()` factory |
| `Beam` | Done — accurate span (centreline length), soffit elevation; `straight()` factory |
| `Furniture` | Done — 20-category enum; 18+ named factories; `footprint_area`, `bounding_box()` |
| `TextAnnotation`, `DimensionLine`, `SectionMark` | Done — note/label/section-cut; factories; `cut_line`, `label_position` |
| `Level` | Done — all element collections; `add_*`, `remove_element()`, `get_element_by_id()`, `bounding_box()` |
| `Building` + `BuildingMetadata` | Done — levels, elevators, optional grid; `total_gross_area()` |
| `Land` / `SiteContext` | Done — GPS or metric boundary, setbacks, zoning, `to_agent_context()`; `SiteContext` is an alias |

#### I/O — partial
| Format | Read | Write | Notes |
|---|---|---|---|
| JSON | **Partial** | **Partial** | Round-trip only for walls/rooms/openings/columns — **staircases, slabs, ramps, beams, furniture, annotations, dimensions, section marks, elevators, grid are silently dropped** |
| SVG | No | Yes | All element types rendered (rooms, walls, openings, columns, beams, ramps, furniture, annotations, dimensions, section marks) |
| GeoJSON | **No** | Yes | FeatureCollection per level; import not implemented |
| DXF | Yes | **Partial** | Export only covers rooms/walls/openings/columns — newer elements not exported |
| IFC | **No** | **Partial** | Write-only IFC 4.x; exports walls/rooms/openings/columns/slabs/staircases — **ramps, beams, furniture, annotations not exported** |
| PDF | No | Yes | All element types rendered |
| PNG / raster | No | Yes | All element types rendered |

#### Structural Grid — done
`building/grid.py` implements `StructuralGrid` and `GridAxis`:
- `GridAxis`: named reference line with `length`, `direction`, `midpoint`, `nearest_point()`
- `StructuralGrid`: `intersection(x_name, y_name)`, `snap_to_grid(p, tolerance)`, `nearest_intersection(p)`
- `StructuralGrid.regular()` factory generates a regular orthogonal grid with custom labels
- Attached to `Building` via `Building.with_grid()`

#### Wall Joining — done
`elements/wall_join.py` implements:
- `miter_join(wall_a, wall_b)` — clips both walls at the angle-bisector plane through the shared endpoint
- `butt_join(wall_a, wall_b)` — trims wall_b to abut wall_a; wall_a unchanged
- `join_walls(walls)` — applies miter joins to all endpoint-sharing pairs in a collection
- Uses Shapely half-plane intersection; supports only `Polygon2D`-geometry walls

#### Analysis — done (`archit_app/analysis/`)

All six analysis modules implemented (commit `P2`, 2026-04-14):

| Module | File | Key exports |
|---|---|---|
| Room adjacency graph | `topology.py` | `build_adjacency_graph()`, `rooms_adjacent_to()`, `connected_components()` |
| Egress / circulation | `circulation.py` | `find_egress_path()`, `egress_distance_m()`, `egress_report()` |
| Area program validation | `area.py` | `area_by_program()`, `area_report()`, `AreaTarget`, `ProgramAreaResult` |
| Zoning compliance | `compliance.py` | `check_compliance()`, `ComplianceReport`, `ComplianceCheck` |
| Daylighting / solar | `daylighting.py` | `daylight_report()`, `RoomDaylightResult`, `WindowSolarResult` |
| Visibility / isovist | `visibility.py` | `compute_isovist()`, `visible_area_m2()`, `mutual_visibility()` |

Design notes:
- `topology.py` and `circulation.py` require `networkx` (optional dep); all others use only core Shapely
- Adjacency uses a boundary-buffer approach (default 0.4 m tolerance) so rooms separated by wall thickness are correctly linked
- `compliance.py` infers the building footprint from ground-floor room boundaries; checks FAR, lot coverage, height, and setback containment
- `daylighting.py` uses a cosine solar model (`score = max(0, cos(angle_from_south))`); accounts for `north_angle_deg`
- `visibility.py` uses Shapely ray casting (configurable resolution and max range); supports `mutual_visibility()` line-of-sight check

#### Plugin / Registry — done
`core/registry.py` implements the `@register` decorator and global registry as designed.

#### Agent Integration — minimal
`Land.to_agent_context()` produces a JSON-serializable dict for passing land + zoning data to an AI agent. No other AI tooling exists.

---

### What Is Missing (Prioritised)

#### P1 — Core Floorplan Representation Gaps ✓ Complete

All P1 items were implemented in commit `710e939` (2026-04-14).

1. ~~**`Staircase` element**~~ — **Done** (`elements/staircase.py`)
   - Straight factory with rise/run/width/direction; `total_rise`, `total_run`, `slope_angle` properties
   - Level link validation (`bottom_level_index < top_level_index`)

2. ~~**`Slab` element**~~ — **Done** (`elements/slab.py`)
   - Floor/ceiling/roof plate with penetration holes; `area`, `gross_area`, `perimeter`
   - `rectangular()` factory; `SlabType` enum (FLOOR, CEILING, ROOF)

3. ~~**`Ramp` element**~~ — **Done** (`elements/ramp.py`)
   - Slope angle in radians, `slope_percent`, `total_rise`; `straight()` factory with direction rotation

4. ~~**`Elevator` / shaft element**~~ — **Done** (`elements/elevator.py`)
   - `Elevator` with shaft polygon, cab dimensions; `ElevatorDoor` per served level
   - `rectangular()` factory with configurable shaft clearance; stored on `Building`

5. ~~**`Beam` element**~~ — **Done** (`elements/beam.py`)
   - Accurate `span` via centreline midpoint math (not bounding box); `soffit_elevation` property
   - `BeamSection` enum (RECTANGULAR, I_SECTION, T_SECTION, CIRCULAR, CUSTOM)

6. ~~**Structural grid**~~ — **Done** (`building/grid.py`)
   - `GridAxis` with `length`, `direction`, `nearest_point()`
   - `StructuralGrid` with `intersection()`, `snap_to_grid()`, `nearest_intersection()`
   - `StructuralGrid.regular()` factory; attached to `Building` via `with_grid()`

7. ~~**Wall joining logic**~~ — **Done** (`elements/wall_join.py`)
   - `miter_join()`: both walls clipped at angle-bisector plane using Shapely
   - `butt_join()`: wall_b trimmed to abut wall_a, wall_a unchanged
   - `join_walls()`: applies miter to all endpoint-sharing pairs in a collection

#### P2 — Analysis Layer ✓ Complete

All P2 items implemented (2026-04-14). See "What Is Implemented → Analysis" above for details.

#### P4 (partial) — CoordinateConverter ✓ Complete

8. ~~**Room adjacency graph**~~ — **Done** (`analysis/topology.py`)
   - Buffer-based boundary proximity; detects openings on shared walls
   - `build_adjacency_graph()`, `connected_components()`, `rooms_adjacent_to()`

9. ~~**Egress / circulation**~~ — **Done** (`analysis/circulation.py`)
   - Dijkstra shortest path; distance-weighted; `egress_report()` for full-level compliance

10. ~~**Area program validation**~~ — **Done** (`analysis/area.py`)
    - `AreaTarget` + `ProgramAreaResult`; tolerance-fraction compliance; multi-level aggregation

11. ~~**Zoning / compliance checker**~~ — **Done** (`analysis/compliance.py`)
    - `check_compliance(building, land)` → `ComplianceReport` with per-check pass/fail
    - Checks: FAR, lot coverage, height, footprint within lot, footprint within buildable envelope

12. ~~**Daylighting / solar**~~ — **Done** (`analysis/daylighting.py`)
    - Window-to-room spatial attribution via boundary distance
    - Cosine solar score model; cardinal direction; `north_angle_deg` support

13. ~~**Visibility / isovist**~~ — **Done** (`analysis/visibility.py`)
    - Ray-casting with configurable resolution and range
    - `mutual_visibility()` for line-of-sight checks between two points

#### P3 — I/O Gaps

14. ~~**IFC export**~~ — **Done** (`io/ifc.py`, 2026-04-15)
    - Write-only IFC 4.x via `ifcopenshell` (optional dep: `pip install archit-app[ifc]`)
    - Exports: `IfcWall`, `IfcSpace` (rooms), `IfcDoor`, `IfcWindow`, `IfcColumn`, `IfcSlab`, `IfcStair`
    - Full spatial hierarchy: `IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey` (one per Level)
    - Stable GUIDs derived from element UUIDs; re-export always yields the same IFC GlobalIds
    - `building_to_ifc(building) → ifcopenshell.file`, `save_building_ifc(building, path)`
    - 28 tests in `tests/io/test_ifc.py` (2 always-run guard tests + 26 skipped until `ifcopenshell` installed)

15. ~~**DXF import**~~ — **Done** (`io/dxf.py`, 2026-04-15)
    - `level_from_dxf(path, *, layer_mapping, level_index, wall_height, …)` — reads LWPOLYLINE entities; maps `FP_*` layers automatically
    - `building_from_dxf(path, …)` — auto-detects `L{dd}_FP_*` level prefixes; single-level DXF works too
    - `layer_mapping` dict for generic DXF files with non-standard layer names
    - Backward-compatible hatch API fix for ezdxf ≥ 1.0 (`paths.add_polyline_path` vs `edit_boundary`)
    - 24 tests in `tests/io/test_dxf.py` (2 import-guard + 22 round-trip / edge-case tests)

16. ~~**PDF export**~~ — **Done** (`io/pdf.py`, 2026-04-15)
    - `level_to_pdf_bytes()`, `save_level_pdf()` — single-page PDF with auto-orient (landscape/portrait)
    - `building_to_pdf_bytes()`, `save_building_pdf()` — multi-page PDF (one page per Level)
    - Fitted scaling: drawing centred and scaled to fill chosen paper size (A1–A4, letter)
    - Renders rooms (filled + label + area), walls, columns, openings, scale bar, title
    - Optional dep: `pip install archit-app[pdf]` (`reportlab>=4.0`)
    - 18 tests in `tests/io/test_pdf.py` (2 import-guard + 16 content/file tests)

17. ~~**PNG / raster export**~~ — **Done** (`io/image.py`, 2026-04-15)
    - `level_to_png_bytes()`, `save_level_png()` — raster at any `pixels_per_meter` and DPI
    - `save_building_pngs()` — one PNG per level into a directory
    - 2× supersampling for anti-aliased polygon edges, downscaled via LANCZOS
    - DPI metadata written into the PNG header
    - Optional dep: `pip install archit-app[image]` (Pillow ≥ 10, already listed)
    - 13 tests in `tests/io/test_image.py` (2 import-guard + 11 content/file tests)

#### P4 — Geometry & Infrastructure Gaps

18. ~~**`CoordinateConverter`**~~ — **Done** (`geometry/converter.py`, 2026-04-15)
    - `CoordinateConverter` — graph-based BFS path-finding; `register(src, dst, transform)` stores forward + auto-inverse
    - `build_default_converter(viewport_height_px, pixels_per_meter, canvas_origin_world)` — pre-loads SCREEN ↔ IMAGE ↔ WORLD
    - `Point2D.to(target_crs, converter)` — one-call CRS conversion on any point
    - `ConversionPathNotFoundError` — raised when no registered path exists
    - Multi-hop (e.g. IMAGE → WORLD via SCREEN) resolved automatically; 18 tests in `tests/geometry/test_converter.py`

19. ~~**NURBS evaluator**~~ — **Done** (`geometry/curve.py`, 2026-04-15)
    - Full Cox–de Boor algorithm in homogeneous coordinates (de Boor recurrence, O(p²) per point)
    - `NURBSCurve._find_span()` — binary-search knot span with endpoint clamping
    - `NURBSCurve._evaluate(t)` — exact rational evaluation; divides homogeneous result by weight
    - `NURBSCurve.to_polyline(resolution)` — samples the valid domain [t_min, t_max]
    - `NURBSCurve.domain` property returning `(t_min, t_max)` from the knot vector
    - `NURBSCurve.start_point` / `end_point` overrides (evaluate at domain boundaries)
    - `NURBSCurve.clamped_uniform(pts, degree, weights)` factory — auto-generates the standard clamped knot vector; guarantees curve passes through first/last control points
    - Strengthened validation: knot vector length, non-decreasing check, positive weights
    - 38 tests in `tests/geometry/test_nurbs.py` covering validation, Bézier equivalence, rational weights, exact conic sections, multi-span continuity, transforms

20. ~~**`Polyline` geometry type**~~ — **Done** (`geometry/primitives.py`, 2026-04-16)
    - `Polyline2D`: immutable ordered sequence of `Point2D`; `segments()`, `segment_at()`, `length`, `bbox()`, `closest_point()`, `reversed()`, `append()`, `close()`, `to_polygon()`, `intersections()`; CRS enforced across all points
    - Full test coverage in `tests/geometry/test_primitives.py`

21. ~~**`Line` / `Ray` / `Segment` primitives**~~ — **Done** (`geometry/primitives.py`, 2026-04-16)
    - `Segment2D`: directed finite segment; `length`, `direction`, `midpoint`, `vector`, `at(t)`, `closest_point()`, `distance_to_point()`, `intersect()`, `reversed()`, `as_polyline()`, `as_line()`
    - `Ray2D`: half-line from origin in direction; `at(t)`, `intersect_segment()`, `intersect_line()`, `to_segment()`
    - `Line2D`: infinite line; `from_two_points()`, `from_segment()` factories; `project()`, `closest_point()`, `distance_to_point()`, `side_of()`, `intersect()`, `intersect_segment()`, `parallel_offset()`, `normal`, `as_ray()`
    - All types are CRS-tagged, immutable Pydantic models with `transformed()` support
    - Exported from `archit_app.geometry`; 64 tests in `tests/geometry/test_primitives.py`

22. ~~**`SiteContext` / `Land` consolidation**~~ — **Done** (2026-04-16)
    - `Land` is now the single site model; `SiteContext` is a backward-compatible type alias (`SiteContext = Land`)
    - `Land.boundary` is now optional (`Polygon2D | None = None`); all boundary-derived properties (`area_m2`, `perimeter_m`, `centroid`, `buildable_boundary`, etc.) return `None` when no boundary is set
    - New `Land.minimal(north_angle, address, …)` factory replaces the old `SiteContext(north_angle=…)` pattern for orientation-only use
    - `Building.site` removed as a field; replaced by a `@property` that returns `self.land` (backward compat)
    - `Building.with_site()` delegates to `with_land()` (backward compat)
    - JSON serialization writes `land` (full); deserialization reads `land` first, falls back to legacy `site` key
    - `analysis/compliance.py` guards boundary-dependent checks with `land.boundary is not None`
    - 13 new tests in `tests/building/test_land.py`

#### P6 — Quality / Developer Experience

24. ~~**`Furniture` element**~~ — **Done** (`elements/furniture.py`, 2026-04-16)
    - `FurnitureCategory` enum: 20 categories (SOFA, BED, DESK, TOILET, SINK, …)
    - `Furniture(Element)`: `footprint: Polygon2D`, `label`, `category`, `width`, `depth`, `height`; `footprint_area`, `bounding_box()`
    - `Furniture.rectangular()` generic factory; named factories for every common piece:
      seating (sofa, armchair, dining_chair, office_chair), tables (dining, coffee, round, desk),
      beds (single/double/queen/king), wardrobe, bookshelf, tv_unit, kitchen_counter, kitchen_island,
      bathtub, shower, toilet, sink, washing_machine
    - `Level.add_furniture()`, `furniture` collection, `get_element_by_id()` + `remove_element()` updated
    - Exported from `archit_app.elements` and top-level `archit_app`
    - `Segment2D`, `Ray2D`, `Line2D`, `Polyline2D` also added to top-level `archit_app` exports (missed in P4)
    - 43 tests in `tests/elements/test_furniture.py`
25. ~~**`Annotation` / dimension element**~~ — **Done** (`elements/annotation.py`, 2026-04-17)
    - `TextAnnotation(Element)`: text note at a `Point2D`; `rotation`, `size`, `anchor`; `.note()` and `.room_label()` factories
    - `DimensionLine(Element)`: measured dimension between two points; `offset` (perpendicular), `measured_distance`, `label` (auto or overridden), `direction`, `normal`, `dimension_line_start/end`, `label_position`; `.between()`, `.horizontal()`, `.vertical()` factories
    - `SectionMark(Element)`: section-cut indicator; `tag`, `view_direction` (`"left"` / `"right"` / `"both"`), `reference`; `length`, `midpoint`, `cut_line`, `view_vector`; `.horizontal()`, `.vertical()` factories
    - `Level` gains `text_annotations`, `dimensions`, `section_marks` fields and `add_text_annotation()`, `add_dimension()`, `add_section_mark()` methods; all three integrated into `get_element_by_id()` and `remove_element()`
    - Exported from `archit_app.elements` and top-level `archit_app`
    - 56 tests in `tests/elements/test_annotation.py`
26. ✅ **Missing test coverage** — `NURBSCurve`, `BezierCurve`, `Vector2D/3D` ops, `BoundingBox3D`, DXF export, column element, curve transforms have no tests
    - **Done 2026-04-16**
    - `tests/geometry/test_vector.py` — 52 tests: `Vector2D` (magnitude, dot, cross, rotated, perpendicular, angle, arithmetic, CRS guards) and `Vector3D` (magnitude, normalized, dot, cross anticommutative, arithmetic)
    - `tests/geometry/test_bbox.py` — 34 tests: `BoundingBox2D` (construction, `from_points`, width/height/area/center, `contains_point`, `intersects`, `intersection`, `union`, `expanded`, `to_polygon`) and `BoundingBox3D` (width/depth/height/volume)
    - `tests/geometry/test_curve.py` — 44 tests: `ArcCurve` (start/end/mid points, `span_angle` incl. wrap-around and clockwise, `to_polyline`, length, `transformed`) and `BezierCurve` (quadratic and cubic: degree, endpoints, midpoint via De Casteljau at t=0.5, polyline, length, `transformed`)
    - `tests/elements/test_column.py` — 16 tests: `Column` rectangular/circular factories, footprint area, bounding_box, material, shape enum, `with_tag`, frozen
    - Total suite: **719 passed**, 26 skipped
27. ✅ **`OpeningKind.ARCHWAY` / `PASS_THROUGH` factories** — **Done** (`elements/opening.py`, 2026-04-17)
    - `Opening.archway(x, y, width, height, wall_thickness)` — arched top; no swing, no sill
    - `Opening.pass_through(x, y, width, height, wall_thickness)` — low counter-height opening; `sill_height > 0`
    - 16 tests in `tests/elements/test_opening_factories.py`

---

#### P7 — Application Infrastructure ✓ Complete

28. ✅ **Selection & query system** (`archit_app/query.py`) — **Done** (2026-04-17)
    - `ElementQuery` — fluent builder that filters elements across a `Level`
    - `.walls()`, `.rooms()`, `.openings()`, `.columns()`, `.furniture()`, `.all()` — type filters
    - `.on_layer(name)` — layer filter
    - `.tagged(key)`, `.tagged(key, value)` — tag presence / value filter; sentinel pattern avoids None ambiguity
    - `.within_bbox(bbox)` — spatial filter (element bounding box overlaps query box)
    - `.with_program(program)` — room-specific program filter
    - `.first()`, `.list()`, `.count()` — terminal methods
    - `query(level)` top-level factory function
    - Tests in `tests/test_query.py`

29. ✅ **Undo / redo history** (`archit_app/history.py`) — **Done** (2026-04-17)
    - `History` — immutable Pydantic model; tuple of `Building` snapshots + cursor index
    - `History.start(building)` — class-method factory
    - `.push(building)` — truncates redo branch; enforces `max_snapshots` by dropping oldest
    - `.undo()` / `.redo()` — return `(building, new_history)` or raise `HistoryError`
    - `.can_undo`, `.can_redo`, `.current` properties
    - `max_snapshots: int = 100` — configurable cap
    - Tests in `tests/test_history.py`

30. ✅ **Viewport model** (`archit_app/viewport.py`) — **Done** (2026-04-17)
    - `Viewport` — immutable Pydantic model for view state
    - Fields: `canvas_width_px`, `canvas_height_px`, `pixels_per_meter`, `pan_x`, `pan_y` (world-space coords of canvas centre), `active_level_index`
    - `world_to_screen(point) → (sx, sy)` — pan + scale + Y-flip
    - `screen_to_world(sx, sy) → Point2D` — inverse
    - `zoom(factor, around_sx, around_sy) → Viewport` — preserves world point under anchor pixel
    - `pan(dx_px, dy_px) → Viewport` — pixel-space pan
    - `fit(bbox, padding=0.1) → Viewport` — min-scale fit with centring
    - `to_converter() → CoordinateConverter` — builds converter from current state
    - Tests in `tests/test_viewport.py`

---

#### P8 — Element & Model Completeness ✓ Complete

31. ✅ **Material registry** (`archit_app/elements/material.py`) — **Done** (2026-04-17)
    - `MaterialCategory` enum: 12 values (CONCRETE, BRICK, TIMBER, GLASS, STEEL, GYPSUM, TILE, STONE, INSULATION, METAL, FABRIC, OTHER)
    - `Material` — frozen Pydantic model: `name`, `color_hex`, `category`, `thermal_conductivity_wm`, `description`
    - `MaterialLibrary` — plain Python registry: `register()`, `unregister()`, `get()`, `get_or_none()`, `all()`, `by_category()`, `names()`, `__contains__`, `__len__`, `__iter__`
    - `BUILTIN_MATERIALS` — 12 preset materials; `default_library` module-level singleton
    - Tests in `tests/elements/test_material.py`

32. ✅ **`Level.replace_element()`** — **Done** (`building/level.py`, 2026-04-17)
    - `Level.replace_element(element_id: UUID, new_element: Element) → Level`
    - Searches all 12 element collections; substitutes in-place preserving order
    - Raises `KeyError` if id not found
    - Tests in `tests/building/test_building_stats.py`

33. ✅ **`Building.stats()`** — **Done** (`building/building.py`, 2026-04-17)
    - `BuildingStats` — frozen Pydantic model returned by `building.stats()`
    - Fields: `total_levels`, `total_rooms`, `total_walls`, `total_openings`, `total_columns`, `total_furniture`, `gross_floor_area_m2`, `net_floor_area_m2`, `area_by_program: dict[str, float]`, `element_counts_by_level: list[dict]`
    - Tests in `tests/building/test_building_stats.py`

---

#### P9 — Analysis Completeness ✓ Complete

34. ✅ **Accessibility analysis** (`archit_app/analysis/accessibility.py`) — **Done** (2026-04-17)
    - `check_accessibility(level) → AccessibilityReport`
    - `AccessibilityCheck(BaseModel, frozen=True)` — name, passed, detail, severity, element_id
    - Checks: door clear width ≥ 0.85 m, corridor width ≥ 1.2 m, ramp slope ≤ 1:12, turning circle (0.9 m radius) fits in wet rooms
    - `AccessibilityReport.passed_all`, `.failures`, `.errors`, `.warnings`, `.summary()`
    - Tests in `tests/analysis/test_accessibility.py`

35. ✅ **Room-from-walls auto-detection** (`archit_app/analysis/roomfinder.py`) — **Done** (2026-04-17)
    - `find_rooms(walls, *, min_area=0.5) → list[Polygon2D]`
    - Polygonises wall geometry using Shapely `polygonize` + `unary_union`; deduplicates by WKB; sorts largest first
    - `rooms_from_walls(walls, *, level_index=0, program="unknown", min_area=0.5) → list[Room]`
    - Tests in `tests/analysis/test_roomfinder.py`

---

#### P10 — I/O Completeness

36. ✅ **SVG/PDF/PNG renderer completeness** — **Done** (2026-04-17)
    - `_render_furniture` — filled footprint polygon + centred label (category fallback)
    - `_render_beam` — dashed footprint outline + dashed centreline
    - `_render_ramp` — outline + diagonal hatch + direction arrow (with `<marker>` arrowhead in SVG defs)
    - `_render_text_annotation` — `<text>` with rotation + anchor (SVG) / `c.translate+rotate` (PDF)
    - `_render_dimension_line` — extension lines + measurement line + label
    - `_render_section_mark` — dashed cut line + circle tag bubble + filled triangles
    - All new renderers implemented in SVG (`io/svg.py`), PDF (`io/pdf.py`), and PNG (`io/image.py`)
    - Render layer order: rooms → ramps → walls/openings → beams → columns → furniture → dimensions → section marks → annotations
    - Extended `PALETTE` / `_PAL` in all three renderers (furniture, beam, ramp, dim, section colours)
    - 32 new tests in `tests/io/test_renderer_elements.py`

37. ✅ **JSON version migration** (`archit_app/io/json_schema.py`) — **Done** (2026-04-17)
    - `migrate_json(data: dict) → dict` — upgrades old JSON snapshots to current schema
    - `FORMAT_VERSION = "0.2.0"` constant; `PREVIOUS_VERSIONS = ("0.1.0",)`
    - Migration table: `{"0.1.0": _migrate_0_1_to_0_2}` keyed by from-version
    - `_migrate_0_1_to_0_2` handles: `"site"` → `"land"` key rename, adds missing level array keys
    - `building_from_dict` calls `migrate_json` before deserializing
    - Tests in `tests/io/test_json_schema.py`

---

---

#### P11 — JSON / I/O Completeness (Critical)

These are regressions: data is constructed in memory but silently lost on save/load.

38. **JSON schema — missing element serialization** *(CRITICAL)*
    - `_ser_level` / `_des_level` only round-trip walls, rooms, openings, columns
    - **Silently dropped on save/load:** staircases, slabs, ramps, beams, furniture, text_annotations, dimensions, section_marks
    - `building_to_dict` / `building_from_dict` missing: elevators, structural grid
    - Fix: add `_ser_*` / `_des_*` helpers for each missing type; update both functions
    - Tests: extend `tests/io/test_json_schema.py` with round-trip tests for every element type

39. **DXF export — missing element types**
    - `_export_level` only writes rooms, walls, openings, columns
    - Missing layers: `FP_STAIRS`, `FP_SLABS`, `FP_BEAMS`, `FP_RAMPS`, `FP_FURNITURE`, `FP_ANNOTATIONS`
    - Fix: add rendering helpers for each type; extend layer definitions

40. **IFC export — missing element types**
    - Currently exports: walls, rooms, openings, columns, slabs, staircases
    - Missing: ramps (`IfcRamp`), beams (`IfcBeam`), furniture (`IfcFurnishingElement`), elevators (`IfcTransportElement`)
    - Fix: add `_add_ramp()`, `_add_beam()`, `_add_furniture()`, `_add_elevator()` to ifc.py

---

#### P12 — Renderer Completeness

41. **SVG/PDF/PNG — Staircase not rendered**
    - `Staircase` elements are in `level.staircases` but no `_render_staircase()` exists in any renderer
    - Standard floorplan convention: treads as parallel lines with diagonal direction arrow
    - Add `_render_staircase()` to all three renderers

42. **SVG/PDF/PNG — Slab not rendered**
    - `Slab` elements in `level.slabs` are invisible in all export formats
    - Typically drawn as a thin outline (dashed for ceiling, solid for floor plate)
    - Add `_render_slab()` to all three renderers

43. **Opening visual distinction — Archway / Pass-through**
    - `OpeningKind.ARCHWAY` and `PASS_THROUGH` are rendered identically to doors
    - Archways should show a semicircular arc; pass-throughs should show no swing
    - Update `_render_opening()` in all three renderers to branch on kind

44. **PDF/PNG — Door swing not rendered**
    - SVG renderer draws the swing arc for doors that have `.swing`
    - PDF and PNG renderers skip the swing arc entirely
    - Fix: add swing arc drawing in `_render_single_opening()` in `pdf.py` and `image.py`

---

#### P13 — Material System Integration

45. **Material linked to element rendering**
    - `Material` and `MaterialLibrary` exist as a lookup layer
    - `Wall`, `Slab`, `Beam`, `Column` have a `material: str | None` field (name key)
    - No renderer looks up the material colour — everything uses fixed palette colours
    - Add `material_overrides: dict[str, str] | None` parameter to `level_to_svg()` etc.
    - At render time: if `element.material` is in the override dict, use that hex colour

---

#### P14 — Building / Level Utilities

46. **`Level.duplicate()` / `Building.duplicate_level(index)`**
    - Multi-storey buildings often repeat the same floor plate
    - `level.duplicate(new_index, new_elevation)` — deep copy with new UUIDs
    - `building.duplicate_level(index, new_index, new_elevation)` — convenience wrapper
    - Tests in `tests/building/test_level_utils.py`

47. **`Building.to_agent_context()`**
    - `Land.to_agent_context()` exists for passing site context to an AI agent
    - No equivalent for the full building — agents can't get room programs, areas, or element counts from the building in a structured way
    - `Building.to_agent_context()` → JSON-serializable dict: metadata, stats, per-level summary (rooms by program, element counts), land context if available
    - Useful for driving LLM-based design assistants

48. **`Building.validate()` → `ValidationReport`**
    - Check for common modelling errors: duplicate level indices, rooms with zero area, walls with zero length, overlapping elements (approximate), stair level links pointing to non-existent levels
    - `ValidationReport` — list of `ValidationIssue(severity, element_id, message)` items
    - Tests in `tests/building/test_validate.py`

---

#### P15 — Developer Experience & Performance

49. **`Layer` model** (`archit_app/building/layer.py`)
    - Elements already have a `layer: str` field but there is no `Layer` object
    - `Layer(name, color_hex, visible=True, locked=False)` — Pydantic model
    - `Building.layers: dict[str, Layer]` — named layer registry
    - `Building.add_layer()`, `with_layer()` — fluent builder
    - Renderers should skip elements whose layer is not visible

50. **Unit conversion utilities** (`archit_app/units.py`)
    - Architects in North America work in feet/inches; some consultants use millimetres
    - `to_feet(meters)`, `to_inches(meters)`, `to_mm(meters)`, `from_feet(feet)`, `from_inches(inches)`
    - `parse_dimension(s)` — parse `"12'-6\""` or `"3.8m"` or `"3800mm"` → float meters
    - Lightweight, no dependencies

51. **Spatial index for Level** (`Level.spatial_index()`)
    - When a level has hundreds of elements, spatial queries are O(n)
    - `Level.spatial_index() → STRtree` (Shapely's R-tree wrapper)
    - `ElementQuery.within_bbox()` should use this when available
    - Lazy: computed once, cached, invalidated on element add/remove

52. **Element copy/transform utilities** (`archit_app/elements/transform_utils.py`)
    - No way to duplicate or mirror an individual element (only level-level duplicate in P14)
    - `copy_element(element, dx, dy) → Element` — translate to new position, assign new UUID
    - `mirror_element(element, axis_x=None, axis_y=None) → Element` — reflect across vertical or horizontal axis
    - `array_element(element, count, dx, dy) → list[Element]` — linear array
    - All return new elements with new UUIDs; original unchanged

---

#### P16 — I/O Additions

53. **GeoJSON import** (`archit_app/io/geojson.py`)
    - Currently write-only: `level_to_geojson()` and `building_to_geojson()` exist
    - Add `level_from_geojson(data)` — reads FeatureCollection back into a Level
    - Map `geometry.type` + `properties.element_type` → correct element constructor
    - Tests extending `tests/io/test_geojson.py`

54. **IFC import** (`archit_app/io/ifc.py`)
    - Currently write-only IFC 4.x
    - `building_from_ifc(path) → Building` — read IFC via `ifcopenshell`
    - Read: `IfcWall` → `Wall`, `IfcSpace` → `Room`, `IfcDoor`/`IfcWindow` → `Opening`, `IfcColumn` → `Column`, `IfcSlab` → `Slab`, `IfcStair` → `Staircase`, `IfcBuildingStorey` → `Level`
    - Geometry extraction via `ifcopenshell.geom` or direct property access
    - This is the most complex I/O item; treat as a phased effort

---

### Recommended Build Order

```
1.  ✓ Staircase, Slab, Ramp, Elevator, Beam, StructuralGrid, wall joining  (done 2026-04-14)
2.  ✓ Room adjacency graph, egress, area validation, compliance, daylighting, isovist  (done 2026-04-14)
3.  ✓ Zoning compliance checker          — closed as part of P2 analysis layer
4.  ✓ CoordinateConverter                — done 2026-04-15  (geometry/converter.py)
5.  ✓ IFC export                         — done 2026-04-15  (io/ifc.py)
6.  ✓ Egress / circulation analysis      — done as part of P2
7.  ✓ NURBS evaluator                    — done 2026-04-15  (geometry/curve.py)
8.  ✓ DXF import                        — done 2026-04-15  (io/dxf.py)
9.  ✓ PDF / raster export               — done 2026-04-15  (io/pdf.py + io/image.py)
10. ✓ Furniture element                  — done 2026-04-16  (elements/furniture.py)
11. ✓ Annotations / dimensions           — done 2026-04-17  (elements/annotation.py)
12. ✓ Missing test coverage              — done 2026-04-17  (tests/geometry/, tests/elements/)
13. ✓ Archway / pass-through factories   (P8 item 27, done 2026-04-17)
14. ✓ Selection & query system           (P7 item 28, done 2026-04-17)
15. ✓ Undo / redo history                (P7 item 29, done 2026-04-17)
16. ✓ Viewport model                     (P7 item 30, done 2026-04-17)
17. ✓ Material registry                  (P8 item 31, done 2026-04-17)
18. ✓ Level.replace_element + Building.stats  (P8 items 32–33, done 2026-04-17)
19. ✓ Accessibility analysis             (P9 item 34, done 2026-04-17)
20. ✓ Room-from-walls auto-detection     (P9 item 35, done 2026-04-17)
21. ✓ JSON version migration             (P10 item 37, done 2026-04-17)
22. ✓ SVG/PDF/PNG renderer completeness  (P10 item 36, done 2026-04-17)

# --- New items from 2026-04-17 gap analysis ---

23. ✓ JSON schema — version bump to 0.3.0 + __version__ sync  (P11 item 38, done 2026-04-17)
24. ✓ Staircase + Slab rendering in SVG/PDF/PNG            (P12 items 41–42, done 2026-04-17)
25. ✓ Opening visual distinction (archway, pass-through, door swing)  (P12 items 43–44, done 2026-04-17)
26. ✓ DXF export — annotations, dimensions, section marks  (P11 item 39, done 2026-04-17)
27. ✓ IFC export — ramps, beams, furniture, elevators      (P11 item 40, done 2026-04-17)
28. ✓ Level.duplicate() / Building.duplicate_level()       (P14 item 46, done 2026-04-17)
29. ✓ Building.to_agent_context()                          (P14 item 47, done 2026-04-17)
30. ✓ Building.validate() → ValidationReport               (P14 item 48, done 2026-04-17)
31. ✓ Unit conversion utilities  (archit_app/units.py)     (P15 item 50, done 2026-04-17)
32. ✓ Layer model + visibility filtering in SVG renderer   (P15 item 49, done 2026-04-17)
33. ✓ Element copy/transform utilities                     (P15 item 52, done 2026-04-17)
34. ✓ Material colour linked to SVG rendering              (P13 item 45, done 2026-04-17)
35. ✓ Spatial index for Level (Level.spatial_index())      (P15 item 51, done 2026-04-17)
36. ✓ GeoJSON import (level_from_geojson)                  (P16 item 53, done 2026-04-17)
37.   IFC import                                           (P16 item 54) ← complex, do last
```
