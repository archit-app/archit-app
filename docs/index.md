<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../logo/archit-app-dark.svg">
  <img src="../logo/archit-app-light.svg" alt="archit-app" width="300">
</picture>

# archit_app Documentation

Welcome to the `archit_app` library documentation.

`archit_app` is a general-purpose, extensible Python library for architectural floorplan design and analysis. It provides a clean, layered data model with full support for non-Manhattan geometry, multi-level buildings, and standard interchange formats.

## What's new in 0.5.0

- **Typed error hierarchy** — `ArchitError`, `OverlapError`, `OutOfBoundsError`, `ElementNotFoundError`, `GeometryError`, `SessionError`. See [`api/errors.md`](api/errors.md) (or `archit_app.core.errors`).
- **Structured `validate(building)`** — `archit_app.analysis.validate` returns `list[Finding]` with severity, code, message, and paste-ready `fix_hint`.
- **Opening render geometry** — `Opening.swing_arc()` and `Opening.glazing_lines()` derive door swing arcs and window glazing in the geometry layer; every renderer shares the same output.
- **Polished SVG / PDF** — title block, scale bar, north arrow, room labels with areas, exterior dimension chains, swing arcs, glazing lines, brand palette.
- **Lazy `numpy`/`shapely`** — `import archit_app` is now numpy/shapely-free at module load.
- **Per-Level Shapely cache** + new batch mutators (`Level.add_openings`, `add_columns`, etc.; `Building.add_levels`, `replace_levels`).

See the full [CHANGELOG](../CHANGELOG.md) for details.

## Contents

### Guides

- [Getting Started](getting_started.md) — installation, quick start, and basic examples
- [Core Concepts](concepts.md) — coordinate systems, immutability, the element model, and design principles

### API Reference

- [Geometry](api/geometry.md) — `CoordinateSystem`, `CoordinateConverter`, `Point2D`, `Vector2D`, `Polygon2D`, `Transform2D`, curves, `Segment2D`, `Line2D`, `Polyline2D`
- [Elements](api/elements.md) — `Wall`, `Room`, `Opening`, `Column`, `Staircase`, `Slab`, `Ramp`, `Elevator`, `Beam`, `Furniture`, `TextAnnotation`, `DimensionLine`, `SectionMark`
- [Building](api/building.md) — `Level`, `Building`, `BuildingMetadata`, `Land`, `StructuralGrid`
- [I/O](api/io.md) — JSON, SVG, GeoJSON, DXF, IFC, PNG, PDF
- [Agent Protocol](api/protocol.md) — `FloorplanSnapshot`, `AgentHandoff`, `MutationEnvelope`, `ProtocolReport`, versioning, JSON Schema export
- [Registry](api/registry.md) — plugin/extension system

### Development

- [Contributing](contributing.md) — setup, testing, coding standards, and how to add features

## Package info

| | |
|---|---|
| Version | 0.5.0 |
| Python | 3.11+ |
| License | MIT |
| Source | [github.com/archit-app/archit-app](https://github.com/archit-app/archit-app) |
