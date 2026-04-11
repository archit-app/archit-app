# Contributing

Contributions are welcome — bug reports, documentation improvements, new features, and tests.

---

## Development setup

```bash
git clone https://github.com/your-org/floorplan.git
cd floorplan
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev,io,image,analysis]"
```

This installs the package in editable mode with all development and optional dependencies.

---

## Running tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=floorplan --cov-report=term-missing
```

The test suite is organized to mirror the package structure:

```
tests/
├── geometry/     test_crs, test_point, test_polygon, test_transform
├── elements/     test_wall, test_room
├── building/     test_building
└── io/           test_json_schema, test_svg, test_geojson
```

---

## Code style

```bash
ruff check floorplan tests
ruff format floorplan tests
```

Configuration is in `pyproject.toml`. Line length is 100. The linting rules are `E`, `F`, and `I` (errors, pyflakes, isort).

---

## Design principles

Before contributing code, read [Core Concepts](concepts.md). The key rules:

1. **All models are immutable.** Never use `model_copy` with a side effect; always return the new object. Never use `object.__setattr__` to bypass immutability.

2. **CRS tagging is mandatory.** Every `Point2D` and `Vector2D` must carry a `crs`. Do not create bare geometry without a CRS.

3. **Internal unit is meters.** Store all lengths and areas in meters. Unit conversion belongs at import/export boundaries only.

4. **Geometry-agnostic core.** Do not hard-code Manhattan or right-angle assumptions in `geometry/` or `elements/`. Tests should cover non-rectilinear shapes.

5. **Shapely for ops, not storage.** Use Shapely for polygon computations (`contains`, `intersection`, etc.) but never store a `shapely.Polygon` in a Pydantic field.

6. **No silent wrong-answer bugs.** If a function is called with invalid inputs (mismatched CRS, negative thickness), raise a descriptive exception immediately. Do not return silently incorrect results.

---

## Adding a new element type

1. Create `floorplan/elements/my_element.py` inheriting from `Element`.
2. Add factories and computed properties following the pattern in `wall.py` and `room.py`.
3. Export from `floorplan/elements/__init__.py` and `floorplan/__init__.py`.
4. Add serialization to `floorplan/io/json_schema.py` (`_ser_*` / `_des_*` functions and integration into `_ser_level` / `_des_level`).
5. Add rendering to `floorplan/io/svg.py`.
6. Add GeoJSON export to `floorplan/io/geojson.py`.
7. Write tests in `tests/elements/test_my_element.py` and `tests/io/` covering the round-trip.

---

## Adding an I/O format

1. Create `floorplan/io/my_format.py`.
2. Document the optional dependency in `pyproject.toml` under `[project.optional-dependencies]`.
3. Guard the import with a clear `ImportError` if the dependency is missing:
   ```python
   try:
       import my_lib
   except ImportError as e:
       raise ImportError(
           "my_format export requires: pip install 'floorplan[my_extra]'"
       ) from e
   ```
4. Write tests that skip gracefully if the optional dependency is not installed:
   ```python
   pytest.importorskip("my_lib")
   ```

---

## Test fixtures

`tests/conftest.py` contains shared fixtures: a simple rectangular level, a multi-room level, and a two-level building. Use these as starting points for new tests rather than constructing everything inline.

---

## Pull request checklist

- [ ] New code is covered by tests
- [ ] `pytest` passes with no failures
- [ ] `ruff check` reports no errors
- [ ] Public APIs are documented in `docs/api/`
- [ ] Breaking changes are noted in the PR description
