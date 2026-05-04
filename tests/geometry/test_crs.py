import pytest

from archit_app import (
    IMAGE,
    SCREEN,
    WGS84,
    WORLD,
    CoordinateSystem,
    CRSMismatchError,
    LengthUnit,
    YDirection,
)


def test_singletons_exist():
    assert WORLD.name == "world"
    assert SCREEN.name == "screen"
    assert IMAGE.name == "image"
    assert WGS84.name == "geographic"


def test_world_is_y_up_meters():
    assert WORLD.unit == LengthUnit.METERS
    assert WORLD.y_direction == YDirection.UP


def test_screen_is_y_down_pixels():
    assert SCREEN.unit == LengthUnit.PIXELS
    assert SCREEN.y_direction == YDirection.DOWN


def test_crs_equality_by_name_unit_direction():
    a = CoordinateSystem("world", LengthUnit.METERS, YDirection.UP, origin=(1.0, 2.0))
    b = CoordinateSystem("world", LengthUnit.METERS, YDirection.UP, origin=(99.0, 99.0))
    # origin is mutable config, not identity
    assert a == b
    assert hash(a) == hash(b)


def test_crs_inequality():
    assert WORLD != SCREEN
    assert WORLD != WGS84


def test_crs_mismatch_error_message():
    err = CRSMismatchError(WORLD, SCREEN, "add")
    assert "world" in str(err)
    assert "screen" in str(err)
    assert "add" in str(err)


def test_length_unit_to_meters():
    assert LengthUnit.METERS.to_meters(1.0) == pytest.approx(1.0)
    assert LengthUnit.FEET.to_meters(1.0) == pytest.approx(0.3048)
    assert LengthUnit.INCHES.to_meters(12.0) == pytest.approx(0.3048, rel=1e-6)
    assert LengthUnit.MILLIMETERS.to_meters(1000.0) == pytest.approx(1.0)


def test_pixels_to_meters_requires_ppm():
    with pytest.raises(ValueError, match="pixels_per_meter"):
        LengthUnit.PIXELS.to_meters(100.0)


def test_pixels_to_meters_with_ppm():
    result = LengthUnit.PIXELS.to_meters(100.0, pixels_per_meter=50.0)
    assert result == pytest.approx(2.0)


def test_length_unit_round_trip():
    for unit in [LengthUnit.METERS, LengthUnit.FEET, LengthUnit.INCHES, LengthUnit.MILLIMETERS]:
        val = 5.0
        assert unit.to_meters(unit.from_meters(val)) == pytest.approx(val, rel=1e-9)
