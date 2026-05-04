import math

import pytest

from archit_app import Ramp, RampType


def test_straight_factory():
    r = Ramp.straight(x=0, y=0, width=2.0, length=6.0, slope_angle=math.radians(8))
    assert isinstance(r, Ramp)
    assert r.ramp_type == RampType.STRAIGHT


def test_slope_percent():
    angle = math.radians(5)
    r = Ramp.straight(x=0, y=0, width=2.0, length=5.0, slope_angle=angle)
    assert r.slope_percent == pytest.approx(math.tan(angle) * 100)


def test_total_rise_approx():
    length = 6.0
    angle = math.radians(8)
    r = Ramp.straight(x=0, y=0, width=2.0, length=length, slope_angle=angle)
    expected = length * math.tan(angle)
    assert r.total_rise == pytest.approx(expected, rel=0.05)


def test_boundary_four_vertices():
    r = Ramp.straight(x=0, y=0, width=1.5, length=8.0, slope_angle=math.radians(6))
    assert len(r.boundary.exterior) == 4


def test_level_indices():
    r = Ramp.straight(x=0, y=0, width=2.0, length=6.0, slope_angle=math.radians(8),
                      bottom_level_index=0, top_level_index=1)
    assert r.bottom_level_index == 0
    assert r.top_level_index == 1


def test_invalid_slope_zero():
    with pytest.raises(ValueError):
        Ramp.straight(x=0, y=0, width=2, length=6, slope_angle=0.0)


def test_invalid_level_order():
    with pytest.raises(ValueError):
        Ramp.straight(x=0, y=0, width=2, length=6, slope_angle=math.radians(5),
                      bottom_level_index=1, top_level_index=0)


def test_frozen():
    r = Ramp.straight(x=0, y=0, width=2.0, length=6.0, slope_angle=math.radians(8))
    with pytest.raises(Exception):
        r.width = 3.0  # type: ignore
