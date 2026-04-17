# API Reference — Geometry

```python
from archit_app import (
    CoordinateSystem, LengthUnit, YDirection,
    CRSMismatchError, require_same_crs,
    WORLD, SCREEN, IMAGE, WGS84,
    CoordinateConverter, build_default_converter,
    Transform2D,
    Point2D, Point3D,
    Vector2D, Vector3D,
    BoundingBox2D, BoundingBox3D,
    Polygon2D,
    ArcCurve, BezierCurve, NURBSCurve,
    Segment2D, Ray2D, Line2D, Polyline2D,
)
```

---

## CoordinateSystem

```python
@dataclass(frozen=True)
class CoordinateSystem:
    name: str
    unit: LengthUnit
    y_direction: YDirection
    origin: tuple[float, float] = (0.0, 0.0)
    pixels_per_meter: float | None = None
    epsg_code: int | None = None
```

Describes a coordinate space. Carries identity semantics based on `(name, unit, y_direction)` — the `origin` and `pixels_per_meter` fields are configuration, not identity.

**Singletons (import directly):**

| Name | Description |
|------|-------------|
| `WORLD` | Meters, Y-up, architectural world space |
| `SCREEN` | Pixels, Y-down, screen/viewport space |
| `IMAGE` | Pixels, Y-down, raster image space |
| `WGS84` | Meters, Y-up, geographic (EPSG:4326) |

---

## LengthUnit

```python
class LengthUnit(Enum):
    METERS      = 1.0
    FEET        = 0.3048
    INCHES      = 0.0254
    MILLIMETERS = 0.001
    PIXELS      = None
```

### Methods

#### `to_meters(value, pixels_per_meter=None) → float`

Convert a value in this unit to meters. For `PIXELS`, `pixels_per_meter` is required.

#### `from_meters(value, pixels_per_meter=None) → float`

Convert a value in meters to this unit.

---

## YDirection

```python
class YDirection(Enum):
    UP   # architectural / mathematical convention
    DOWN # screen / image convention
```

---

## CRSMismatchError

Raised when two spatial objects in incompatible coordinate systems are combined. The error message names both CRS and instructs the caller to convert explicitly.

```python
class CRSMismatchError(ValueError): ...
```

---

## CoordinateConverter

```python
class CoordinateConverter:
    def register(src: CoordinateSystem, dst: CoordinateSystem, transform: Transform2D) -> None
    def convert(pts: np.ndarray, src: CoordinateSystem, dst: CoordinateSystem) -> np.ndarray
    def can_convert(src: CoordinateSystem, dst: CoordinateSystem) -> bool
```

Graph-based multi-hop CRS converter. `register()` stores the forward transform and its inverse automatically. `convert()` takes an `(N, 2)` float64 array and returns a converted array; intermediate hops are resolved via BFS.

`ConversionPathNotFoundError` is raised when no registered path exists between `src` and `dst`.

### `build_default_converter`

```python
build_default_converter(
    viewport_height_px: float,
    pixels_per_meter: float,
    canvas_origin_world: tuple[float, float] = (0.0, 0.0),
) -> CoordinateConverter
```

Factory pre-registering SCREEN ↔ IMAGE ↔ WORLD with the standard Y-flip and pixel/meter scale.

**Example:**

```python
from archit_app import build_default_converter, SCREEN, WORLD, IMAGE, Point2D
import numpy as np

conv = build_default_converter(viewport_height_px=600, pixels_per_meter=50)

# Convert a screen click to world coordinates
click = Point2D(x=400, y=300, crs=SCREEN)
world_pt = click.to(WORLD, conv)

# Bulk conversion
pts_screen = np.array([[200.0, 100.0], [400.0, 300.0]])
pts_world = conv.convert(pts_screen, SCREEN, WORLD)
```

---

## require_same_crs

```python
def require_same_crs(a: CoordinateSystem, b: CoordinateSystem, op: str = "operate on") -> None
```

Assert that two CRS are equal; raise `CRSMismatchError` if not.

---

## Transform2D

```python
class Transform2D:
    matrix: np.ndarray  # read-only (3, 3) float64
```

Immutable 3×3 homogeneous affine transform. All factory methods return new instances. Composed with `@`.

**Convention:** `(T1 @ T2)` applies `T2` first, then `T1`.

### Factories

