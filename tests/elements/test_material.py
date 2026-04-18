"""Tests for Material and MaterialLibrary."""

import pytest
from archit_app import Material, MaterialCategory, MaterialLibrary, default_library
from archit_app.elements.material import BUILTIN_MATERIALS


class TestMaterial:

    def test_basic(self):
        m = Material(name="brick", color_hex="#C0633A", category=MaterialCategory.BRICK)
        assert m.name == "brick"
        assert m.color_hex == "#C0633A"
        assert m.category == MaterialCategory.BRICK

    def test_thermal_conductivity_optional(self):
        m = Material(name="custom", color_hex="#AAAAAA")
        assert m.thermal_conductivity_wm is None

    def test_empty_name_raises(self):
        with pytest.raises(Exception):
            Material(name="", color_hex="#AAAAAA")

    def test_invalid_color_hex_raises(self):
        with pytest.raises(Exception):
            Material(name="x", color_hex="AAAAAA")   # missing #

    def test_negative_conductivity_raises(self):
        with pytest.raises(Exception):
            Material(name="x", color_hex="#AAAAAA", thermal_conductivity_wm=-1.0)

    def test_frozen(self):
        m = Material(name="x", color_hex="#AAAAAA")
        with pytest.raises(Exception):
            m.name = "y"  # type: ignore

    def test_repr(self):
        m = Material(name="concrete", color_hex="#B0B0B0", category=MaterialCategory.CONCRETE)
        assert "Material" in repr(m)
        assert "concrete" in repr(m)

    def test_short_hex_allowed(self):
        m = Material(name="x", color_hex="#ABC")   # 4-char hex
        assert m.color_hex == "#ABC"


class TestBuiltins:

    def test_twelve_builtins(self):
        assert len(BUILTIN_MATERIALS) == 12

    def test_concrete_present(self):
        names = [m.name for m in BUILTIN_MATERIALS]
        assert "concrete" in names

    def test_all_have_valid_color(self):
        for m in BUILTIN_MATERIALS:
            assert m.color_hex.startswith("#")

    def test_concrete_conductivity(self):
        concrete = next(m for m in BUILTIN_MATERIALS if m.name == "concrete")
        assert concrete.thermal_conductivity_wm == pytest.approx(1.7)


class TestMaterialLibrary:

    def test_default_library_preloaded(self):
        assert len(default_library) == 12

    def test_get_existing(self):
        lib = MaterialLibrary()
        m = lib.get("concrete")
        assert m.name == "concrete"

    def test_get_missing_raises(self):
        lib = MaterialLibrary()
        with pytest.raises(KeyError):
            lib.get("unobtanium")

    def test_get_or_none_missing(self):
        lib = MaterialLibrary()
        assert lib.get_or_none("unobtanium") is None

    def test_register_custom(self):
        lib = MaterialLibrary()
        m = Material(name="rammed_earth", color_hex="#C4A882")
        lib.register(m)
        assert lib.get("rammed_earth") is m

    def test_register_replaces(self):
        lib = MaterialLibrary()
        m1 = Material(name="concrete", color_hex="#111111")
        lib.register(m1)
        assert lib.get("concrete").color_hex == "#111111"

    def test_unregister(self):
        lib = MaterialLibrary()
        lib.unregister("concrete")
        assert "concrete" not in lib

    def test_unregister_missing_raises(self):
        lib = MaterialLibrary()
        with pytest.raises(KeyError):
            lib.unregister("unobtanium")

    def test_all_sorted(self):
        lib = MaterialLibrary()
        names = [m.name for m in lib.all()]
        assert names == sorted(names)

    def test_by_category(self):
        lib = MaterialLibrary()
        concrete_mats = lib.by_category(MaterialCategory.CONCRETE)
        assert all(m.category == MaterialCategory.CONCRETE for m in concrete_mats)
        assert any(m.name == "concrete" for m in concrete_mats)

    def test_names(self):
        lib = MaterialLibrary()
        names = lib.names()
        assert isinstance(names, list)
        assert "concrete" in names

    def test_contains(self):
        lib = MaterialLibrary()
        assert "concrete" in lib
        assert "unobtanium" not in lib

    def test_len(self):
        lib = MaterialLibrary()
        assert len(lib) == 12

    def test_iter(self):
        lib = MaterialLibrary()
        materials = list(lib)
        assert len(materials) == 12

    def test_empty_library(self):
        lib = MaterialLibrary(include_builtins=False)
        assert len(lib) == 0

    def test_repr(self):
        lib = MaterialLibrary()
        assert "MaterialLibrary" in repr(lib)
        assert "12" in repr(lib)


# ---------------------------------------------------------------------------
# Material colour applied to SVG rendering
# ---------------------------------------------------------------------------

class TestMaterialInSVG:
    """Verify that material_library parameter influences SVG fill colours."""

    def test_wall_material_color_in_svg(self):
        from archit_app import WORLD, Level, Room, Polygon2D, Wall, MaterialLibrary
        from archit_app.io.svg import level_to_svg

        lib = MaterialLibrary(include_builtins=False)
        lib.register(Material(name="lego_blue", color_hex="#0055BF",
                               category=MaterialCategory.OTHER))

        wall = Wall.straight(0, 0, 4, 0, thickness=0.2, height=3.0).model_copy(
            update={"material": "lego_blue"}
        )
        room = Room(
            boundary=Polygon2D.rectangle(0, 0, 4, 3, crs=WORLD),
            name="Hall", program="living",
        )
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room).add_wall(wall)
        svg = level_to_svg(level, material_library=lib)
        # The material's colour should appear in the SVG fill
        assert "#0055BF" in svg

    def test_no_material_uses_default_palette_color(self):
        from archit_app import WORLD, Level, Room, Polygon2D, Wall, MaterialLibrary
        from archit_app.io.svg import level_to_svg

        lib = MaterialLibrary()
        wall = Wall.straight(0, 0, 4, 0, thickness=0.2, height=3.0)
        room = Room(
            boundary=Polygon2D.rectangle(0, 0, 4, 3, crs=WORLD),
            name="Hall", program="living",
        )
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(room).add_wall(wall)
        svg = level_to_svg(level, material_library=lib)
        # Default wall fill from palette
        from archit_app.io.svg import PALETTE
        assert PALETTE["wall_fill"] in svg
