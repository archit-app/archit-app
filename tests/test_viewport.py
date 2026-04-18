"""Tests for Viewport — view-state model."""

import math
import pytest
from archit_app import Viewport, WORLD
from archit_app.geometry.bbox import BoundingBox2D
from archit_app.geometry.point import Point2D


def _vp(**kwargs) -> Viewport:
    defaults = dict(canvas_width_px=800, canvas_height_px=600, pixels_per_meter=50)
    defaults.update(kwargs)
    return Viewport(**defaults)


class TestConstruction:

    def test_basic(self):
        vp = _vp()
        assert vp.canvas_width_px == 800
        assert vp.pixels_per_meter == 50

    def test_defaults(self):
        vp = _vp()
        assert vp.pan_x == pytest.approx(0.0)
        assert vp.pan_y == pytest.approx(0.0)
        assert vp.active_level_index == 0

    def test_invalid_canvas_raises(self):
        with pytest.raises(Exception):
            _vp(canvas_width_px=0)

    def test_invalid_ppm_raises(self):
        with pytest.raises(Exception):
            _vp(pixels_per_meter=-1)

    def test_frozen(self):
        vp = _vp()
        with pytest.raises(Exception):
            vp.pan_x = 5.0  # type: ignore


class TestWorldToScreen:

    def test_centre_maps_to_canvas_centre(self):
        vp = _vp(pan_x=0, pan_y=0)
        sx, sy = vp.world_to_screen(Point2D(x=0, y=0, crs=WORLD))
        assert sx == pytest.approx(400)
        assert sy == pytest.approx(300)

    def test_positive_x_moves_right(self):
        vp = _vp(pan_x=0, pan_y=0)
        sx, _ = vp.world_to_screen(Point2D(x=1, y=0, crs=WORLD))
        assert sx > 400

    def test_positive_y_moves_up_screen_moves_down(self):
        vp = _vp(pan_x=0, pan_y=0)
        _, sy = vp.world_to_screen(Point2D(x=0, y=1, crs=WORLD))
        assert sy < 300   # Y-flip: world +Y → lower screen Y

    def test_scale_applied(self):
        vp = _vp(pan_x=0, pan_y=0, pixels_per_meter=100)
        sx, _ = vp.world_to_screen(Point2D(x=1, y=0, crs=WORLD))
        assert sx == pytest.approx(400 + 100)


class TestScreenToWorld:

    def test_canvas_centre_to_world(self):
        vp = _vp(pan_x=0, pan_y=0)
        wp = vp.screen_to_world(400, 300)
        assert wp.x == pytest.approx(0.0)
        assert wp.y == pytest.approx(0.0)

    def test_round_trip(self):
        vp = _vp(pan_x=3.0, pan_y=2.0)
        pt = Point2D(x=5.5, y=1.3, crs=WORLD)
        sx, sy = vp.world_to_screen(pt)
        wp = vp.screen_to_world(sx, sy)
        assert wp.x == pytest.approx(pt.x, rel=1e-9)
        assert wp.y == pytest.approx(pt.y, rel=1e-9)

    def test_result_crs_is_world(self):
        vp = _vp()
        wp = vp.screen_to_world(400, 300)
        assert wp.crs == WORLD


class TestZoom:

    def test_zoom_in_increases_ppm(self):
        vp = _vp(pixels_per_meter=50)
        vp2 = vp.zoom(2.0)
        assert vp2.pixels_per_meter == pytest.approx(100)

    def test_zoom_out_decreases_ppm(self):
        vp = _vp(pixels_per_meter=50)
        vp2 = vp.zoom(0.5)
        assert vp2.pixels_per_meter == pytest.approx(25)

    def test_zoom_preserves_anchor_world_point(self):
        vp = _vp(pan_x=0, pan_y=0, pixels_per_meter=50)
        # Zoom centred on canvas centre — world point (0,0) should stay at canvas centre
        vp2 = vp.zoom(2.0, around_sx=400, around_sy=300)
        sx, sy = vp2.world_to_screen(Point2D(x=0, y=0, crs=WORLD))
        assert sx == pytest.approx(400, abs=1)
        assert sy == pytest.approx(300, abs=1)

    def test_original_unchanged(self):
        vp = _vp()
        _ = vp.zoom(2.0)
        assert vp.pixels_per_meter == pytest.approx(50)


class TestPan:

    def test_pan_right(self):
        vp = _vp(pan_x=0, pan_y=0)
        vp2 = vp.pan(100, 0)  # move canvas 100 px right (world moves left)
        assert vp2.pan_x < vp.pan_x

    def test_pan_down(self):
        vp = _vp(pan_x=0, pan_y=0)
        vp2 = vp.pan(0, 100)   # move canvas 100 px down (world moves up)
        assert vp2.pan_y > vp.pan_y

    def test_zero_pan_unchanged(self):
        vp = _vp(pan_x=3, pan_y=2)
        vp2 = vp.pan(0, 0)
        assert vp2.pan_x == pytest.approx(vp.pan_x)
        assert vp2.pan_y == pytest.approx(vp.pan_y)

    def test_original_unchanged(self):
        vp = _vp()
        _ = vp.pan(50, 50)
        assert vp.pan_x == pytest.approx(0)


class TestFit:

    def _bb(self, x0, y0, x1, y1):
        return BoundingBox2D(
            min_corner=Point2D(x=x0, y=y0, crs=WORLD),
            max_corner=Point2D(x=x1, y=y1, crs=WORLD),
        )

    def test_fit_centres_on_bbox(self):
        vp = _vp()
        bb = self._bb(0, 0, 10, 8)
        vp2 = vp.fit(bb)
        assert vp2.pan_x == pytest.approx(5.0)
        assert vp2.pan_y == pytest.approx(4.0)

    def test_fit_adjusts_scale(self):
        vp = _vp(pixels_per_meter=1)
        bb = self._bb(0, 0, 4, 3)
        vp2 = vp.fit(bb, padding=0.0)
        # Should scale to fill 800x600: min(800/4, 600/3) = 200
        assert vp2.pixels_per_meter == pytest.approx(200)

    def test_fit_returns_new_viewport(self):
        vp = _vp()
        vp2 = vp.fit(self._bb(0, 0, 5, 5))
        assert vp2 is not vp


class TestWithActiveLevel:

    def test_changes_level(self):
        vp = _vp()
        vp2 = vp.with_active_level(3)
        assert vp2.active_level_index == 3
        assert vp.active_level_index == 0


class TestToConverter:

    def test_returns_converter(self):
        from archit_app import CoordinateConverter
        vp = _vp()
        conv = vp.to_converter()
        assert isinstance(conv, CoordinateConverter)

    def test_converter_world_to_screen_consistent(self):
        from archit_app import SCREEN
        vp = _vp(pan_x=0, pan_y=0)
        conv = vp.to_converter()
        import numpy as np
        pts = conv.convert(np.array([[0.0, 0.0]]), WORLD, SCREEN)
        sx_conv, sy_conv = pts[0]
        sx_vp, sy_vp = vp.world_to_screen(Point2D(x=0, y=0, crs=WORLD))
        assert sx_conv == pytest.approx(sx_vp, abs=1.0)
        assert sy_conv == pytest.approx(sy_vp, abs=1.0)


class TestRepr:

    def test_repr(self):
        r = repr(_vp())
        assert "Viewport" in r
        assert "800" in r
