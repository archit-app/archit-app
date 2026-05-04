# Cookbook

Worked examples for the most common tasks. The README has the elevator pitch
and a minimal Quick Start; this page is the recipe book.

> **Prerequisites:** install the relevant optional extras
> (`pip install "archit-app[io,ifc,image,pdf,analysis]"`).

---

## Contents

- [Define a land parcel and get agent context](#define-a-land-parcel-and-get-agent-context)
- [Export — SVG / JSON / GeoJSON](#export--svg--json--geojson)
- [Export — DXF round-trip](#export--dxf-round-trip)
- [Export — PNG (raster)](#export--png-raster)
- [Export — PDF](#export--pdf)
- [Export — IFC 4.x](#export--ifc-4x)
- [Vertical circulation and structural elements](#vertical-circulation-and-structural-elements)
- [Structural grid and wall joining](#structural-grid-and-wall-joining)
- [NURBS curved walls](#nurbs-curved-walls)
- [Coordinate conversion](#coordinate-conversion)
- [Layer visibility and material-linked rendering](#layer-visibility-and-material-linked-rendering)
- [Unit conversion](#unit-conversion)
- [Element transform utilities](#element-transform-utilities)
- [Building validation and agent context](#building-validation-and-agent-context)
- [Floorplan Agent Protocol](#floorplan-agent-protocol)
- [Spatial index](#spatial-index)
- [GeoJSON import](#geojson-import)
- [Wall geometry helpers](#wall-geometry-helpers)
- [Level batch creation and spatial query](#level-batch-creation-and-spatial-query)
- [Spatial analysis](#spatial-analysis)
- [Structured findings — `validate(building)` (v0.5.0+)](#structured-findings--validatebuilding-v050)
- [Door swing and window glazing geometry (v0.5.0+)](#door-swing-and-window-glazing-geometry-v050)

---

## Define a land parcel and get agent context

```python
from archit_app import Land, Setbacks, ZoningInfo, Building

# 1. Define the parcel from GPS coordinates
land = Land.from_latlon([
    (37.7749, -122.4194),
    (37.7750, -122.4194),
    (37.7750, -122.4183),
    (37.7749, -122.4183),
], address="123 Main St, San Francisco, CA")

print(f"Lot area: {land.area_m2:.1f} m²")

# 2. Export a context dict — pass this to an AI agent to get zoning info
context = land.to_agent_context()

# 3. Enrich with zoning (manually or from an agent response)
land = (
    land
    .with_zoning(ZoningInfo(
        zone_code="RH-2", max_height_m=10.0, max_far=1.8,
        max_lot_coverage=0.6, allowed_uses=("residential",),
        source="SF Planning Code §207",
    ))
    .with_setbacks(Setbacks(front=3.0, back=6.0, left=1.5, right=1.5))
)

print(f"Buildable area: {land.buildable_area_m2:.1f} m²")
print(f"Max floor area: {land.max_floor_area_m2:.1f} m²")

building = Building().with_land(land)
```

---

## Export — SVG / JSON / GeoJSON

```python
from archit_app.io.svg import level_to_svg, save_level_svg
from archit_app.io.json_schema import save_building, load_building
from archit_app.io.geojson import level_to_geojson
import json

# SVG
svg_str = level_to_svg(ground, pixels_per_meter=50)
save_level_svg(ground, "ground_floor.svg", pixels_per_meter=50)

# JSON (round-trippable)
save_building(building, "my_house.archit_app.json")
restored = load_building("my_house.archit_app.json")

# GeoJSON
fc = level_to_geojson(ground)
print(json.dumps(fc, indent=2))
```

---

## Export — DXF round-trip

```python
# Requires: pip install "archit-app[io]"
from archit_app.io.dxf import (
    save_building_dxf, building_from_dxf,
    save_level_dxf, level_from_dxf,
)

save_building_dxf(building, "my_house.dxf")

# Auto-detects archit-app's FP_* layer convention
restored = building_from_dxf("my_house.dxf")

# Single level + override defaults
level = level_from_dxf("floor_plan.dxf", wall_height=3.5, wall_thickness=0.25)

# Generic DXF with custom layer names
level = level_from_dxf(
    "autocad_drawing.dxf",
    layer_mapping={"A-WALL": "walls", "A-FLOR-PATT": "rooms"},
)
```

Recognised element types in `layer_mapping`: `"walls"`, `"rooms"`,
`"openings"`, `"columns"`.

---

## Export — PNG (raster)

```python
# Requires: pip install "archit-app[image]"
from archit_app.io.image import save_level_png, save_building_pngs, level_to_png_bytes

save_level_png(ground, "ground_floor.png", pixels_per_meter=100, dpi=150)
save_building_pngs(building, "output/", pixels_per_meter=100, dpi=150)

# Raw bytes for HTTP responses
png_bytes = level_to_png_bytes(ground, pixels_per_meter=100)
```

Renders rooms, walls, columns, openings, room labels with area, and a 1 m
scale bar. Uses 2× supersampling for clean anti-aliased edges.

---

## Export — PDF

```python
# Requires: pip install "archit-app[pdf]"
from archit_app.io.pdf import save_level_pdf, save_building_pdf, level_to_pdf_bytes

# Single level — auto-selects landscape if drawing is wider than tall
save_level_pdf(ground, "ground_floor.pdf", paper_size="A3")

# All levels in one multi-page PDF
save_building_pdf(building, "my_house.pdf", paper_size="A3")

# Force portrait, A4
save_level_pdf(ground, "ground_portrait.pdf", paper_size="A4", landscape=False)

pdf_bytes = level_to_pdf_bytes(ground, paper_size="A3")
```

Supported sizes: `"A1"`, `"A2"`, `"A3"` (default), `"A4"`, `"letter"`. Each
level is centred and scaled to fill the page. v0.5.0+ output includes a
title block, scale bar, north arrow, room labels with areas, exterior
dimension chains, dashed door swing arcs, and parallel window glazing
lines — all in the brand palette.

---

## Export — IFC 4.x

```python
# Requires: pip install "archit-app[ifc]"
from archit_app.io.ifc import building_to_ifc, save_building_ifc, building_from_ifc, level_from_ifc

# Export
model = building_to_ifc(building)
print(model.by_type("IfcWall"))
print(model.by_type("IfcSpace"))
save_building_ifc(building, "my_house.ifc")

# Import
building = building_from_ifc("my_house.ifc")
ground = level_from_ifc("my_house.ifc", storey_index=0)
```

Element-type mapping: `Wall`↔`IfcWall`, `Room`↔`IfcSpace`,
`Opening`↔`IfcDoor`/`IfcWindow`, `Column`↔`IfcColumn`, `Slab`↔`IfcSlab`,
`Staircase`↔`IfcStair`, `Ramp`↔`IfcRamp`, `Beam`↔`IfcBeam`,
`Furniture`↔`IfcFurnishingElement`, `Elevator`↔`IfcTransportElement`. Full
`IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey` hierarchy.

---

## Vertical circulation and structural elements

```python
import math
from archit_app import (
    Staircase, Slab, Ramp, Elevator, Beam, BeamSection, Level, Building,
)

stair = Staircase.straight(
    x=6, y=0, width=1.2, rise_count=12,
    rise_height=0.175, run_depth=0.28,
    bottom_level_index=0, top_level_index=1,
)

slab = Slab.rectangular(x=0, y=0, width=10, depth=8, thickness=0.2, elevation=0.0)

ramp = Ramp.straight(x=0, y=0, width=1.5, length=3.6,
                     slope_angle=math.radians(4.76),
                     bottom_level_index=0, top_level_index=1)

elevator = Elevator.rectangular(x=8, y=0, cab_width=1.1, cab_depth=1.4,
                                bottom_level_index=0, top_level_index=3)

beam = Beam.straight(x1=0, y1=0, x2=6, y2=0,
                     width=0.3, depth=0.5, elevation=3.5,
                     section=BeamSection.RECTANGULAR)

ground = (
    Level(index=0, elevation=0.0, floor_height=3.0)
    .add_staircase(stair)
    .add_slab(slab)
    .add_ramp(ramp)
    .add_beam(beam)
)
building = Building().add_level(ground).add_elevator(elevator)
```

---

## Structural grid and wall joining

```python
from archit_app import StructuralGrid, Wall, join_walls, miter_join, Point2D, WORLD

grid = StructuralGrid.regular(x_spacing=6.0, y_spacing=6.0, x_count=3, y_count=3)
pt = grid.intersection("2", "B")        # Point2D(x=6.0, y=6.0, ...)
snapped = grid.snap_to_grid(Point2D(x=5.95, y=6.1, crs=WORLD), tolerance=0.2)
building = Building().with_grid(grid)

# Clean up wall corners with miter joins
wall_h = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
wall_v = Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0)
wall_h_trimmed, wall_v_trimmed = miter_join(wall_h, wall_v)

# Or join a whole room's walls at once
joined_walls = join_walls([
    Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0),
    Wall.straight(5, 0, 5, 4, thickness=0.2, height=3.0),
    Wall.straight(5, 4, 0, 4, thickness=0.2, height=3.0),
    Wall.straight(0, 4, 0, 0, thickness=0.2, height=3.0),
])
```

---

## NURBS curved walls

```python
import math
from archit_app import Point2D, WORLD, Wall
from archit_app.geometry.curve import NURBSCurve

# Smooth cubic curve through 5 control points (clamped — passes through endpoints)
ctrl = (
    Point2D(0, 0, crs=WORLD), Point2D(1, 2, crs=WORLD), Point2D(2, 0, crs=WORLD),
    Point2D(3, 2, crs=WORLD), Point2D(4, 0, crs=WORLD),
)
curve = NURBSCurve.clamped_uniform(ctrl, degree=3)
polyline = curve.to_polyline(resolution=64)
print(f"Arc length ≈ {curve.length():.3f} m")

# Exact quarter-circle via rational NURBS (w = cos(π/4) on the middle point)
w = math.cos(math.pi / 4)
quarter_circle = NURBSCurve.clamped_uniform(
    (Point2D(1, 0, crs=WORLD), Point2D(1, 1, crs=WORLD), Point2D(0, 1, crs=WORLD)),
    degree=2, weights=(1.0, w, 1.0),
)

# NURBS as wall geometry
wall = Wall(geometry=curve.to_polygon(resolution=32), thickness=0.2, height=3.0)
```

---

## Coordinate conversion

```python
from archit_app import build_default_converter, SCREEN, WORLD, IMAGE, Point2D

conv = build_default_converter(
    viewport_height_px=600.0, pixels_per_meter=50.0,
    canvas_origin_world=(0.0, 0.0),
)

screen_click = Point2D(x=400.0, y=300.0, crs=SCREEN)
world_pos = screen_click.to(WORLD, conv)
back = world_pos.to(SCREEN, conv)

# IMAGE → WORLD resolves via BFS through SCREEN
import numpy as np
world_pts = conv.convert(np.array([[400.0, 300.0]]), IMAGE, WORLD)

# Custom CRS — multi-hop paths are found automatically
from archit_app import WGS84
conv.register(WORLD, WGS84, some_georeference_transform)
# Now IMAGE → WGS84 resolves as IMAGE → SCREEN → WORLD → WGS84
```

---

## Layer visibility and material-linked rendering

```python
from archit_app import Building
from archit_app.building.layer import Layer
from archit_app.io.svg import level_to_svg
from archit_app.materials import default_library

building = (
    Building()
    .add_layer(Layer(name="structure", color_hex="#808080", visible=True))
    .add_layer(Layer(name="finishes",  color_hex="#C8A080", visible=False))
    .add_level(ground)
)

# SVG only renders elements whose layer is in the visible set
svg = level_to_svg(ground, visible_layers={"structure"})

# Material-linked colours
svg = level_to_svg(ground, material_library=default_library)
```

---

## Unit conversion

```python
from archit_app.units import (
    to_feet, from_feet, to_inches, from_inches,
    to_mm, from_mm, to_cm, from_cm, parse_dimension,
)

print(to_feet(3.048))           # 10.0
print(from_feet(10.0))          # 3.048
print(to_mm(1.0))               # 1000.0

print(parse_dimension("12'-6\""))   # 3.81  (meters)
print(parse_dimension("3800mm"))    # 3.8
print(parse_dimension("10ft"))      # 3.048
print(parse_dimension("3.5"))       # 3.5   (bare float → meters)
```

---

## Element transform utilities

```python
from archit_app.elements.transform_utils import copy_element, mirror_element, array_element
from archit_app import Wall

wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)

wall2     = copy_element(wall, dx=0, dy=3.0)         # translate
mirrored  = mirror_element(wall, axis_y=2.5)         # mirror about y = 2.5
row       = array_element(wall, count=4, dx=6.0, dy=0)  # 4 walls 6 m apart
```

---

## Building validation and agent context

```python
from archit_app import Building

building = Building().add_level(ground)

# Legacy validate() — quick pass/fail
report = building.validate()
if report.has_errors:
    for issue in report.issues:
        print(f"[{issue.severity.upper()}] {issue.message}")

# v0.5.0+: structured findings with fix hints
from archit_app.analysis.validate import validate
findings = validate(building)
for f in findings:
    print(f"{f.severity:8s} {f.code:24s} {f.message}")
    if f.fix_hint:
        print(f"  fix: {f.fix_hint}")

# Flat agent context (legacy)
ctx = building.to_agent_context()

# v0.4+: validated FloorplanSnapshot (Floorplan Agent Protocol v1)
snap = building.to_protocol_snapshot(mode="compact", building_revision=0)
agent_json = snap.model_dump_json(exclude_none=True)

# Duplicate a level (fresh UUIDs for all elements)
building2 = building.duplicate_level(src_index=0, new_index=1, new_elevation=3.0)
```

---

## Floorplan Agent Protocol

```python
from archit_app.protocol import (
    FloorplanSnapshot, AgentHandoff, MutationEnvelope, ProtocolReport,
    parse_message, dump_message, PROTOCOL_VERSION,
)
from archit_app.protocol.handoff import Decision
from archit_app.protocol import compliance_report_to_protocol

snap = building.to_protocol_snapshot(mode="compact")
print(PROTOCOL_VERSION)    # "1.0.0"

handoff = AgentHandoff(
    agent_role="architect",
    summary="Placed 6 rooms on level 0; total net area 87 m².",
    decisions=(Decision(title="Compact footprint", rationale="10×9 m fits the brief."),),
)

# Analysis adapter
from archit_app.analysis.compliance import check_compliance
raw = check_compliance(building, land)
report = compliance_report_to_protocol(raw)
print(report.kind)          # "compliance"

# Discriminated-union parsing
msg = parse_message(handoff.model_dump_json())   # → AgentHandoff
raw = dump_message(msg)

# JSON Schema export
from archit_app.protocol.schema_export import export_schemas
export_schemas("./schemas/")
```

---

## Spatial index

```python
# Requires: pip install shapely
from shapely.geometry import box

tree, elements = ground.spatial_index()

hits = tree.query(box(0, 0, 3, 3))
nearby = [elements[i] for i in hits]
print([type(e).__name__ for e in nearby])   # ["Wall", "Room", ...]
```

---

## GeoJSON import

```python
from archit_app.io.geojson import (
    level_to_geojson, level_from_geojson,
    level_to_geojson_str, level_from_geojson_str,
)

fc = level_to_geojson(ground)

restored = level_from_geojson(fc, index=0, elevation=0.0, floor_height=3.0)
assert len(restored.rooms) == len(ground.rooms)

json_str  = level_to_geojson_str(ground)
restored2 = level_from_geojson_str(json_str)
```

---

## Wall geometry helpers

```python
from archit_app import Wall

wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)

print(wall.start_point)         # (0.0, 0.0)
print(wall.end_point)            # (6.0, 0.0)
print(wall.facing_direction())   # "N"  (wall runs E–W → normal faces N)
```

---

## Level batch creation and spatial query

```python
from archit_app import Wall, Room, Level, Polygon2D, WORLD

r1 = Room(boundary=Polygon2D.rectangle(0, 0, 6, 4, crs=WORLD), name="Living", program="living")
r2 = Room(boundary=Polygon2D.rectangle(6, 0, 4, 4, crs=WORLD), name="Kitchen", program="kitchen")
w1 = Wall.straight(0, 4, 10, 4, thickness=0.2, height=3.0)
w2 = Wall.straight(10, 0, 10, 4, thickness=0.2, height=3.0)

# Single tuple rebuild for the whole batch (v0.3.4+ for rooms/walls,
# v0.5.0+ for openings/columns/beams/slabs/ramps/staircases/furniture).
ground = (
    Level(index=0, elevation=0.0, floor_height=3.0)
    .add_rooms([r1, r2])
    .add_walls([w1, w2])
)

# Spatial query — find walls adjacent to a room
adjacent = ground.walls_for_room(r1.id, tolerance_m=0.35)

# v0.5.0+: verbose mode returns intersection_area_m2 + distance_to_room_m per match
adjacent_dbg = ground.walls_for_room(r1.id, verbose=True)
```

---

## Spatial analysis

```python
from archit_app.analysis.topology import build_adjacency_graph, connected_components
from archit_app.analysis.circulation import egress_report
from archit_app.analysis.area import area_by_program, area_report, AreaTarget
from archit_app.analysis.compliance import check_compliance
from archit_app.analysis.daylighting import daylight_report
from archit_app.analysis.visibility import compute_isovist, mutual_visibility

# Adjacency graph (requires pip install archit-app[analysis])
G = build_adjacency_graph(ground)
components = connected_components(G)

# Egress (auto-detects exits from "exit"/"lobby" programs)
report = egress_report(ground)
# {"overall_compliant", "max_distance_m", "exit_count", "rooms": [...], "failed_rooms": [...]}

# Area program validation
totals = area_by_program(building)
results = area_report(building, targets=[
    AreaTarget(program="bedroom", target_m2=30.0, tolerance_fraction=0.10),
    AreaTarget(program="kitchen", target_m2=10.0),
])

# Zoning compliance
compliance = check_compliance(building, land)
print(compliance.summary())

# Daylighting (compliant flag + issue + suggested_fix per room)
daylight = daylight_report(ground, north_angle_deg=15.0)

# Isovist (visibility polygon)
from archit_app import Point2D, WORLD
result = compute_isovist(Point2D(x=5.0, y=3.0, crs=WORLD), ground,
                         resolution=360, max_range=20.0)
can_see = mutual_visibility(Point2D(x=2, y=2, crs=WORLD),
                             Point2D(x=8, y=2, crs=WORLD), ground)
```

---

## Structured findings — `validate(building)` (v0.5.0+)

```python
from archit_app.analysis.validate import validate

findings = validate(building)
for f in findings:
    print(f"{f.severity:7s} {f.code:24s} on level {f.level_index}: {f.message}")
    if f.fix_hint:
        print(f"        → {f.fix_hint}")

errors   = [f for f in findings if f.severity == "error"]
warnings = [f for f in findings if f.severity == "warning"]
```

Codes implemented: `orphan_wall`, `room_overlap`, `missing_perimeter`,
`zero_length_wall`, `orphan_opening`, `duplicate_wall`,
`level_walls_no_rooms`, `level_rooms_no_walls`.

---

## Door swing and window glazing geometry (v0.5.0+)

```python
# Both methods derive geometry from the host wall's frame.
# Returns are in the same CRS as Opening.geometry (typically WORLD).

door = wall.openings[0]                 # an Opening of kind=DOOR
arc_pts = door.swing_arc(host_wall=wall)  # list[Point2D] | None
# 17 points (16 segments) approximating a 90° sweep from the hinge.

window = wall.openings[1]               # an Opening of kind=WINDOW
glazing = window.glazing_lines(host_wall=wall)
# list[(Point2D, Point2D)] | None — two parallel segments along the opening width.
```

`Opening.swing_arc()` returns `None` for non-doors and curve-based walls.
`Opening.glazing_lines()` returns `None` for doors and openings without
glass. Both are pure (no mutation).
