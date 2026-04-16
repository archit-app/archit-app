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

## Layer 4 — Image & Panorama Support

This is where it gets interesting for your use case:

```
image/
├── panorama.py       # EquirectangularImage, CubemapImage
├── rectification.py  # homography estimation, perspective correction
├── calibration.py    # camera intrinsics/extrinsics
└── overlay.py        # project floorplan onto image or vice versa
```

```python
class PanoramaImage:
    data: np.ndarray
    projection: ProjectionType    # equirectangular, cubemap, fisheye
    camera_pose: Pose3D           # where in the building this was shot
    linked_room: Room | None      # semantic link to floorplan

class RoomRectifier:
    """Given a perspective photo of a room, recover the planar layout."""
    def estimate_vanishing_points(self, image) -> VanishingPoints: ...
    def rectify(self, image, vps) -> RectifiedImage: ...
    def extract_wall_mask(self, rectified) -> Polygon: ...
```

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

## Handling Non-Euclidean: Panoramas

Panoramas break the flat-plane assumption entirely, so they need their own projection layer sitting *above* the CRS system:

```python
class ProjectionType(Enum):
    EQUIRECTANGULAR = auto()   # 360° lat/lon mapped to a rectangle
    CUBEMAP         = auto()   # six faces
    FISHEYE         = auto()   # single lens, radial distortion
    PERSPECTIVE     = auto()   # standard pinhole

@dataclass
class CameraModel:
    projection: ProjectionType
    intrinsics: np.ndarray     # 3×3 K matrix (focal length, principal point)
    distortion: np.ndarray     # radial/tangential coefficients
    pose: "Pose3D"             # where the camera sits in world space

class PanoramaProjector:
    def __init__(self, model: CameraModel): ...

    def image_to_ray(self, pixel: Point2D) -> Ray3D:
        """Un-project a pixel to a 3D ray in world space."""
        ...

    def ray_to_image(self, ray: Ray3D) -> Point2D:
        """Project a world-space ray back to a pixel."""
        ...

    def intersect_floor_plane(self, pixel: Point2D,
                               floor_height: float = 0.0) -> Point2D:
        """
        Given a pixel in the panorama, find where the corresponding
        ray hits the floor plane — returns a World-space point.
        """
        ...
```

This lets you click a point on a panorama photo and get a world-space coordinate back — the foundation for semi-automatic floorplan tracing from imagery.

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

*Updated 2026-04-11. Reflects what is actually in the codebase vs. what was planned above.*

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

#### Architectural Elements — partial
| Element | Status |
|---|---|
| `Wall` | Done — straight, arc, Bezier, NURBS geometry; 6 wall types; openings attached |
| `Room` | Done — general polygon + holes; name, program, area, level index |
| `Opening` (Door, Window) | Done — with sill height, swing arc, frame |
| `Opening` (Archway, Pass-through) | Enum variant exists; no factory or geometry logic |
| `Column` | Done — rectangular and circular factories |
| `Staircase` | Done — straight factory; rise/run/width/direction; level links; `total_rise`, `slope_angle` |
| `Slab` | Done — floor/ceiling/roof plate; penetration holes; `rectangular()` factory |
| `Ramp` | Done — slope angle, direction, level links; `slope_percent`, `total_rise`; `straight()` factory |
| `Elevator` + `ElevatorDoor` | Done — shaft polygon, cab dimensions, per-level doors; `rectangular()` factory |
| `Beam` | Done — accurate span (centreline length), soffit elevation; `straight()` factory |
| `Level` | Done — holds walls, rooms, openings, columns, staircases, slabs, ramps, beams |
| `Building` + `BuildingMetadata` | Done — holds levels, elevators, and optional `StructuralGrid` |
| `Land` | Done — GPS latlon or metric polygon, setbacks, ZoningInfo, `to_agent_context()` |
| `SiteContext` | Minimal — boundary + north_angle + address only |
| `Furniture` | **Missing** |
| `Annotation` / Dimension | **Missing** |

#### I/O — partial
| Format | Read | Write | Notes |
|---|---|---|---|
| JSON | Yes | Yes | Full round-trip, versioned |
| SVG | No | Yes | Rooms, walls, openings, columns, scale bar |
| GeoJSON | No | Yes | FeatureCollection per level |
| DXF | **No** | Yes | `ezdxf` required; write-only |
| IFC | **No** | Yes | Write-only IFC 4.x; `ifcopenshell` required |
| PDF | **No** | **No** | Not started |
| PNG / raster | **No** | **No** | `pillow`/`opencv` listed as optional deps but unused |

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

15. **DXF import**
    - Currently write-only; reading DXF is needed to work with existing drawings

16. **PDF export** (`io/pdf.py`)
    - Standard deliverable format for architectural drawings

17. **PNG / raster export** (`io/image.py`)
    - `pillow`/`opencv` are optional deps but completely unused; add raster rendering at specified DPI/scale

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

20. **`Polyline` geometry type**
    - No first-class polyline; sequences of line segments are currently just `tuple[Point2D]` with no type or methods

21. **`Line` / `Ray` / `Segment` primitives**
    - Useful for beam spans, grid axes, section cut lines

22. **`SiteContext` / `Land` consolidation**
    - These two models partially overlap (both have `boundary`, `north_angle`, `address`, `epsg_code`)
    - Consider merging or formally separating their responsibilities to avoid confusion

#### P5 — Image / Panorama Layer (entire module missing)

23. **`image/` module**
    - `panorama.py`, `rectification.py`, `calibration.py`, `overlay.py` — all planned, none implemented
    - `CameraModel`, `PanoramaProjector`, `RoomRectifier` from the design above are the right starting point

#### P6 — Quality / Developer Experience

24. **`Furniture` element** — even bounding-box placeholders would allow layout studies
25. **`Annotation` / dimension element** — dimension lines, labels, section marks; needed for construction documents
26. **Missing test coverage** — `NURBSCurve`, `BezierCurve`, `Vector2D/3D` ops, `BoundingBox3D`, DXF export, column element, curve transforms have no tests
27. **`OpeningKind.ARCHWAY` / `PASS_THROUGH` factories** — enum variants exist but no geometry factories

---

### Recommended Build Order

```
1. ✓ Staircase, Slab, Ramp, Elevator, Beam, StructuralGrid, wall joining  (done 2026-04-14)
2. ✓ Room adjacency graph, egress, area validation, compliance, daylighting, isovist  (done 2026-04-14)
3. ✓ Zoning compliance checker          — closed as part of P2 analysis layer
4. ✓ CoordinateConverter                — done 2026-04-15  (geometry/converter.py)
5. ✓ IFC export                         — done 2026-04-15  (io/ifc.py)
6. ✓ Egress / circulation analysis      — done as part of P2
7. ✓ NURBS evaluator                    — done 2026-04-15  (geometry/curve.py)
8. DXF import                         — round-trip DXF support
9. PDF / raster export                — standard deliverable formats
10. image/ module (panorama)          — most complex; do last
```
