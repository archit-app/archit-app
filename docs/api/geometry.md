# API Reference — Geometry

```python
from floorplan import (
    CoordinateSystem, LengthUnit, YDirection,
    CRSMismatchError, require_same_crs,
    WORLD, SCREEN, IMAGE, WGS84,
    Transform2D,
    Point2D, Point3D,
    Vector2D, Vector3D,
    BoundingBox2D, BoundingBox3D,
    Polygon2D,
    ArcCurve, BezierCurve, NURBSCurve, CurveBase,
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

### Key methods (Vector2D)

| Method | Returns | Description |
|--------|---------|-------------|
| `v.length()` | `float` | Euclidean norm |
| `v.normalized()` | `Vector2D` | Unit vector |
| `v.dot(other)` | `float` | Dot product |
| `v.cross(other)` | `float` | 2D cross product (scalar) |
| `v.as_array()` | `ndarray (2,)` | `[x, y]` float64 |

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
| `center` | `Point2D` | Centroid of the box |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `BoundingBox2D.from_points(pts)` | `BoundingBox2D` | Compute from an iterable of `Point2D` |
| `bb.union(other)` | `BoundingBox2D` | Smallest box containing both |
| `bb.contains_point(p)` | `bool` | Point-in-box test |

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

A Non-Uniform Rational B-Spline. Weights must match the number of control points. The knot vector must satisfy standard NURBS constraints (length = `len(control_points) + degree + 1`).
