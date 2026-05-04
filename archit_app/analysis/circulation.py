"""
Egress and circulation analysis.

Builds on the room adjacency graph from ``topology.py`` to answer questions
about movement through a building: shortest path between rooms, egress
distance to exits, and whether egress distances comply with a limit.

Requires: pip install 'archit-app[analysis]'
"""

from __future__ import annotations

from uuid import UUID

from archit_app.analysis.topology import _require_networkx, build_adjacency_graph


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


# Programs that are treated as egress exits when exit_ids is not provided.
_EXIT_PROGRAMS = frozenset({
    "lobby", "entry", "corridor", "staircase", "exit", "escape",
    "fire_exit", "emergency_exit", "hall", "vestibule",
})


def _auto_exit_ids(level) -> set[UUID]:
    """Return IDs of rooms whose program matches a known exit program."""
    return {r.id for r in level.rooms if (r.program or "").lower() in _EXIT_PROGRAMS}


def egress_report(
    level,
    exit_ids: set[UUID] | None = None,
    max_distance_m: float = 30.0,
    adjacency_buffer_m: float = 0.4,
) -> list[dict]:
    """
    Generate an egress compliance report for every room on a level.

    For each room, reports:

    - ``room_id``            — UUID of the room
    - ``room_name``          — human-readable name
    - ``program``            — space program type
    - ``egress_distance_m``  — approximate distance to nearest exit (or None)
    - ``path``               — ordered list of room IDs on the shortest path
    - ``compliant``          — True if distance ≤ *max_distance_m*
    - ``is_exit``            — True if this room itself is an exit
    - ``issue``              — human-readable issue description (empty if compliant)
    - ``suggested_fix``      — actionable suggestion when non-compliant

    Parameters
    ----------
    level : Level
        Floor to analyse.
    exit_ids : set[UUID] | None
        Room IDs that count as exits.  When ``None`` (default), exits are
        auto-detected from room programs matching :data:`_EXIT_PROGRAMS`
        (lobby, corridor, staircase, entry, etc.).
    max_distance_m : float
        Maximum permitted egress distance in metres (default 30 m).
    adjacency_buffer_m : float
        Adjacency threshold passed to ``build_adjacency_graph()``.
    """
    if exit_ids is None:
        exit_ids = _auto_exit_ids(level)

    G = build_adjacency_graph(level, adjacency_buffer_m=adjacency_buffer_m)
    results = []

    for room in level.rooms:
        if room.id in exit_ids:
            results.append({
                "room_id": str(room.id),
                "room_name": room.name,
                "program": room.program,
                "egress_distance_m": 0.0,
                "path": [str(room.id)],
                "compliant": True,
                "is_exit": True,
                "issue": "",
                "suggested_fix": "",
            })
            continue

        path = find_egress_path(G, room.id, exit_ids)
        dist = egress_distance_m(G, room.id, exit_ids)
        compliant = (dist is not None) and (dist <= max_distance_m)

        if dist is None:
            issue = f"'{room.name or room.program}' has no accessible egress path."
            fix = "Add a door/corridor connecting this room to an exit or lobby."
        elif not compliant:
            issue = (
                f"'{room.name or room.program}' egress distance "
                f"{dist:.1f}m exceeds {max_distance_m}m limit."
            )
            fix = "Add a staircase or exit closer to this room, or shorten the egress path."
        else:
            issue = ""
            fix = ""

        results.append({
            "room_id": str(room.id),
            "room_name": room.name,
            "program": room.program,
            "egress_distance_m": round(dist, 2) if dist is not None else None,
            "path": [str(rid) for rid in path] if path else [],
            "compliant": compliant,
            "is_exit": False,
            "issue": issue,
            "suggested_fix": fix,
        })

    overall_compliant = all(r["compliant"] for r in results)
    return {
        "overall_compliant": overall_compliant,
        "max_distance_m": max_distance_m,
        "exit_count": len(exit_ids),
        "rooms": results,
        "failed_rooms": [r for r in results if not r["compliant"]],
    }