| Method | Description |
|--------|-------------|
| `Transform2D.identity()` | 3×3 identity matrix |
| `Transform2D.translate(dx, dy)` | Pure translation |
| `Transform2D.scale(sx, sy)` | Axis-aligned scale |
| `Transform2D.rotate(angle_rad)` | Counter-clockwise rotation |
| `Transform2D.reflect_y()` | Flip Y axis (world↔screen) |
| `Transform2D.from_matrix(m)` | Wrap an existing 3×3 ndarray |
| `Transform2D.from_list(data)` | Deserialize from `list[list[float]]` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `t1 @ t2` | `Transform2D` | Compose transforms |
| `t.apply_to_array(pts)` | `ndarray (N,2)` | Apply to N×2 point array |
| `t.inverse()` | `Transform2D` | Matrix inverse |
| `t.is_identity(tol=1e-9)` | `bool` | True if matrix ≈ identity |
| `t.to_list()` | `list[list[float]]` | Serialize to nested list |

---

## Point2D

```python
class Point2D(BaseModel, frozen=True):
    x: float
    y: float
    crs: CoordinateSystem = WORLD
```

An immutable 2D position tagged with its coordinate system.

### Operators

| Expression | Result | Notes |
|------------|--------|-------|
| `Point2D + Vector2D` | `Point2D` | Displacement |
| `Point2D - Point2D` | `Vector2D` | Difference vector |
| `Point2D - Vector2D` | `Point2D` | Reverse displacement |
| `Point2D + Point2D` | `TypeError` | Meaningless; adding two positions |

All operators enforce CRS equality and raise `CRSMismatchError` on mismatch.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `p.distance_to(other)` | `float` | Euclidean distance (same CRS required) |
| `p.midpoint(other)` | `Point2D` | Midpoint between two points |
| `p.transformed(t)` | `Point2D` | Apply a `Transform2D` |
| `p.as_array()` | `ndarray (2,)` | `[x, y]` float64 |
| `p.as_tuple()` | `tuple[float, float]` | `(x, y)` |

---

## Point3D

```python
class Point3D(BaseModel, frozen=True):
    x: float
    y: float
    z: float
    crs: CoordinateSystem = WORLD
```

Same arithmetic contract as `Point2D`, extended to 3D.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `p.distance_to(other)` | `float` | 3D Euclidean distance |
| `p.as_array()` | `ndarray (3,)` | `[x, y, z]` float64 |
| `p.as_2d()` | `Point2D` | Drop Z component |

---

## Vector2D / Vector3D

```python
class Vector2D(BaseModel, frozen=True):
    x: float
    y: float
    crs: CoordinateSystem = WORLD
```

Vectors transform without translation (unlike points). Arithmetic enforces CRS equality.

### Key properties and methods (Vector2D)

| Member | Returns | Description |
|--------|---------|-------------|
| `v.magnitude` | `float` | Euclidean norm (`√(x²+y²)`) |
| `v.magnitude_sq` | `float` | Squared norm (avoids sqrt) |
| `v.normalized()` | `Vector2D` | Unit vector; raises `ValueError` on zero vector |
| `v.dot(other)` | `float` | Dot product (same CRS required) |
| `v.cross(other)` | `float` | 2D cross product scalar (`x₁y₂ − y₁x₂`) |
| `v.rotated(angle_rad)` | `Vector2D` | CCW rotation |
| `v.perpendicular()` | `Vector2D` | CCW perpendicular unit vector |
| `v.angle()` | `float` | Bearing from +X axis in radians (`atan2`) |
| `v.as_array()` | `ndarray (2,)` | `[x, y]` float64 |

Arithmetic (`+`, `-`, `*`, `/`, `neg`, `rmul`) all enforce CRS equality and return same-CRS vectors.

---

## BoundingBox2D

```python
class BoundingBox2D(BaseModel, frozen=True):
    min_corner: Point2D
    max_corner: Point2D
```

