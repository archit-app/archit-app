"""Tests for analysis.circulation — egress path finding."""

from archit_app import WORLD, Level, Polygon2D, Room
from archit_app.analysis.circulation import (
    egress_distance_m,
    egress_report,
    find_egress_path,
)
from archit_app.analysis.topology import build_adjacency_graph


def _rect_room(x, y, w, h, name="", program=""):
    boundary = Polygon2D.rectangle(x, y, w, h, crs=WORLD)
    return Room(boundary=boundary, name=name, program=program)


def _chain_level():
    """A — B — C chain; A and C are not directly adjacent."""
    a = _rect_room(0, 0, 4, 4, name="A", program="room")
    b = _rect_room(4, 0, 4, 4, name="B", program="hall")
    c = _rect_room(8, 0, 4, 4, name="C", program="exit")
    return (
        Level(index=0, elevation=0.0, floor_height=3.0)
        .add_room(a).add_room(b).add_room(c),
        a, b, c,
    )


class TestFindEgressPath:
    def test_direct_neighbor(self):
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        path = find_egress_path(G, b.id, {c.id})
        assert path is not None
        assert path[0] == b.id
        assert path[-1] == c.id

    def test_two_hops(self):
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        path = find_egress_path(G, a.id, {c.id})
        assert path is not None
        assert path[0] == a.id
        assert path[-1] == c.id
        assert b.id in path

    def test_no_path_disconnected(self):
        a = _rect_room(0, 0, 4, 4, name="A")
        b = _rect_room(20, 0, 4, 4, name="B")  # far away
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(a).add_room(b)
        G = build_adjacency_graph(level)
        assert find_egress_path(G, a.id, {b.id}) is None

    def test_start_is_exit(self):
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        path = find_egress_path(G, c.id, {c.id})
        assert path is not None
        assert path == [c.id]

    def test_nearest_of_two_exits(self):
        """B should reach C (1 hop) rather than going further."""
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        path = find_egress_path(G, b.id, {a.id, c.id})
        # Both are 1 hop away; either is valid
        assert path is not None
        assert len(path) == 2

    def test_unknown_start_returns_none(self):
        import uuid
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        assert find_egress_path(G, uuid.uuid4(), {c.id}) is None


class TestEgressDistanceM:
    def test_distance_is_positive(self):
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        dist = egress_distance_m(G, a.id, {c.id})
        assert dist is not None
        assert dist > 0

    def test_closer_exit_gives_shorter_distance(self):
        level, a, b, c = _chain_level()
        G = build_adjacency_graph(level)
        dist_to_b = egress_distance_m(G, a.id, {b.id})
        dist_to_c = egress_distance_m(G, a.id, {c.id})
        assert dist_to_b < dist_to_c

    def test_no_path_returns_none(self):
        a = _rect_room(0, 0, 4, 4)
        b = _rect_room(20, 0, 4, 4)
        level = Level(index=0, elevation=0.0, floor_height=3.0).add_room(a).add_room(b)
        G = build_adjacency_graph(level)
        assert egress_distance_m(G, a.id, {b.id}) is None


class TestEgressReport:
    def test_report_has_entry_per_room(self):
        level, a, b, c = _chain_level()
        report = egress_report(level, exit_ids={c.id})
        assert len(report) == 3

    def test_exit_room_is_compliant(self):
        level, a, b, c = _chain_level()
        report = egress_report(level, exit_ids={c.id})
        exit_entry = next(r for r in report if r["room_id"] == c.id)
        assert exit_entry["compliant"] is True
        assert exit_entry["egress_distance_m"] == 0.0

    def test_compliant_within_limit(self):
        level, a, b, c = _chain_level()
        report = egress_report(level, exit_ids={c.id}, max_distance_m=100.0)
        for entry in report:
            assert entry["compliant"] is True

    def test_non_compliant_beyond_limit(self):
        level, a, b, c = _chain_level()
        report = egress_report(level, exit_ids={c.id}, max_distance_m=0.01)
        non_exits = [r for r in report if not r["is_exit"]]
        for entry in non_exits:
            assert entry["compliant"] is False
