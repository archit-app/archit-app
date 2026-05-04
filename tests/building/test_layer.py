"""Tests for Layer model and Building layer management + SVG visibility filtering."""

from __future__ import annotations

import pytest

from archit_app import (
    WORLD,
    Building,
    Furniture,
    Layer,
    Level,
    Polygon2D,
    Room,
    Wall,
)
from archit_app.io.svg import level_to_svg

# ---------------------------------------------------------------------------
# Layer model
# ---------------------------------------------------------------------------

class TestLayerModel:

    def test_default_visible(self):
        lyr = Layer(name="Structure")
        assert lyr.visible is True

    def test_default_not_locked(self):
        lyr = Layer(name="Structure")
        assert lyr.locked is False

    def test_custom_color(self):
        lyr = Layer(name="Structure", color_hex="#FF0000")
        assert lyr.color_hex == "#FF0000"

    def test_color_normalised_to_uppercase(self):
        lyr = Layer(name="A", color_hex="#ff0000")
        assert lyr.color_hex == "#FF0000"

    def test_invalid_color_raises(self):
        with pytest.raises(Exception):
            Layer(name="A", color_hex="red")  # not a hex string

    def test_hide(self):
        lyr = Layer(name="A").hide()
        assert lyr.visible is False

    def test_show(self):
        lyr = Layer(name="A", visible=False).show()
        assert lyr.visible is True

    def test_lock(self):
        lyr = Layer(name="A").lock()
        assert lyr.locked is True

    def test_unlock(self):
        lyr = Layer(name="A", locked=True).unlock()
        assert lyr.locked is False

    def test_with_color(self):
        lyr = Layer(name="A").with_color("#00FF00")
        assert lyr.color_hex == "#00FF00"

    def test_immutable(self):
        lyr = Layer(name="A")
        with pytest.raises(Exception):
            lyr.visible = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Building layer registry
# ---------------------------------------------------------------------------

class TestBuildingLayers:

    def test_add_layer(self):
        b = Building().add_layer(Layer(name="Structure"))
        assert "Structure" in b.layers

    def test_with_layer_alias(self):
        b = Building().with_layer(Layer(name="Structure"))
        assert "Structure" in b.layers

    def test_add_layer_replaces_existing(self):
        b = Building().add_layer(Layer(name="Structure", color_hex="#FF0000"))
        b2 = b.add_layer(Layer(name="Structure", color_hex="#00FF00"))
        assert b2.layers["Structure"].color_hex == "#00FF00"

    def test_remove_layer(self):
        b = Building().add_layer(Layer(name="Structure"))
        b2 = b.remove_layer("Structure")
        assert "Structure" not in b2.layers

    def test_remove_nonexistent_is_noop(self):
        b = Building()
        b2 = b.remove_layer("Ghost")
        assert b2.layers == {}

    def test_get_layer(self):
        lyr = Layer(name="Structure", color_hex="#FF0000")
        b = Building().add_layer(lyr)
        assert b.get_layer("Structure") is lyr

    def test_get_layer_returns_none_when_missing(self):
        assert Building().get_layer("Ghost") is None

    def test_is_layer_visible_unregistered(self):
        assert Building().is_layer_visible("anything") is True

    def test_is_layer_visible_registered_visible(self):
        b = Building().add_layer(Layer(name="A", visible=True))
        assert b.is_layer_visible("A") is True

    def test_is_layer_visible_registered_hidden(self):
        b = Building().add_layer(Layer(name="A", visible=False))
        assert b.is_layer_visible("A") is False


# ---------------------------------------------------------------------------
# SVG visibility filtering via visible_layers parameter
# ---------------------------------------------------------------------------

def _make_level_with_furniture_on_layer(layer_name: str) -> Level:
    room = Room(
        boundary=Polygon2D.rectangle(0, 0, 6, 5, crs=WORLD),
        name="Hall", program="living",
    )
    wall = Wall.straight(0, 0, 6, 0, thickness=0.2, height=3.0)
    sofa = Furniture.sofa(x=1, y=1).model_copy(update={"layer": layer_name})
    return (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(room)
        .add_wall(wall)
        .add_furniture(sofa)
    )


class TestSVGLayerVisibility:

    def test_furniture_hidden_when_layer_not_in_visible_set(self):
        level = _make_level_with_furniture_on_layer("Furniture")
        svg = level_to_svg(level, visible_layers={"Structure"})
        # furniture group should be absent
        assert 'id="furniture"' not in svg

    def test_furniture_shown_when_layer_in_visible_set(self):
        level = _make_level_with_furniture_on_layer("Furniture")
        svg = level_to_svg(level, visible_layers={"Furniture"})
        assert 'id="furniture"' in svg

    def test_none_visible_layers_shows_all(self):
        level = _make_level_with_furniture_on_layer("Furniture")
        svg = level_to_svg(level, visible_layers=None)
        assert 'id="furniture"' in svg

    def test_empty_visible_layers_hides_everything(self):
        level = _make_level_with_furniture_on_layer("Furniture")
        svg = level_to_svg(level, visible_layers=set())
        assert 'id="furniture"' not in svg