Axis-aligned bounding box.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `width` | `float` | max_x − min_x |
| `height` | `float` | max_y − min_y |
| `area` | `float` | width × height |
| `center` | `Point2D` | Centroid of the box |
| `crs` | `CoordinateSystem` | From `min_corner.crs` |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `BoundingBox2D.from_points(pts)` | `BoundingBox2D` | Compute tight box from an iterable of `Point2D` |
| `bb.contains_point(p)` | `bool` | True if point is inside or on boundary |
| `bb.intersects(other)` | `bool` | True if boxes overlap (inclusive on edges) |
| `bb.intersection(other)` | `BoundingBox2D \| None` | Overlapping region, or `None` if disjoint |
| `bb.union(other)` | `BoundingBox2D` | Smallest box containing both |
| `bb.expanded(delta)` | `BoundingBox2D` | All sides grown by `delta` meters |
| `bb.to_polygon()` | `Polygon2D` | Rectangle as a `Polygon2D` |

`BoundingBox3D` adds `depth` (max_z − min_z) and `volume` properties.

---

## Polygon2D

```python
class Polygon2D(BaseModel, frozen=True):
    exterior: tuple[Point2D, ...]
    holes: tuple[tuple[Point2D, ...], ...] = ()
    crs: CoordinateSystem = WORLD
```

A general 2D polygon — non-convex, with holes. Uses Shapely internally for geometric operations; Shapely objects are not stored in the model.

### Factories

| Method | Description |
|--------|-------------|
| `Polygon2D.rectangle(x, y, width, height, crs)` | Axis-aligned rectangle, lower-left at `(x, y)` |
| `Polygon2D.circle(cx, cy, radius, resolution, crs)` | Regular polygon approximating a circle |

### Properties / Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `poly.area` | `float` | Signed area in m² (exterior minus holes) |
| `poly.perimeter` | `float` | Exterior perimeter in meters |
| `poly.centroid` | `Point2D` | Centroid of the exterior |
| `poly.bounding_box()` | `BoundingBox2D` | Axis-aligned bounding box |
| `poly.contains_point(p)` | `bool` | Point-in-polygon (respects holes) |
| `poly.to_shapely()` | `shapely.Polygon` | Convert to Shapely for custom ops |

---

## Curve types

All curves inherit from `CurveBase` (abstract) and share:

```python
class CurveBase:
    crs: CoordinateSystem
    def length(self) -> float: ...
    def to_polyline(self, resolution: int = 32) -> list[Point2D]: ...
    def bounding_box(self) -> BoundingBox2D: ...
```

### ArcCurve

```python
class ArcCurve(BaseModel, frozen=True):
    center: Point2D
    radius: float
    start_angle: float   # radians, measured from +X axis
    end_angle: float     # radians
    clockwise: bool = False
    crs: CoordinateSystem = WORLD
```

A circular arc. `start_angle` and `end_angle` follow standard mathematical convention (counter-clockwise from +X axis) unless `clockwise=True`.

### BezierCurve

```python
class BezierCurve(BaseModel, frozen=True):
    control_points: tuple[Point2D, ...]  # 2..N control points
    crs: CoordinateSystem = WORLD
```

A polynomial Bézier curve. The degree is `len(control_points) - 1`. Common cases: 3 points = quadratic, 4 points = cubic.

### NURBSCurve

```python
class NURBSCurve(BaseModel, frozen=True):
    control_points: tuple[Point2D, ...]
    weights: tuple[float, ...]
    knots: tuple[float, ...]
    degree: int
    crs: CoordinateSystem = WORLD
```

A Non-Uniform Rational B-Spline. Uses the full Cox–de Boor algorithm (exact rational evaluation). Weights must match the number of control points. The knot vector length must equal `len(control_points) + degree + 1`.

### Factory: `NURBSCurve.clamped_uniform`

```python
NURBSCurve.clamped_uniform(
    control_points: tuple[Point2D, ...],
    degree: int,
    weights: tuple[float, ...] | None = None,   # defaults to all-ones
) -> NURBSCurve
```

Generates a standard clamped knot vector automatically. The curve passes exactly through the first and last control points. With `degree=3` this gives the standard cubic spline.

Pass non-uniform weights to produce rational curves (e.g. exact circles: set the middle weight to `cos(π/4)` for a quarter-circle).

### Additional curve properties

| Property / Method | Description |
|---|---|
| `curve.start_point` | Evaluate at start of domain |
| `curve.end_point` | Evaluate at end of domain |
| `curve.mid_point` | Evaluate at domain midpoint |
| `curve.domain` | `(t_min, t_max)` from knot vector (NURBSCurve only) |
| `curve.span_angle()` | Total arc span in radians (ArcCurve only) |
| `curve.transformed(t)` | New curve with transform applied |
| `curve.length(resolution=128)` | Arc length via polyline approximation |

