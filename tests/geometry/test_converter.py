"""Tests for CoordinateConverter and build_default_converter."""

import math

import numpy as np
import pytest

from archit_app.geometry.converter import (
    ConversionPathNotFoundError,
    CoordinateConverter,
    build_default_converter,
)
from archit_app.geometry.crs import (
    IMAGE,
    SCREEN,
    WGS84,
    WORLD,
    CoordinateSystem,
    LengthUnit,
    YDirection,
)
from archit_app.geometry.point import Point2D
from archit_app.geometry.transform import Transform2D

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INTERMEDIATE = CoordinateSystem("intermediate", LengthUnit.METERS, YDirection.UP)


# ---------------------------------------------------------------------------
# Registration and direct conversion
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_forward_and_inverse(self) -> None:
        conv = CoordinateConverter()
        t = Transform2D.translate(10.0, 20.0)
        conv.register(WORLD, INTERMEDIATE, t)

        pts = np.array([[0.0, 0.0], [1.0, 2.0]])

        forward = conv.convert(pts, WORLD, INTERMEDIATE)
        assert np.allclose(forward, [[10.0, 20.0], [11.0, 22.0]])

        # inverse registered automatically
        backward = conv.convert(forward, INTERMEDIATE, WORLD)
        assert np.allclose(backward, pts)

    def test_same_crs_returns_unchanged(self) -> None:
        conv = CoordinateConverter()
        pts = np.array([[3.0, 4.0]])
        result = conv.convert(pts, WORLD, WORLD)
        assert np.allclose(result, pts)

    def test_single_1d_array(self) -> None:
        conv = CoordinateConverter()
        conv.register(WORLD, INTERMEDIATE, Transform2D.translate(1.0, 2.0))
        result = conv.convert(np.array([0.0, 0.0]), WORLD, INTERMEDIATE)
        assert result.shape == (2,)
        assert np.allclose(result, [1.0, 2.0])

    def test_overwrite_registration(self) -> None:
        conv = CoordinateConverter()
        conv.register(WORLD, INTERMEDIATE, Transform2D.translate(1.0, 0.0))
        conv.register(WORLD, INTERMEDIATE, Transform2D.translate(5.0, 0.0))  # overwrite
        result = conv.convert(np.array([[0.0, 0.0]]), WORLD, INTERMEDIATE)
        assert np.allclose(result, [[5.0, 0.0]])


# ---------------------------------------------------------------------------
# BFS path finding
# ---------------------------------------------------------------------------


class TestPathFinding:
    def test_two_hop_path(self) -> None:
        conv = CoordinateConverter()
        conv.register(SCREEN, WORLD, Transform2D.scale(0.02, -0.02))  # simplified
        conv.register(WORLD, WGS84, Transform2D.translate(100.0, 200.0))

        # SCREEN → WGS84 via WORLD
        assert conv.can_convert(SCREEN, WGS84)
        pts = np.array([[0.0, 0.0]])
        result = conv.convert(pts, SCREEN, WGS84)
        # scale then translate
        expected = np.array([[0.0 * 0.02 + 100.0, 0.0 * -0.02 + 200.0]])
        assert np.allclose(result, expected)

    def test_reverse_two_hop(self) -> None:
        conv = CoordinateConverter()
        t_sw = Transform2D.translate(10.0, 5.0)
        conv.register(SCREEN, WORLD, t_sw)
        conv.register(WORLD, WGS84, Transform2D.translate(1.0, 2.0))

        # WGS84 → SCREEN should also work
        assert conv.can_convert(WGS84, SCREEN)
        pt = np.array([[11.0, 7.0]])  # WORLD = (10,5) then WGS84 = (11,7)
        result = conv.convert(pt, WGS84, SCREEN)
        assert np.allclose(result, [[0.0, 0.0]])

    def test_no_path_raises(self) -> None:
        conv = CoordinateConverter()
        conv.register(SCREEN, IMAGE, Transform2D.identity())
        # WORLD is not connected
        with pytest.raises(ConversionPathNotFoundError):
            conv.convert(np.array([[0.0, 0.0]]), SCREEN, WORLD)

    def test_can_convert_false_when_disconnected(self) -> None:
        conv = CoordinateConverter()
        assert conv.can_convert(WORLD, SCREEN) is False

    def test_can_convert_true_same_crs(self) -> None:
        conv = CoordinateConverter()
        assert conv.can_convert(WORLD, WORLD) is True


