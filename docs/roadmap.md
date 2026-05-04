# Roadmap

A living checklist of capability areas and what's landed in each. For a
chronological, version-tagged history see [`CHANGELOG.md`](../CHANGELOG.md).

| Phase | Status | Description |
|-------|--------|-------------|
| Layer 1 — Geometry | Done | CRS, Point, Vector, BBox, Polygon, Curve, Transform, Segment2D/Ray2D/Line2D/Polyline2D |
| Layer 2 — Elements (core) | Done | Wall, Room, Opening, Column, Furniture, TextAnnotation, DimensionLine, SectionMark |
| Layer 2 — Elements (circulation/structural) | Done | Staircase, Ramp, Elevator, Slab, Beam, StructuralGrid, wall joining |
| Layer 3 — Building | Done | Level, Building, Land, Setbacks, ZoningInfo |
| Layer 5 — I/O | Done | JSON, SVG, GeoJSON, DXF (read+write), IFC 4.x, PNG, PDF |
| Layer 6 — Analysis | Done | Topology graph, egress, area validation, zoning compliance, daylighting, isovist |
| `CoordinateConverter` | Done | Graph-based multi-CRS path-finding; `Point2D.to()` |
| NURBS evaluator | Done | Cox–de Boor; `clamped_uniform()` factory; exact conic sections |
| Layer 4 — App infrastructure | Done | `ElementQuery` (select/filter), `History` (undo/redo), `Viewport` (view state) |
| Material registry | Done | `Material`, `MaterialLibrary`, 12 builtin presets, `default_library` |
| Level / Building utilities | Done | `Level.replace_element()`, `Building.stats()` → `BuildingStats` |
| Analysis completeness | Done | Accessibility checker, room-from-walls auto-detection |
| JSON migration | Done | `migrate_json()` — upgrades 0.1.0 → 0.2.0 snapshots |
| I/O completeness | Done | SVG/PDF/PNG render furniture, beams, ramps, annotations, dimensions, section marks, staircases, slabs, archways; material-linked SVG fill colours; DXF annotation/dimension/section-mark layers; IFC extended export |
| GeoJSON round-trip | Done | `level_from_geojson()` / `level_from_geojson_str()` import |
| IFC round-trip | Done | `building_from_ifc()` / `level_from_ifc()` import; full element type coverage |
| Layer registry | Done | `Layer` model; building-level layer registry; renderer visibility filtering |
| Unit conversion | Done | `parse_dimension()`, `to_feet/inches/mm/cm`, `from_feet/inches/mm/cm` |
| Element transforms | Done | `copy_element`, `mirror_element`, `array_element` |
| Building utilities | Done | `validate()` → `ValidationReport`, `to_agent_context()`, `duplicate_level()` |
| Spatial index | Done | `Level.spatial_index()` → Shapely `STRtree` over all elements |
| Wall geometry helpers | Done | `Wall.start_point`, `Wall.end_point`, `Wall.facing_direction()` — 8-point compass |
| Level batch APIs | Done | `Level.add_walls(list)`, `Level.add_rooms(list)`, `Level.walls_for_room(room_id)` |
| Structured analysis findings | Done | `egress_report()` returns structured dict with `issue`/`suggested_fix`; `daylight_report()` adds `compliant`, `issue`, `suggested_fix` per room |
| Enriched agent context | Done | `Building.to_detailed_agent_context(...)` — scoped, with wall endpoints + facing |
| Architectural SVG furniture symbols | Done | 19 plan-view symbols per furniture category |
| Extended building validation | Done | `Building.validate()` detects room overlaps and door connectivity gaps |
| Floorplan Agent Protocol v1.0.0 | Done | `FloorplanSnapshot`, `AgentHandoff`, `MutationEnvelope`, `ProtocolReport`, discriminated-union parse, 5 analysis adapters, JSON Schema export CLI |
| Typed error hierarchy *(v0.5.0)* | Done | `ArchitError` base + `OverlapError`, `OutOfBoundsError`, `ElementNotFoundError`, `GeometryError`, `SessionError` — each with `code`, optional `element_id`, optional `hint` |
| Structured `validate(building)` *(v0.5.0)* | Done | `archit_app.analysis.validate` returns `list[Finding]` with severity, code, element id, message, paste-ready `fix_hint` |
| Opening render geometry *(v0.5.0)* | Done | `Opening.swing_arc()` + `Opening.glazing_lines()` — every renderer shares identical door-swing and glazing geometry |
| Polished SVG / PDF exports *(v0.5.0)* | Done | Title block, scale bar, north arrow, per-room labels with areas, exterior dimension chains, dashed swing arcs, glazing lines — Void / Vellum / Blueprint / Datum palette |
| Lazy heavy imports + per-Level Shapely cache *(v0.5.0)* | Done | `import archit_app` no longer pulls numpy/shapely; `Level.walls_for_room()` memoizes per immutable Level instance via `WeakKeyDictionary` |
| Batch mutators *(v0.5.0)* | Done | `Level.add_openings`, `add_columns`, `add_beams`, `add_slabs`, `add_ramps`, `add_furniture_items`; `Building.add_levels`, `replace_levels` |
