# API Reference — I/O

`archit_app` supports seven interchange formats. All exporters work at both `Level` and `Building` level.

---

## JSON (canonical format)

```python
from archit_app.io.json_schema import (
    building_to_json, building_from_json,
    building_to_dict, building_from_dict,
    save_building, load_building,
)
```

The canonical format is fully round-trippable, versioned (`"_archit_app_version": "0.2.0"`), and human-readable.

### Functions

| Function | Description |
|----------|-------------|
| `building_to_json(building, indent=2) → str` | Serialize to JSON string |
| `building_from_json(s) → Building` | Deserialize from JSON string |
| `building_to_dict(building) → dict` | Serialize to plain dict |
| `building_from_dict(data) → Building` | Reconstruct from dict |
| `save_building(building, path, indent=2) → None` | Write to `.archit_app.json` file |
| `load_building(path) → Building` | Read from file |

The deserializer reads both the current `"land"` key and the legacy `"site"` key for backward compatibility.

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

Renders 2D floorplan diagrams. World Y-up is automatically flipped to SVG Y-down.

**Currently rendered:** rooms (filled, label, area), walls, openings (door swing arc, window sill line), columns, scale bar, title.

**Not yet rendered:** furniture, annotations, dimension lines, section marks, beams, ramps. These are planned (P10 item 36).

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

### `save_level_svg` / `save_building_svgs`

```python
save_level_svg(level, path, **kwargs) -> None
save_building_svgs(building, directory, **kwargs) -> list[str]
```

### Color palette keys

`room_fill`, `room_stroke`, `wall_fill`, `wall_stroke`, `column_fill`, `column_stroke`, `door_fill`, `door_stroke`, `window_fill`, `window_stroke`, `background`, `room_label`, `annotation`

---

## PNG (raster export)

```python
# Requires: pip install "archit-app[image]"
from archit_app.io.image import (
    level_to_png_bytes,
    save_level_png,
    save_building_pngs,
)
```

Raster export via Pillow. Uses 2× supersampling for clean anti-aliased edges.

### `level_to_png_bytes`

```python
level_to_png_bytes(
    level: Level,
    pixels_per_meter: float = 100.0,
    dpi: int = 150,
    margin: int = 40,
    palette: dict | None = None,
) -> bytes
```

### `save_level_png`

```python
save_level_png(level, path, pixels_per_meter=100.0, dpi=150, **kwargs) -> None
```

### `save_building_pngs`

```python
save_building_pngs(building, directory, pixels_per_meter=100.0, dpi=150, **kwargs) -> list[str]
```

Writes one PNG per level into `directory`. Returns the list of file paths.

**Example:**

```python
from archit_app.io.image import save_level_png, save_building_pngs

save_level_png(ground, "ground_floor.png", pixels_per_meter=100, dpi=150)
save_building_pngs(building, "output/pngs/", pixels_per_meter=100)
```

---

## PDF

```python
# Requires: pip install "archit-app[pdf]"
from archit_app.io.pdf import (
    level_to_pdf_bytes,
    save_level_pdf,
    building_to_pdf_bytes,
    save_building_pdf,
)
```

Print-ready PDF export via reportlab. Auto-selects landscape/portrait based on drawing aspect ratio.

### `save_level_pdf`

```python
save_level_pdf(
    level: Level,
    path: str,
    paper_size: str = "A3",
    landscape: bool | None = None,   # None = auto-detect
    **kwargs,
) -> None
```

### `save_building_pdf`

```python
save_building_pdf(
    building: Building,
    path: str,
    paper_size: str = "A3",
    **kwargs,
) -> None
```

Multi-page PDF — one page per level.

**Supported paper sizes:** `"A1"`, `"A2"`, `"A3"` (default), `"A4"`, `"letter"`

**Example:**

```python
from archit_app.io.pdf import save_building_pdf

save_building_pdf(building, "project.pdf", paper_size="A2")
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

Exports as a GeoJSON `FeatureCollection`. Coordinates are in world space (meters). Each feature carries its element type, UUID, tags, and layer as GeoJSON properties. Multi-level exports include a `level_index` property per feature.

> **Note:** GeoJSON import is not yet implemented (planned P10 item 37).

**Example:**

```python
import json
from archit_app.io.geojson import level_to_geojson

fc = level_to_geojson(ground)
print(json.dumps(fc, indent=2))
```

---

## DXF

```python
# Requires: pip install "archit-app[io]"  (installs ezdxf ≥ 1.3)
from archit_app.io.dxf import (
    building_to_dxf, level_to_dxf,
    save_building_dxf, save_level_dxf,
    building_from_dxf, level_from_dxf,
)
```

Full read/write round-trip via [ezdxf](https://ezdxf.readthedocs.io/).

### Layer naming convention

| Element type | Single level | Multi-level |
|---|---|---|
| Rooms | `FP_ROOMS` | `L00_FP_ROOMS` |
| Walls | `FP_WALLS` | `L00_FP_WALLS` |
| Openings | `FP_OPENINGS` | `L00_FP_OPENINGS` |
| Columns | `FP_COLUMNS` | `L00_FP_COLUMNS` |

### Write

```python
save_building_dxf(building, "project.dxf") -> None
save_level_dxf(level, "floor.dxf") -> None
building_to_dxf(building) -> ezdxf.document.Drawing   # for further manipulation
```

### Read

```python
level_from_dxf(
    path: str,
    *,
    layer_mapping: dict[str, str] | None = None,  # e.g. {"A-WALL": "walls"}
    level_index: int = 0,
    wall_height: float = 3.0,
    wall_thickness: float = 0.2,
) -> Level
```

Auto-detects `FP_*` layer names. Pass `layer_mapping` for non-archit-app DXF files.

```python
building_from_dxf(
    path: str,
    **kwargs,
) -> Building
```

Auto-detects `L{dd}_FP_*` level prefixes. Single-level files without prefixes produce a one-level building.

**Example:**

```python
from archit_app.io.dxf import save_building_dxf, building_from_dxf

save_building_dxf(building, "project.dxf")
restored = building_from_dxf("project.dxf")

# Import from generic CAD file
level = level_from_dxf("autocad.dxf",
                        layer_mapping={"A-WALL": "walls", "A-FLOR-PATT": "rooms"})
```

---

## IFC 4.x

```python
# Requires: pip install "archit-app[ifc]"  (installs ifcopenshell)
from archit_app.io.ifc import (
    building_to_ifc,
    save_building_ifc,
)
```

Write-only IFC 4.x export. The file can be opened in Revit, ArchiCAD, FreeCAD, and any IFC 4-compliant viewer.

**Exported types:** `IfcWall`, `IfcSpace` (rooms), `IfcDoor`, `IfcWindow`, `IfcColumn`, `IfcSlab`, `IfcStair` — all under `IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey`.

Stable GUIDs are derived from element UUIDs — re-exporting always yields the same IFC GlobalIds.

### `building_to_ifc`

```python
building_to_ifc(building: Building) -> ifcopenshell.file
```

Returns an `ifcopenshell.file` object for further manipulation before saving.

### `save_building_ifc`

```python
save_building_ifc(building: Building, path: str) -> None
```

**Example:**

```python
from archit_app.io.ifc import save_building_ifc, building_to_ifc

save_building_ifc(building, "project.ifc")

# Or inspect before saving
model = building_to_ifc(building)
print(len(model.by_type("IfcWall")))
model.write("project.ifc")
```