# ---------------------------------------------------------------------------
# build_default_converter
# ---------------------------------------------------------------------------


class TestBuildDefaultConverter:
    """Verify the screen ↔ world math for a known viewport."""

    # viewport: 800×600 px, 50 px/m, world origin at canvas bottom-left = (0, 0)
    H = 600.0
    PPM = 50.0
    ORIGIN = (0.0, 0.0)

    @pytest.fixture()
    def conv(self) -> CoordinateConverter:
        return build_default_converter(self.H, self.PPM, self.ORIGIN)

    def test_screen_bottom_left_maps_to_world_origin(self, conv: CoordinateConverter) -> None:
        # Screen (0, H) is the bottom-left → world (0, 0)
        result = conv.convert(np.array([[0.0, self.H]]), SCREEN, WORLD)
        assert np.allclose(result, [[0.0, 0.0]], atol=1e-9)

    def test_screen_top_left_maps_to_world_top_left(self, conv: CoordinateConverter) -> None:
        # Screen (0, 0) → world (0, H/ppm)
        result = conv.convert(np.array([[0.0, 0.0]]), SCREEN, WORLD)
        assert np.allclose(result, [[0.0, self.H / self.PPM]], atol=1e-9)

    def test_screen_center_maps_correctly(self, conv: CoordinateConverter) -> None:
        # Screen (400, 300) → world (400/50, (600-300)/50) = (8, 6)
        result = conv.convert(np.array([[400.0, 300.0]]), SCREEN, WORLD)
        assert np.allclose(result, [[8.0, 6.0]], atol=1e-9)

    def test_round_trip_screen_world(self, conv: CoordinateConverter) -> None:
        pts = np.array([[100.0, 200.0], [0.0, 600.0], [800.0, 0.0]])
        world = conv.convert(pts, SCREEN, WORLD)
        back = conv.convert(world, WORLD, SCREEN)
        assert np.allclose(back, pts, atol=1e-9)

    def test_image_equals_screen(self, conv: CoordinateConverter) -> None:
        pts = np.array([[100.0, 200.0]])
        assert np.allclose(
            conv.convert(pts, SCREEN, IMAGE),
            conv.convert(pts, SCREEN, IMAGE),
        )
        # IMAGE → WORLD should also work via BFS (SCREEN intermediate)
        assert conv.can_convert(IMAGE, WORLD)

    def test_with_nonzero_world_origin(self) -> None:
        conv = build_default_converter(
            viewport_height_px=400.0,
            pixels_per_meter=100.0,
            canvas_origin_world=(5.0, 10.0),
        )
        # Screen bottom-left (0, 400) → world (5, 10)
        result = conv.convert(np.array([[0.0, 400.0]]), SCREEN, WORLD)
        assert np.allclose(result, [[5.0, 10.0]], atol=1e-9)

    def test_registered_crs_contains_screen_image_world(self, conv: CoordinateConverter) -> None:
        names = {c.name for c in conv.registered_crs()}
        assert {"screen", "image", "world"}.issubset(names)


# ---------------------------------------------------------------------------
# Point2D.to() integration
# ---------------------------------------------------------------------------


class TestPoint2DTo:
    def test_point_to_via_converter(self) -> None:
        conv = build_default_converter(600.0, 50.0, (0.0, 0.0))
        screen_pt = Point2D(x=400.0, y=300.0, crs=SCREEN)
        world_pt = screen_pt.to(WORLD, conv)
        assert world_pt.crs == WORLD
        assert math.isclose(world_pt.x, 8.0, abs_tol=1e-9)
        assert math.isclose(world_pt.y, 6.0, abs_tol=1e-9)

    def test_round_trip_point(self) -> None:
        conv = build_default_converter(600.0, 50.0, (0.0, 0.0))
        original = Point2D(x=250.0, y=150.0, crs=SCREEN)
        world = original.to(WORLD, conv)
        back = world.to(SCREEN, conv)
        assert math.isclose(back.x, original.x, abs_tol=1e-9)
        assert math.isclose(back.y, original.y, abs_tol=1e-9)
