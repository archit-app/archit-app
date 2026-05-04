import math

import pytest

from archit_app import Staircase, StaircaseType


def test_straight_factory_returns_staircase():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=12)
    assert isinstance(s, Staircase)
    assert s.stair_type == StaircaseType.STRAIGHT


def test_default_rise_run():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=10)
    assert s.rise_height == pytest.approx(0.175)
    assert s.run_depth == pytest.approx(0.28)


def test_total_rise():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=12, rise_height=0.175)
    assert s.total_rise == pytest.approx(12 * 0.175)


def test_total_run():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=10, run_depth=0.28)
    assert s.total_run == pytest.approx(10 * 0.28)


def test_slope_angle():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=10, rise_height=0.175, run_depth=0.28)
    expected = math.atan2(0.175, 0.28)
    assert s.slope_angle == pytest.approx(expected)


def test_boundary_polygon_has_four_vertices():
    s = Staircase.straight(x=0, y=0, width=1.5, rise_count=8)
    assert len(s.boundary.exterior) == 4


def test_level_indices():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=10,
                           bottom_level_index=1, top_level_index=2)
    assert s.bottom_level_index == 1
    assert s.top_level_index == 2


def test_invalid_rise_count():
    with pytest.raises(ValueError):
        Staircase.straight(x=0, y=0, width=1.2, rise_count=0)


def test_invalid_level_indices():
    with pytest.raises(ValueError):
        Staircase.straight(x=0, y=0, width=1.2, rise_count=10,
                           bottom_level_index=2, top_level_index=1)


def test_frozen():
    s = Staircase.straight(x=0, y=0, width=1.2, rise_count=10)
    with pytest.raises(Exception):
        s.width = 2.0  # type: ignore


def test_direction_rotates_footprint():
    # With direction=π/2 (north), the long axis of the footprint should run along Y
    s_east = Staircase.straight(x=0, y=0, width=1.2, rise_count=10, run_depth=0.28, direction=0)
    s_north = Staircase.straight(x=0, y=0, width=1.2, rise_count=10, run_depth=0.28,
                                 direction=math.pi / 2)
    bb_east = s_east.bounding_box()
    bb_north = s_north.bounding_box()
    # East-facing: wide in X
    assert bb_east.width > bb_east.height - 0.01
    # North-facing: wide in Y
    assert bb_north.height > bb_north.width - 0.01
