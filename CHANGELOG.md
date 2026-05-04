# Changelog

All notable changes to `archit-app` are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.5.0 — 2026-05-03

### Added
- **Typed exception hierarchy** in `archit_app.core.errors`:
  `ArchitError` base + `OverlapError`, `OutOfBoundsError`,
  `ElementNotFoundError`, `GeometryError`, `SessionError`. Each carries
  `code`, optional `element_id`, and optional `hint` so downstream tools
  can render structured error payloads.
- **Structured building validation** — new `archit_app.analysis.validate.validate(building)`
  returns `list[Finding]` with `severity`, `code`, `element_id`,
  `level_index`, `message`, and `fix_hint`. Codes implemented:
  `orphan_wall`, `room_overlap`, `missing_perimeter`, `zero_length_wall`,
  `orphan_opening`, `duplicate_wall`, `level_walls_no_rooms`,
  `level_rooms_no_walls`.
- **`Opening.swing_arc(host_wall, …)`** and **`Opening.glazing_lines(host_wall)`** —
  derive door-swing polylines and window-glazing line segments directly in the
  geometry layer so every renderer (SVG / PDF / DXF / IFC) gets identical
  geometry.
- **`Wall.opening_at(position_along_wall)`** — convenience lookup.
- **`Level.walls_for_room(verbose=True)`** — verbose mode returns
  `{wall, intersection_area_m2, distance_to_room_m}` records for debugging
  tolerance issues.
- **Per-Level Shapely cache** — room-polygon and wall-bbox memoization keyed
  on the immutable Level instance via `WeakKeyDictionary`. Mutation produces
  a new instance which automatically invalidates.
- **Batch mutators on `Level` and `Building`** — `Level.add_openings`,
  `add_columns`, `add_beams`, `add_slabs`, `add_ramps`, `add_staircases`,
  `add_furniture_items`; `Building.add_levels`, `replace_levels`. Each
  performs a single tuple rebuild for large batches.

### Changed
- **Polished SVG / PDF exports** — title block, scale bar, north arrow,
  per-room labels with areas, dimension chains on exterior walls, dashed
  90° door swing arcs, and parallel window glazing lines. All use the
  brand palette: Void linework, Vellum background, Blueprint accents,
  Datum highlights.
- **Lazy heavy imports** — `numpy` and `shapely` are no longer imported at
  package load; they're pulled in inside the geometry/analysis paths that
  need them. `import archit_app` now succeeds on environments without
  numpy/shapely installed (the heavy paths still raise on use).

### Migration notes
- The error classes are infrastructure-only in this release; primitives
  still raise plain `Exception` in some places. If you wrap archit-app in
  a tool layer, you can already catch `ArchitError` for finer-grained
  recovery — but expect both branches for now.
- The polished SVG/PDF output adds chrome (title block, scale bar, north
  arrow). If you parse exported SVGs, the new `<g id="…">` groups are:
  `title-block`, `scale-bar`, `north-arrow`, `dimensions`, `room-labels`.

## 0.4.0 — 2026-04-19

- **Floorplan Agent Protocol v1.0.0** — strict Pydantic inter-agent message
  layer (`FloorplanSnapshot`, `AgentHandoff`, `MutationEnvelope`,
  `ProtocolReport`), discriminated-union parse, JSON Schema export CLI.
- `Opening.position_along_wall` field added.

## 0.3.5 — 2026-03-12

- Architectural SVG furniture symbols (19 plan-view category symbols).
- `Building.validate()` extended with overlap detection (Shapely) and
  door-connectivity checks (networkx).

## 0.3.4

- Wall geometry helpers — `Wall.start_point`, `Wall.end_point`,
  `Wall.facing_direction()`.
- Level batch APIs — `Level.add_walls(list)`, `Level.add_rooms(list)`,
  `Level.walls_for_room(room_id)`.
- Structured analysis findings — `egress_report()`, `daylight_report()`
  return per-element dicts with `compliant`, `issue`, `suggested_fix`.
- Enriched agent context — `Building.to_detailed_agent_context(...)`.

Earlier history: see git log.
