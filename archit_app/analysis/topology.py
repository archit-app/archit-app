"""
Room adjacency graph.

Determines which rooms share a wall and which openings connect them,
then exposes this as a networkx.Graph.

Requires: pip install 'archit-app[analysis]'

Graph structure
---------------
Nodes — one per Room:
    G.nodes[room.id] = {
        "room":        Room,
        "centroid":    (x, y),
        "area_m2":     float,
        "program":     str,
        "level_index": int,
    }

Edges — one per adjacent room pair:
    G.edges[room_a.id, room_b.id] = {
        "shared_length_m": float,   # approximate shared wall length
        "distance_m":      float,   # centroid-to-centroid distance
        "opening_ids":     list,    # UUIDs of openings that connect the rooms
    }

Adjacency criterion
-------------------
Two rooms are considered adjacent when the distance between their boundary
polygons is ≤ *adjacency_buffer_m* (default 0.4 m, a typical wall thickness).
"""

from __future__ import annotations

import math
from uuid import UUID

import shapely.geometry

from archit_app.elements.opening import OpeningKind
from archit_app.geometry.polygon import Polygon2D

_ADJACENCY_BUFFER_M = 0.4


def _require_networkx():
    try:
        import networkx
        return networkx
    except ImportError as exc:
        raise ImportError(
            "networkx is required for topology analysis. "
            "Install it with:  pip install 'archit-app[analysis]'"
        ) from exc


def build_adjacency_graph(level, adjacency_buffer_m: float = _ADJACENCY_BUFFER_M):
    """
    Build a room adjacency graph for a single Level.

    Parameters
    ----------
    level : Level
        The floor to analyse.
    adjacency_buffer_m : float
        Maximum boundary-to-boundary distance (in meters) for two rooms to be
        considered adjacent. Should be at least as large as the wall thickness.

    Returns
    -------
    networkx.Graph
        Undirected graph. Nodes are ``Room.id`` (UUID). See module docstring
        for edge and node attribute descriptions.
    """
    nx = _require_networkx()
    G = nx.Graph()

    if not level.rooms:
        return G

    # ---- nodes ---------------------------------------------------------------
    for room in level.rooms:
        G.add_node(
            room.id,
            room=room,
            centroid=(room.centroid.x, room.centroid.y),
            area_m2=room.area,
            program=room.program,
            level_index=room.level_index,
        )

    # ---- pre-compute Shapely geometries and opening centroids ----------------
    room_shapes = {room.id: room.boundary._to_shapely() for room in level.rooms}

    opening_centroids: list[tuple[object, float, float]] = []
    for wall in level.walls:
        for opening in wall.openings:
            c = opening.geometry.centroid
            opening_centroids.append((opening, c.x, c.y))

    # ---- edges ---------------------------------------------------------------
    rooms = list(level.rooms)
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            room_a = rooms[i]
            room_b = rooms[j]
            shape_a = room_shapes[room_a.id]
            shape_b = room_shapes[room_b.id]

            # Fast rejection: bounding-box distance
            bb_dist = shape_a.distance(shape_b)
            if bb_dist > adjacency_buffer_m:
                continue

            # Reject rooms that overlap significantly (they are not "adjacent")
            overlap_area = shape_a.intersection(shape_b).area
            if overlap_area > adjacency_buffer_m ** 2:
                continue

            # Estimate shared wall length: length of room_b boundary within
            # the buffer zone of room_a boundary
            buf_a = shape_a.exterior.buffer(adjacency_buffer_m)
            shared_geom = buf_a.intersection(shape_b.exterior)
            shared_length = shared_geom.length if not shared_geom.is_empty else 0.0

            if shared_length < 0.05:
                continue

            # Centroid-to-centroid distance
            cx_a, cy_a = room_a.centroid.x, room_a.centroid.y
            cx_b, cy_b = room_b.centroid.x, room_b.centroid.y
            distance = math.sqrt((cx_b - cx_a) ** 2 + (cy_b - cy_a) ** 2)

            # Find openings that lie on the shared boundary
            connecting_ids: list[UUID] = []
            for opening, ox, oy in opening_centroids:
                pt = shapely.geometry.Point(ox, oy)
                if (shape_a.exterior.distance(pt) <= adjacency_buffer_m and
                        shape_b.exterior.distance(pt) <= adjacency_buffer_m):
                    connecting_ids.append(opening.id)

            G.add_edge(
                room_a.id,
                room_b.id,
                shared_length_m=round(shared_length, 4),
                distance_m=round(distance, 4),
                opening_ids=connecting_ids,
            )

    return G


def rooms_adjacent_to(room_id: UUID, G) -> list[UUID]:
    """Return the IDs of all rooms directly adjacent to the given room."""
    if room_id not in G:
        return []
    return list(G.neighbors(room_id))


def connected_components(G) -> list[list[UUID]]:
    """
    Return groups of rooms that are connected to each other (reachable by
    walking through openings/shared walls). Each inner list is one component.
    """
    nx = _require_networkx()
    return [list(c) for c in nx.connected_components(G)]
