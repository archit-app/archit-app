<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../logo/archit-app-dark.svg">
  <img src="../logo/archit-app-light.svg" alt="floorplan" width="320">
</picture>

# floorplan Documentation

Welcome to the `floorplan` library documentation.

`floorplan` is a general-purpose, extensible Python library for architectural floorplan design and analysis. It provides a clean, layered data model with full support for non-Manhattan geometry, multi-level buildings, and standard interchange formats.

## Contents

### Guides

- [Getting Started](getting_started.md) — installation, quick start, and basic examples
- [Core Concepts](concepts.md) — coordinate systems, immutability, the element model, and design principles

### API Reference

- [Geometry](api/geometry.md) — `CoordinateSystem`, `Point2D`, `Vector2D`, `Polygon2D`, `Transform2D`, curves
- [Elements](api/elements.md) — `Wall`, `Room`, `Opening`, `Column`, `Element`
- [Building](api/building.md) — `Level`, `Building`, `BuildingMetadata`, `SiteContext`
- [I/O](api/io.md) — JSON, SVG, GeoJSON, DXF exporters
- [Registry](api/registry.md) — plugin/extension system

### Development

- [Contributing](contributing.md) — setup, testing, coding standards, and how to add features

## Package info

| | |
|---|---|
| Version | 0.1.0 |
| Python | 3.11+ |
| License | MIT |
| Source | [github.com/…/floorplan](https://github.com) |
