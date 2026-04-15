"""Tests for analysis.topology — room adjacency graph."""

import pytest
from archit_app import (
    Level, Room, Wall, Opening, OpeningKind,
    Point2D, Polygon2D, WORLD,
)
from archit_app.analysis.topology import (
    build_adjacency_graph,
    rooms_adjacent_to,
    connected_components,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _rect_room(x, y, w, h, name="", program=""):
    boundary = Polygon2D.rectangle(x, y, w, h, crs=WORLD)
    return Room(boundary=boundary, name=name, program=program)


def _level_two_adjacent_rooms() -> Level:
    """Two rooms sharing an edge at x=4."""
    r1 = _rect_room(0, 0, 4, 4, name="A", program="living")
    r2 = _rect_room(4, 0, 4, 4, name="B", program="bedroom")
    level = Level(index=0, elevation=0.0, floor_height=3.0)
    return level.add_room(r1).add_room(r2)


def _level_separated_rooms() -> Level:
    """Two rooms with a 2 m gap between them — not adjacent."""
    r1 = _rect_room(0, 0, 4, 4, name="A")
    r2 = _rect_room(8, 0, 4, 4, name="B")
    level = Level(index=0, elevation=0.0, floor_height=3.0)
    return level.add_room(r1).add_room(r2)


def _level_three_rooms_chain() -> Level:
    """A — B — C (linear chain, B in the middle)."""
    a = _rect_room(0, 0, 4, 4, name="A", program="living")
    b = _rect_room(4, 0, 4, 4, name="B", program="hall")
    c = _rect_room(8, 0, 4, 4, name="C", program="bedroom")
    level = Level(index=0, elevation=0.0, floor_height=3.0)
    return level.add_room(a).add_room(b).add_room(c)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildAdjacencyGraph:
    def test_nodes_equal_rooms(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        assert len(G.nodes) == 2
        for room in level.rooms:
            assert room.id in G.nodes

    def test_adjacent_rooms_have_edge(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        assert G.number_of_edges() == 1

    def test_separated_rooms_no_edge(self):
        level = _level_separated_rooms()
        G = build_adjacency_graph(level)
        assert G.number_of_edges() == 0

    def test_three_room_chain_edges(self):
        level = _level_three_rooms_chain()
        G = build_adjacency_graph(level)
        assert G.number_of_edges() == 2

    def test_edge_has_shared_length(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        edge_data = list(G.edges(data=True))[0][2]
        assert "shared_length_m" in edge_data
        assert edge_data["shared_length_m"] > 0

    def test_edge_has_distance(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        edge_data = list(G.edges(data=True))[0][2]
        assert "distance_m" in edge_data
        assert edge_data["distance_m"] == pytest.approx(4.0, abs=0.5)

    def test_edge_has_opening_ids(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        edge_data = list(G.edges(data=True))[0][2]
        assert "opening_ids" in edge_data
        assert isinstance(edge_data["opening_ids"], list)

    def test_node_attributes(self):
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        room = level.rooms[0]
        data = G.nodes[room.id]
        assert data["room"] is room
        assert "area_m2" in data
        assert data["area_m2"] == pytest.approx(16.0)
        assert data["program"] == room.program

    def test_empty_level_empty_graph(self):
        level = Level(index=0, elevation=0.0, floor_height=3.0)
        G = build_adjacency_graph(level)
        assert G.number_of_nodes() == 0

    def test_opening_on_shared_wall_is_detected(self):
        """A door centred on the shared boundary (x=4) should appear in opening_ids."""
        r1 = _rect_room(0, 0, 4, 4, name="A")
        r2 = _rect_room(4, 0, 4, 4, name="B")
        # Door centred at x=4: starts at x=4-0.9/2=3.55, ends at 4.45 → centroid x=4.0
        door = Opening.door(x=3.55, y=1.5, width=0.9, wall_thickness=0.2)
        wall = Wall.straight(4, 0, 4, 4, thickness=0.2, height=3.0).add_opening(door)
        level = (
            Level(index=0, elevation=0.0, floor_height=3.0)
            .add_room(r1)
            .add_room(r2)
            .add_wall(wall)
        )
        G = build_adjacency_graph(level)
        assert G.number_of_edges() == 1
        edge_data = list(G.edges(data=True))[0][2]
        assert door.id in edge_data["opening_ids"]


class TestHelpers:
    def test_rooms_adjacent_to(self):
        level = _level_three_rooms_chain()
        G = build_adjacency_graph(level)
        rooms = {r.name: r for r in level.rooms}
        neighbors = rooms_adjacent_to(rooms["B"].id, G)
        assert len(neighbors) == 2

    def test_rooms_adjacent_to_unknown_id(self):
        import uuid
        level = _level_two_adjacent_rooms()
        G = build_adjacency_graph(level)
        assert rooms_adjacent_to(uuid.uuid4(), G) == []

    def test_connected_components_one_component(self):
        level = _level_three_rooms_chain()
        G = build_adjacency_graph(level)
        components = connected_components(G)
        assert len(components) == 1
        assert len(components[0]) == 3

    def test_connected_components_two_components(self):
        level = _level_separated_rooms()
        G = build_adjacency_graph(level)
        components = connected_components(G)
        assert len(components) == 2
