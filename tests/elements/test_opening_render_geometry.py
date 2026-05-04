"""Tests for Opening.swing_arc(), Opening.glazing_lines(), and Wall.opening_at()."""

import math

import pytest

from archit_app import Opening, OpeningKind, Point2D, Wall


def _make_wall_with_door(position: float = 0.5) -> tuple[Wall, Opening]:
    wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
    door = Opening.door(x=2.05, y=-0.1, width=0.9)
    door = door.model_copy(update={"position_along_wall": position})
    wall = wall.add_opening(door)
    return wall, door


class TestSwingArc:

    def test_returns_none_for_window(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        win = Opening.window(x=2.0, y=-0.1, width=1.0)
        assert win.swing_arc(wall) is None

    def test_returns_none_for_archway(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        op = Opening.archway(x=2.0, y=-0.1, width=1.0)
        assert op.swing_arc(wall) is None

    def test_returns_polyline_for_door(self):
        wall, door = _make_wall_with_door()
        arc = door.swing_arc(wall)
        assert arc is not None
        assert len(arc) == 17  # 16 segments + 1
        for p in arc:
            assert isinstance(p, Point2D)

    def test_arc_radius_equals_door_width(self):
        # Hinge is at door width away from each arc sample.
        wall, door = _make_wall_with_door()
        arc = door.swing_arc(wall)
        # Reconstruct hinge: arc[0] is on the closed leaf at radius=width
        # from the hinge. The hinge lies along the wall centre line offset
        # by ±width/2 from the opening centre. We instead verify that the
        # set of arc points all lie on a circle by checking pairwise
        # equidistance from the centroid of (arc[0], arc[-1]) — but the
        # cleanest check is: every arc point is at distance == door.width
        # from a single common centre. Find that centre as arc[0] minus the
        # initial radius vector. Since arc[0] = hinge + width * (ux, uy)
        # for left-hinged, hinge = arc[0] - width * (ux, uy).
        # The wall here runs +x, so (ux, uy) = (1, 0).
        hinge_x = arc[0].x - door.width * 1.0
        hinge_y = arc[0].y - door.width * 0.0
        for p in arc:
            d = math.hypot(p.x - hinge_x, p.y - hinge_y)
            assert d == pytest.approx(door.width, abs=1e-6)

    def test_arc_sweeps_90_degrees(self):
        wall, door = _make_wall_with_door()
        arc = door.swing_arc(wall)
        # Reconstruct hinge as in previous test.
        hinge_x = arc[0].x - door.width
        hinge_y = arc[0].y
        v_first = (arc[0].x - hinge_x, arc[0].y - hinge_y)
        v_last = (arc[-1].x - hinge_x, arc[-1].y - hinge_y)
        len_first = math.hypot(*v_first)
        len_last = math.hypot(*v_last)
        cos_theta = (v_first[0] * v_last[0] + v_first[1] * v_last[1]) / (
            len_first * len_last
        )
        assert cos_theta == pytest.approx(0.0, abs=1e-6)

    def test_hinge_left_vs_right(self):
        wall, door = _make_wall_with_door()
        left = door.swing_arc(wall, hinge_side="left")
        right = door.swing_arc(wall, hinge_side="right")
        assert (left[0].x, left[0].y) != (right[0].x, right[0].y)

    def test_does_not_mutate(self):
        wall, door = _make_wall_with_door()
        before = (door.position_along_wall, door.kind, door.width)
        door.swing_arc(wall)
        after = (door.position_along_wall, door.kind, door.width)
        assert before == after

    def test_segments_parameter(self):
        wall, door = _make_wall_with_door()
        arc = door.swing_arc(wall, segments=8)
        assert len(arc) == 9


class TestGlazingLines:

    def test_returns_none_for_door(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        door = Opening.door(x=2.0, y=-0.1, width=0.9)
        assert door.glazing_lines(wall) is None

    def test_returns_none_for_archway(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        op = Opening.archway(x=2.0, y=-0.1, width=1.0)
        assert op.glazing_lines(wall) is None

    def test_returns_two_segments_for_window(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        win = Opening.window(x=2.0, y=-0.1, width=1.0)
        win = win.model_copy(update={"position_along_wall": 0.5})
        lines = win.glazing_lines(wall)
        assert lines is not None
        assert len(lines) == 2
        for a, b in lines:
            assert isinstance(a, Point2D)
            assert isinstance(b, Point2D)

    def test_segment_length_equals_window_width(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        win = Opening.window(x=2.0, y=-0.1, width=1.0)
        win = win.model_copy(update={"position_along_wall": 0.5})
        lines = win.glazing_lines(wall)
        for a, b in lines:
            assert math.hypot(b.x - a.x, b.y - a.y) == pytest.approx(win.width)

    def test_lines_are_parallel_and_offset(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        win = Opening.window(x=2.0, y=-0.1, width=1.0)
        win = win.model_copy(update={"position_along_wall": 0.5})
        (a1, b1), (a2, b2) = win.glazing_lines(wall)
        # Wall runs along +x, so glazing lines run along +x with differing y.
        assert a1.y != a2.y
        assert a1.x == pytest.approx(a2.x)
        assert b1.x == pytest.approx(b2.x)


class TestWallOpeningAt:

    def test_returns_none_when_no_openings(self):
        wall = Wall.straight(0, 0, 5, 0, thickness=0.2, height=3.0)
        assert wall.opening_at(0.5) is None

    def test_finds_opening_at_position(self):
        wall, door = _make_wall_with_door(position=0.4)
        found = wall.opening_at(0.4)
        assert found is not None
        assert found.id == door.id

    def test_returns_none_when_no_match_within_tol(self):
        wall, _ = _make_wall_with_door(position=0.4)
        assert wall.opening_at(0.9) is None
