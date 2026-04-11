# API Reference — Registry

```python
from archit_app import register, get, list_registered, get_all
from archit_app.core.registry import register, get, list_registered, get_all
```

The registry is a lightweight plugin system that lets third-party code extend `archit_app` without modifying the core library. Categories are arbitrary strings; the built-in convention is `"exporter"`, `"wall_type"`, `"renderer"`, etc.

---

## Functions

### `register(category, name)`

```python
def register(category: str, name: str)
```

Decorator that registers a class under `(category, name)`.

```python
from archit_app import register
from archit_app.elements.wall import Wall

@register("wall_type", "double_skin")
class DoubleSkinWall(Wall):
    outer_leaf_thickness: float = 0.1
    cavity_width: float = 0.05
    inner_leaf_thickness: float = 0.1
```

### `get(category, name)`

```python
def get(category: str, name: str) -> type
```

Retrieve a registered class. Raises `KeyError` if not found.

```python
from archit_app import get

WallClass = get("wall_type", "double_skin")
wall = WallClass(
    geometry=my_geom,
    thickness=0.25,
    height=3.0,
    outer_leaf_thickness=0.1,
)
```

### `list_registered(category)`

```python
def list_registered(category: str) -> list[str]
```

Return all registered names for a category.

```python
from archit_app import list_registered

print(list_registered("exporter"))
# ['svg', 'dxf', 'geojson', 'my_custom_exporter']
```

### `get_all(category)`

```python
def get_all(category: str) -> dict[str, type]
```

Return the full `{name: class}` mapping for a category.

---

## Building a plugin

A plugin is any Python package that imports `archit_app` and calls `@register`. The registration happens at import time, so loading the plugin package is sufficient.

**Example plugin (`my_fp_plugin/__init__.py`):**

```python
from archit_app import register
from archit_app.building.building import Building

@register("exporter", "revit_csv")
class RevitCsvExporter:
    """Export a Building to a Revit-compatible CSV schedule."""

    def export(self, building: Building, path: str) -> None:
        rows = []
        for level in building.levels:
            for room in level.rooms:
                rows.append({
                    "Level": level.name,
                    "Room Name": room.name,
                    "Program": room.program,
                    "Area (m2)": round(room.area, 2),
                })
        import csv
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Level", "Room Name", "Program", "Area (m2)"])
            writer.writeheader()
            writer.writerows(rows)
```

**Usage:**

```python
import my_fp_plugin  # triggers registration

from archit_app import get

ExporterClass = get("exporter", "revit_csv")
exporter = ExporterClass()
exporter.export(building, "room_schedule.csv")
```

---

## Suggested categories

| Category | Purpose |
|----------|---------|
| `"exporter"` | Custom export formats (IFC, PDF, RVT, etc.) |
| `"wall_type"` | Custom wall subclasses with additional fields |
| `"renderer"` | Custom renderers (matplotlib, OpenGL, etc.) |
| `"analyzer"` | Custom analysis algorithms |
| `"importer"` | Custom import parsers |
