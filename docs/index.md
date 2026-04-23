<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../logo/archit-app-dark.svg">
  <img src="../logo/archit-app-light.svg" alt="archit-app" width="300">
</picture>

# archit_app Documentation

Welcome to the `archit_app` library documentation.

`archit_app` is a general-purpose, extensible Python library for architectural floorplan design and analysis. It provides a clean, layered data model with full support for non-Manhattan geometry, multi-level buildings, and standard interchange formats.

## Contents

### Guides

- [Getting Started](getting_started.md) — installation, quick start, and basic examples
- [Core Concepts](concepts.md) — coordinate systems, immutability, the element model, and design principles

### API Reference

- [Geometry](api/geometry.md) — `CoordinateSystem`, `CoordinateConverter`, `Point2D`, `Vector2D`, `Polygon2D`, `Transform2D`, curves, `Segment2D`, `Line2D`, `Polyline2D`
- [Elements](api/elements.md) — `Wall`, `Room`, `Opening`, `Column`, `Staircase`, `Slab`, `Ramp`, `Elevator`, `Beam`, `Furniture`, `TextAnnotation`, `DimensionLine`, `SectionMark`
- [Building](api/building.md) — `Level`, `Building`, `BuildingMetadata`, `Land`, `StructuralGrid`
- [I/O](api/io.md) — JSON, SVG, GeoJSON, DXF, IFC, PNG, PDF
- [Registry](api/registry.md) — plugin/extension system

### Development

- [Contributing](contributing.md) — setup, testing, coding standards, and how to add features

## Package info

| | |
|---|---|
| Version | 0.3.3 |
| Python | 3.11+ |
| License | MIT |
| Source | [github.com/archit-app/archit-app](https://github.com/archit-app/archit-app) |
