"""
Egress and circulation analysis.

Builds on the room adjacency graph from ``topology.py`` to answer questions
about movement through a building: shortest path between rooms, egress
distance to exits, and whether egress distances comply with a limit.

Requires: pip install 'archit-app[analysis]'
"""

from __future__ import annotations

from uuid import UUID

from archit_app.analysis.topology import build_adjacency_graph, _require_networkx


def find_egress_path(
    G,
    start_id: UUID,
    exit_ids: set[UUID],
) -> list[UUID] | None:
    """
    Find the shortest path (fewest room transitions) from *start_id* to the
    nearest room in *exit_ids*.

    Parameters
    ----------
    G : networkx.Graph
        Room adjacency graph produced by ``build_adjacency_graph()``.
    start_id : UUID
        ID of the room to start from.
    exit_ids : set[UUID]
        IDs of rooms that count as exits (e.g. stairwells, lobbies,
        exterior doors).

    Returns
    -------
    list[UUID] | None
        Ordered list of room IDs from *start_id* to the nearest exit
        (inclusive of both), or None if no path exists.
    """
    nx = _require_networkx()

    if start_id not in G:
        return None
    reachable_exits = [eid for eid in exit_ids if eid in G]
    if not reachable_exits:
        return None

    best_path: list[UUID] | None = None
    for exit_id in reachable_exits:
        try:
            path = nx.shortest_path(G, start_id, exit_id)
            if best_path is None or len(path) < len(best_path):
                best_path = path
        except nx.NetworkXNoPath:
            continue

    return best_path


def egress_distance_m(
    G,
    start_id: UUID,
    exit_ids: set[UUID],
) -> float | None:
    """
    Approximate egress distance in meters from *start_id* to the nearest exit.

    Distance is the sum of centroid-to-centroid distances along the shortest
    path (by hop count). Returns None if no path exists.
    """
    nx = _require_networkx()

    if start_id not in G:
        return None
    reachable_exits = [eid for eid in exit_ids if eid in G]
    if not reachable_exits:
        return None

    best_dist: float | None = None
    for exit_id in reachable_exits:
        try:
            path = nx.shortest_path(G, start_id, exit_id, weight="distance_m")
            dist = sum(
                G[path[k]][path[k + 1]]["distance_m"]
                for k in range(len(path) - 1)
            )
            if best_dist is None or dist < best_dist:
                best_dist = dist
        except nx.NetworkXNoPath:
            continue

    return best_dist


def egress_report(
    level,
    exit_ids: set[UUID],
    max_distance_m: float = 30.0,
    adjacency_buffer_m: float = 0.4,
) -> list[dict]:
    """
    Generate an egress compliance report for every room on a level.

    For each room, reports:
    - ``room_id``
    - ``room_name``
    - ``program``
    - ``egress_distance_m``  — approximate distance to nearest exit (or None)
    - ``path``               — list of room IDs on the shortest path
    - ``compliant``          — True if distance ≤ *max_distance_m*

    Parameters
    ----------
    level : Level
        Floor to analyse.
    exit_ids : set[UUID]
        Room IDs that are exits. Rooms not on this level are ignored.
    max_distance_m : float
        Maximum permitted egress distance (default 30 m).
    adjacency_buffer_m : float
        Adjacency threshold passed to ``build_adjacency_graph()``.
    """
    G = build_adjacency_graph(level, adjacency_buffer_m=adjacency_buffer_m)
    results = []

    for room in level.rooms:
        if room.id in exit_ids:
            results.append({
                "room_id": room.id,
                "room_name": room.name,
                "program": room.program,
                "egress_distance_m": 0.0,
                "path": [room.id],
                "compliant": True,
                "is_exit": True,
            })
            continue

        path = find_egress_path(G, room.id, exit_ids)
        dist = egress_distance_m(G, room.id, exit_ids)
        compliant = (dist is not None) and (dist <= max_distance_m)

        results.append({
            "room_id": room.id,
            "room_name": room.name,
            "program": room.program,
            "egress_distance_m": round(dist, 2) if dist is not None else None,
            "path": path,
            "compliant": compliant,
            "is_exit": False,
        })

    return results
