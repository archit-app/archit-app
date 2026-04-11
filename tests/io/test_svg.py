"""Tests for SVG export."""

import pytest

from floorplan import Building, Level, WORLD, Polygon2D, Room
from floorplan.io.svg import level_to_svg, building_to_svg_pages


def test_level_to_svg_returns_string(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    assert isinstance(svg, str)
    assert svg.startswith("<?xml")


def test_svg_contains_svg_tag(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    assert "<svg" in svg
    assert "</svg>" in svg


def test_svg_contains_rooms_group(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    assert 'id="rooms"' in svg


def test_svg_contains_walls_group(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    assert 'id="walls"' in svg


def test_svg_contains_columns_group(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    assert 'id="columns"' in svg


def test_empty_level_svg():
    """Empty level should return a valid SVG with a placeholder message."""
    lv = Level(index=0, elevation=0.0, floor_height=3.0)
    svg = level_to_svg(lv)
    assert "<svg" in svg


def test_building_to_svg_pages(multi_level_building):
    pages = building_to_svg_pages(multi_level_building)
    assert len(pages) == 3
    for level_index, svg_str in pages:
        assert isinstance(level_index, int)
        assert "<svg" in svg_str


def test_svg_scale_changes_dimensions(single_level_building):
    lv = single_level_building.levels[0]
    svg_small = level_to_svg(lv, pixels_per_meter=25)
    svg_large = level_to_svg(lv, pixels_per_meter=100)
    # Larger scale → larger SVG
    import xml.etree.ElementTree as ET
    small_el = ET.fromstring(svg_small.split("\n", 1)[1])
    large_el = ET.fromstring(svg_large.split("\n", 1)[1])
    small_w = float(small_el.get("width", 0))
    large_w = float(large_el.get("width", 0))
    assert large_w > small_w


def test_svg_title_in_output(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv, title="Ground Floor Plan")
    assert "Ground Floor Plan" in svg


def test_room_label_in_svg(single_level_building):
    lv = single_level_building.levels[0]
    svg = level_to_svg(lv)
    # Room name "square_room" should appear as text
    assert "square_room" in svg


def test_wall_with_door_svg(wall_with_door):
    lv = Level(index=0, elevation=0.0, floor_height=3.0).add_wall(wall_with_door)
    svg = level_to_svg(lv)
    assert "opening" in svg
