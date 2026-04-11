# API Reference — I/O

`archit_app` supports four interchange formats. All exporters work at the `Building` and `Level` level.

---

## JSON (canonical format)

```python
from archit_app.io.json_schema import (
    building_to_json, building_from_json,
    building_to_dict, building_from_dict,
    save_building, load_building,
)
```

The canonical JSON format is:

- Human-readable (pretty-printed by default)
- Fully round-trippable — serialize → deserialize → identical object graph
- Forward-compatible via a `_archit_app_version` field

### Functions

#### `building_to_json(building, indent=2) → str`

Serialize a `Building` to a JSON string.

```python
json_str = building_to_json(building, indent=2)
```

#### `building_from_json(s) → Building`

Deserialize a `Building` from a JSON string.

```python
building = building_from_json(json_str)
```

#### `building_to_dict(building) → dict`

Serialize a `Building` to a JSON-serializable `dict`. Useful for embedding in larger documents.

#### `building_from_dict(data) → Building`

Reconstruct a `Building` from a dict (as produced by `building_to_dict`).

#### `save_building(building, path, indent=2) → None`

Write a `Building` to a file. The conventional extension is `.archit_app.json`.

```python
save_building(building, "project.archit_app.json")
```

#### `load_building(path) → Building`

Read a `Building` from a `.archit_app.json` file.

```python
building = load_building("project.archit_app.json")
```

### File format overview

```json
{
  "_archit_app_version": "0.1.0",
  "metadata": {
    "name": "My House",
    "project_number": "",
    "architect": "",
    "client": "",
    "date": ""
  },
  "levels": [
    {
      "index": 0,
      "elevation": 0.0,
      "floor_height": 3.0,
      "name": "Ground Floor",
      "walls": [ ... ],
      "rooms": [ ... ],
      "openings": [ ... ],
      "columns": [ ... ]
    }
  ],
  "site": null
}
```

All UUIDs are serialized as strings. All `Transform2D` objects are stored as `[[row], [row], [row]]` nested lists. CRS is stored by name (`"world"`, `"screen"`, `"image"`, `"geographic"`).

---

## SVG

```python
from archit_app.io.svg import (
    level_to_svg,
    building_to_svg_pages,
    save_level_svg,
    save_building_svgs,
)
```

Renders clean 2D floorplan diagrams as SVG. Rooms, walls, openings, columns, labels, and a scale bar are all rendered. Coordinate system: world Y-up is automatically flipped to SVG Y-down.

### `level_to_svg`

```python
level_to_svg(
    level: Level,
    pixels_per_meter: float = 50.0,
    margin: float = 40,
    title: str | None = None,
    palette: dict | None = None,
) -> str
```

Render a single level as an SVG string.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pixels_per_meter` | `50.0` | Drawing scale. 50 px/m ≈ 1:20 at 96 dpi |
| `margin` | `40` | Padding around the drawing in pixels |
| `title` | `None` | Title text. Defaults to `level.name` or `"Level N"` |
| `palette` | `None` | Dict to override default colors (see below) |

### `building_to_svg_pages`

```python
building_to_svg_pages(
    building: Building,
    pixels_per_meter: float = 50.0,
    margin: float = 40,
) -> list[tuple[int, str]]
```

Render each level as a separate SVG. Returns a list of `(level_index, svg_string)` tuples.

### `save_level_svg`

```python
save_level_svg(level: Level, path: str, **kwargs) -> None
```

Write a level's SVG to a file. Keyword arguments are passed to `level_to_svg`.

### `save_building_svgs`

```python
save_building_svgs(building: Building, directory: str, **kwargs) -> list[str]
```

Write one SVG per level to `directory`. Returns the list of file paths written. The directory is created if it does not exist. Files are named `level_00.svg`, `level_01.svg`, etc.

### Color palette

Override any color by passing a `palette` dict to `level_to_svg`:

```python
svg = level_to_svg(level, palette={
    "room_fill": "#E8F4E8",
    "wall_fill": "#333333",
})
```

Default palette keys: `room_fill`, `room_stroke`, `wall_fill`, `wall_stroke`, `column_fill`, `column_stroke`, `door_fill`, `door_stroke`, `window_fill`, `window_stroke`, `background`, `room_label`, `annotation`.

**Example:**

```python
from archit_app.io.svg import save_building_svgs

paths = save_building_svgs(building, directory="output/svgs", pixels_per_meter=80)
for p in paths:
    print(f"Wrote {p}")
```

---

## GeoJSON

```python
from archit_app.io.geojson import (
    level_to_geojson,
    building_to_geojson,
    level_to_geojson_string,
    building_to_geojson_string,
)
```

Exports floorplan elements as GeoJSON `FeatureCollection`. Useful for loading into GIS tools (QGIS, Mapbox, Leaflet, etc.) and for spatial analysis.

**Note:** Coordinates are in the CRS of the elements (meters by default). If you need geographic coordinates (lat/lon), apply a georeferencing transform before exporting.

### `level_to_geojson`

```python
level_to_geojson(level: Level) -> dict
```

Returns a GeoJSON `FeatureCollection` dict containing all rooms, walls, openings, and columns as `Feature` objects. Each feature carries its element type, UUID, tags, and layer as GeoJSON properties.

### `building_to_geojson`

```python
building_to_geojson(building: Building) -> dict
```

Returns a merged `FeatureCollection` from all levels. Each feature has a `level_index` property.

### `level_to_geojson_string` / `building_to_geojson_string`

Convenience wrappers that return a JSON string instead of a dict.

**Example:**

```python
from archit_app.io.geojson import level_to_geojson
import json

fc = level_to_geojson(ground_level)
print(json.dumps(fc, indent=2))
```

---

## DXF

```python
from archit_app.io.dxf import (
    building_to_dxf,
    level_to_dxf,
    save_building_dxf,
)
```

> **Requires:** `pip install "archit-app[io]"` (installs `ezdxf ≥ 1.3`)

Exports to AutoCAD DXF format via [ezdxf](https://ezdxf.readthedocs.io/). Elements are placed on named DXF layers for easy import into CAD software.

### DXF layer mapping

| Element type | Layer name (single level) | Layer name (multi-level) |
|---|---|---|
| Rooms | `FP_ROOMS` | `L00_FP_ROOMS` |
| Walls | `FP_WALLS` | `L00_FP_WALLS` |
| Openings | `FP_OPENINGS` | `L00_FP_OPENINGS` |
| Columns | `FP_COLUMNS` | `L00_FP_COLUMNS` |

Layer prefixes use zero-padded level index (`L00`, `L01`, etc.).

### `building_to_dxf`

```python
building_to_dxf(building: Building) -> ezdxf.document.Drawing
```

Returns an `ezdxf` `Drawing` object. You can further modify it before saving.

```python
doc = building_to_dxf(building)
doc.saveas("my_building.dxf")
```

### `save_building_dxf`

```python
save_building_dxf(building: Building, path: str) -> None
```

Convenience function that calls `building_to_dxf` and saves the result.

```python
from archit_app.io.dxf import save_building_dxf

save_building_dxf(building, "project.dxf")
```

### `level_to_dxf`

```python
level_to_dxf(level: Level, doc=None) -> ezdxf.document.Drawing
```

Export a single level to DXF. If `doc` is provided, elements are added to it (useful for building multi-level DXF files manually).