---

## Segment2D

```python
class Segment2D(BaseModel, frozen=True):
    start: Point2D
    end: Point2D
    crs: CoordinateSystem = WORLD
```

A directed finite segment.

| Method | Returns | Description |
|--------|---------|-------------|
| `s.length` | `float` | Euclidean length |
| `s.direction` | `Vector2D` | Unit vector start→end |
| `s.midpoint` | `Point2D` | Midpoint |
| `s.vector` | `Vector2D` | Non-normalised start→end vector |
| `s.at(t)` | `Point2D` | Parametric point, `t ∈ [0, 1]` |
| `s.closest_point(p)` | `Point2D` | Nearest point on segment to `p` |
| `s.distance_to_point(p)` | `float` | Distance from `p` to segment |
| `s.intersect(other)` | `Point2D \| None` | Intersection of two segments |
| `s.reversed()` | `Segment2D` | Swap start/end |
| `s.as_polyline()` | `Polyline2D` | Two-point polyline |
| `s.as_line()` | `Line2D` | Extend to infinite line |
| `s.transformed(t)` | `Segment2D` | Apply transform |

---

## Ray2D

```python
class Ray2D(BaseModel, frozen=True):
    origin: Point2D
    direction: Vector2D    # need not be a unit vector
    crs: CoordinateSystem = WORLD
```

A half-line extending from `origin` in `direction`.

| Method | Returns | Description |
|--------|---------|-------------|
| `r.at(t)` | `Point2D` | `origin + t * direction`, `t ≥ 0` |
| `r.intersect_segment(seg)` | `Point2D \| None` | Ray–segment intersection |
| `r.intersect_line(line)` | `Point2D \| None` | Ray–line intersection |
| `r.to_segment(length)` | `Segment2D` | Finite segment of given length |
| `r.transformed(t)` | `Ray2D` | Apply transform |

---

## Line2D

```python
class Line2D(BaseModel, frozen=True):
    point: Point2D     # any point on the line
    direction: Vector2D
    crs: CoordinateSystem = WORLD
```

An infinite line.

| Method | Returns | Description |
|--------|---------|-------------|
| `Line2D.from_two_points(a, b)` | `Line2D` | Factory |
| `Line2D.from_segment(seg)` | `Line2D` | Extend segment to line |
| `line.normal` | `Vector2D` | CCW perpendicular unit vector |
| `line.project(p)` | `Point2D` | Orthogonal projection onto line |
| `line.closest_point(p)` | `Point2D` | Same as `project` |
| `line.distance_to_point(p)` | `float` | Perpendicular distance |
| `line.side_of(p)` | `float` | > 0 left, < 0 right, 0 on line |
| `line.intersect(other)` | `Point2D \| None` | Line–line intersection |
| `line.intersect_segment(seg)` | `Point2D \| None` | Line–segment intersection |
| `line.parallel_offset(d)` | `Line2D` | Parallel line at signed distance `d` |
| `line.as_ray()` | `Ray2D` | Half-line from `point` in `direction` |
| `line.transformed(t)` | `Line2D` | Apply transform |

---

## Polyline2D

```python
class Polyline2D(BaseModel, frozen=True):
    points: tuple[Point2D, ...]    # ordered sequence (≥ 2 points)
    crs: CoordinateSystem = WORLD
```

An ordered sequence of connected line segments.

| Method | Returns | Description |
|--------|---------|-------------|
| `pl.segments()` | `list[Segment2D]` | All consecutive segments |
| `pl.segment_at(i)` | `Segment2D` | Segment at index `i` |
| `pl.length` | `float` | Total polyline length |
| `pl.bbox()` | `BoundingBox2D` | Tight bounding box |
| `pl.closest_point(p)` | `Point2D` | Nearest point on any segment |
| `pl.reversed()` | `Polyline2D` | Reversed point order |
| `pl.append(p)` | `Polyline2D` | New polyline with `p` added at end |
| `pl.close()` | `Polyline2D` | Append first point to close the loop |
| `pl.to_polygon()` | `Polygon2D` | Close and convert to polygon |
| `pl.intersections(other)` | `list[Point2D]` | All intersection points with another polyline |
| `pl.transformed(t)` | `Polyline2D` | Apply transform to all points |
