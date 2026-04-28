"""
Building — the top-level container.

A Building holds multiple Levels and optional site context.
It supports multi-storey buildings and high-rises by holding arbitrarily
many Level objects indexed by floor number.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from archit_app.building.grid import StructuralGrid
from archit_app.building.land import Land
from archit_app.building.layer import Layer
from archit_app.building.level import Level
from archit_app.elements.base import Element
from archit_app.elements.elevator import Elevator


class BuildingMetadata(BaseModel):
    """Descriptive metadata for a building project."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    project_number: str = ""
    architect: str = ""
    client: str = ""
    date: str = ""   # ISO 8601 date string


class Building(BaseModel):
    """
    A complete building with one or more floors.

    levels are kept sorted by index at all times.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    metadata: BuildingMetadata = Field(default_factory=BuildingMetadata)
    levels: tuple[Level, ...] = ()
    land: Land | None = None
    elevators: tuple[Elevator, ...] = ()
    grid: StructuralGrid | None = None
    layers: dict[str, Layer] = Field(default_factory=dict)

    @property
    def site(self) -> Land | None:
        """Alias for ``land``.  Provided for backward compatibility."""
        return self.land

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_level(self, index: int) -> Level | None:
        return next((lv for lv in self.levels if lv.index == index), None)

    def get_element_by_id(self, element_id: UUID) -> Element | None:
        for level in self.levels:
            el = level.get_element_by_id(element_id)
            if el is not None:
                return el
        return None

    @property
    def total_floors(self) -> int:
        """Number of above-ground floors."""
        return len([lv for lv in self.levels if lv.index >= 0])

    @property
    def total_basements(self) -> int:
        return len([lv for lv in self.levels if lv.index < 0])

    @property
    def total_gross_area(self) -> float:
        """Total gross floor area across all levels in m²."""
        return sum(
            sum(r.gross_area for r in lv.rooms)
            for lv in self.levels
        )

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_level(self, level: Level) -> "Building":
        """Add or replace a level. Levels are kept sorted by index."""
        existing = [lv for lv in self.levels if lv.index != level.index]
        sorted_levels = tuple(sorted((*existing, level), key=lambda lv: lv.index))
        return self.model_copy(update={"levels": sorted_levels})

    def remove_level(self, index: int) -> "Building":
        return self.model_copy(
            update={"levels": tuple(lv for lv in self.levels if lv.index != index)}
        )

    def with_metadata(self, **kwargs) -> "Building":
        new_meta = self.metadata.model_copy(update=kwargs)
        return self.model_copy(update={"metadata": new_meta})

    def with_site(self, site: Land) -> "Building":
        """Set the site context.  Alias for ``with_land()``; kept for backward compatibility."""
        return self.model_copy(update={"land": site})

    def with_land(self, land: Land) -> "Building":
        return self.model_copy(update={"land": land})

    def add_elevator(self, elevator: Elevator) -> "Building":
        return self.model_copy(update={"elevators": (*self.elevators, elevator)})

    def remove_elevator(self, elevator_id: UUID) -> "Building":
        return self.model_copy(
            update={"elevators": tuple(e for e in self.elevators if e.id != elevator_id)}
        )

    def with_grid(self, grid: StructuralGrid) -> "Building":
        return self.model_copy(update={"grid": grid})

    def add_layer(self, layer: Layer) -> "Building":
        """Register a named layer (adds or replaces by name)."""
        new_layers = {**self.layers, layer.name: layer}
        return self.model_copy(update={"layers": new_layers})

    def with_layer(self, layer: Layer) -> "Building":
        """Alias for :meth:`add_layer`."""
        return self.add_layer(layer)

    def remove_layer(self, name: str) -> "Building":
        """Remove a layer by name.  No-op if the layer does not exist."""
        new_layers = {k: v for k, v in self.layers.items() if k != name}
        return self.model_copy(update={"layers": new_layers})

    def get_layer(self, name: str) -> Layer | None:
        """Return the :class:`Layer` with the given name, or ``None``."""
        return self.layers.get(name)

    def is_layer_visible(self, name: str) -> bool:
        """Return ``True`` if the layer is visible (or not registered at all).

        Unknown layers are treated as visible so that elements without an
        explicit layer entry are always rendered.
        """
        layer = self.layers.get(name)
        return layer is None or layer.visible

    def stats(self) -> "BuildingStats":
        """Return a structured summary of element counts and areas across all levels."""
        area_by_program: dict[str, float] = {}
        net_area = 0.0
        counts_by_level = []
        totals = dict(rooms=0, walls=0, openings=0, columns=0,
                      staircases=0, slabs=0, ramps=0, beams=0, furniture=0)

        for lv in self.levels:
            lv_net = sum(r.area for r in lv.rooms)
            net_area += lv_net
            for r in lv.rooms:
                area_by_program[r.program] = area_by_program.get(r.program, 0.0) + r.area
            lv_counts = {
                "level_index": lv.index,
                "rooms": len(lv.rooms),
                "walls": len(lv.walls),
                "openings": len(lv.openings),
                "columns": len(lv.columns),
                "staircases": len(lv.staircases),
                "slabs": len(lv.slabs),
                "ramps": len(lv.ramps),
                "beams": len(lv.beams),
                "furniture": len(lv.furniture),
                "net_area_m2": round(lv_net, 3),
            }
            counts_by_level.append(lv_counts)
            for k in totals:
                totals[k] += lv_counts.get(k, 0)

        return BuildingStats(
            total_levels=len(self.levels),
            total_rooms=totals["rooms"],
            total_walls=totals["walls"],
            total_openings=totals["openings"],
            total_columns=totals["columns"],
            total_furniture=totals["furniture"],
            gross_floor_area_m2=round(self.total_gross_area, 3),
            net_floor_area_m2=round(net_area, 3),
            area_by_program={k: round(v, 3) for k, v in area_by_program.items()},
            element_counts_by_level=counts_by_level,
        )

    def duplicate_level(
        self,
        source_index: int,
        new_index: int,
        new_elevation: float,
        *,
        name: str = "",
    ) -> "Building":
        """Return a new Building with a copy of the level at *source_index* added at *new_index*.

        Raises
        ------
        KeyError
            If no level with *source_index* exists.
        """
        source = self.get_level(source_index)
        if source is None:
            raise KeyError(f"No level with index {source_index} in this building.")
        new_level = source.duplicate(new_index, new_elevation, name=name)
        return self.add_level(new_level)

    def to_detailed_agent_context(
        self,
        level_index: int | None = None,
        include_walls: bool = True,
        include_furniture: bool = True,
        include_columns: bool = True,
    ) -> dict:
        """Return a rich, JSON-serialisable dict for use in LLM/agent prompts.

        Extends :meth:`to_agent_context` with per-room spatial data (centroid,
        bounding box), full wall geometry (start/end points, facing direction),
        and site/land context when available.

        Parameters
        ----------
        level_index:
            When provided, only the data for that floor is returned under
            ``"levels"``.  Useful for agents focused on a single storey —
            avoids returning the full building context and wasting tokens.
        include_walls:
            Set to ``False`` to omit the ``"walls"`` array from each level
            entry (e.g. for the Space Programmer who only needs room areas).
        include_furniture:
            Set to ``False`` to omit the ``"furniture"`` array from each level
            entry (e.g. for structural or compliance agents).
        include_columns:
            Set to ``False`` to omit the ``"columns"`` array from each level
            entry (e.g. for interior design agents).
        """
        base = self.to_agent_context()

        levels_to_process = (
            [lv for lv in self.levels if lv.index == level_index]
            if level_index is not None
            else list(self.levels)
        )

        detailed_levels = []
        for lv in levels_to_process:
            rooms_detail = []
            for r in lv.rooms:
                c = r.centroid
                bb = r.bounding_box()
                room_entry: dict = {
                    "id": str(r.id),
                    "name": r.name,
                    "program": r.program,
                    "area_m2": round(r.area, 2),
                    "gross_area_m2": round(r.gross_area, 2),
                    "perimeter_m": round(r.perimeter, 2),
                    "centroid": {"x": round(c.x, 3), "y": round(c.y, 3)},
                }
                if bb is not None:
                    room_entry["bounding_box"] = {
                        "min": {"x": round(bb.min_corner.x, 3), "y": round(bb.min_corner.y, 3)},
                        "max": {"x": round(bb.max_corner.x, 3), "y": round(bb.max_corner.y, 3)},
                        "width_m": round(bb.max_corner.x - bb.min_corner.x, 3),
                        "depth_m": round(bb.max_corner.y - bb.min_corner.y, 3),
                    }
                rooms_detail.append(room_entry)

            level_entry: dict = {
                "index": lv.index,
                "name": lv.name or f"Level {lv.index}",
                "elevation_m": lv.elevation,
                "floor_height_m": lv.floor_height,
                "rooms": rooms_detail,
                "staircases_count": len(lv.staircases),
                "slabs_count": len(lv.slabs),
                "ramps_count": len(lv.ramps),
                "beams_count": len(lv.beams),
            }

            if include_walls:
                walls_detail = []
                for w in lv.walls:
                    wt = getattr(w, "wall_type", None)
                    wall_entry: dict = {
                        "id": str(w.id),
                        "wall_type": wt.value if hasattr(wt, "value") else str(wt),
                        "thickness_m": getattr(w, "thickness", None),
                        "height_m": getattr(w, "height", None),
                        "length_m": round(w.length, 3),
                        "openings_count": len(getattr(w, "openings", ())),
                        "facing": w.facing_direction(),
                    }
                    sp = w.start_point
                    ep = w.end_point
                    if sp is not None:
                        wall_entry["start"] = {"x": sp[0], "y": sp[1]}
                    if ep is not None:
                        wall_entry["end"] = {"x": ep[0], "y": ep[1]}
                    bb = w.bounding_box()
                    if bb is not None:
                        wall_entry["bounding_box"] = {
                            "min": {"x": round(bb.min_corner.x, 3), "y": round(bb.min_corner.y, 3)},
                            "max": {"x": round(bb.max_corner.x, 3), "y": round(bb.max_corner.y, 3)},
                        }
                    if w.openings:
                        wall_entry["openings"] = [
                            {
                                "id": str(o.id),
                                "kind": o.kind.value if hasattr(o.kind, "value") else str(o.kind),
                                "width_m": o.width,
                                "height_m": o.height,
                                "position_along_wall": o.position_along_wall,
                            }
                            for o in w.openings
                        ]
                    walls_detail.append(wall_entry)
                level_entry["walls"] = walls_detail

            if include_columns:
                level_entry["columns"] = [
                    {
                        "id": str(c.id),
                        "shape": str(getattr(c, "shape", "")),
                        "width_m": getattr(c, "width", None),
                        "depth_m": getattr(c, "depth", None),
                    }
                    for c in lv.columns
                ]

            if include_furniture:
                level_entry["furniture"] = [
                    {
                        "id": str(f.id),
                        "category": str(getattr(f, "category", "")),
                        "name": getattr(f, "name", ""),
                    }
                    for f in lv.furniture
                ]

            bb_lv = lv.bounding_box
            if bb_lv is not None:
                level_entry["bounding_box"] = {
                    "min": {"x": round(bb_lv.min_corner.x, 3), "y": round(bb_lv.min_corner.y, 3)},
                    "max": {"x": round(bb_lv.max_corner.x, 3), "y": round(bb_lv.max_corner.y, 3)},
                    "width_m": round(bb_lv.max_corner.x - bb_lv.min_corner.x, 3),
                    "depth_m": round(bb_lv.max_corner.y - bb_lv.min_corner.y, 3),
                }
            detailed_levels.append(level_entry)

        base["levels"] = detailed_levels
        base["elevators_count"] = len(self.elevators)

        if self.land is not None:
            base["land"] = self.land.to_agent_context()

        if self.grid is not None:
            base["structural_grid"] = {
                "x_axes": [str(a.label) for a in getattr(self.grid, "x_axes", ())],
                "y_axes": [str(a.label) for a in getattr(self.grid, "y_axes", ())],
            }

        return base

    def to_agent_context(self) -> dict:
        """Return a compact, JSON-serialisable dict describing this building.

        Designed for use as context in LLM/agent prompts.  Contains high-level
        summary statistics and a per-level breakdown of element counts and areas.
        """
        stats = self.stats()
        levels_summary = []
        for lv in self.levels:
            room_programs = [r.program for r in lv.rooms if r.program]
            levels_summary.append({
                "index": lv.index,
                "name": lv.name or f"Level {lv.index}",
                "elevation_m": lv.elevation,
                "floor_height_m": lv.floor_height,
                "rooms": [
                    {
                        "name": r.name,
                        "program": r.program,
                        "area_m2": round(r.area, 2),
                    }
                    for r in lv.rooms
                ],
                "element_counts": {
                    "walls": len(lv.walls),
                    "openings": len(lv.openings),
                    "columns": len(lv.columns),
                    "staircases": len(lv.staircases),
                    "slabs": len(lv.slabs),
                    "ramps": len(lv.ramps),
                    "beams": len(lv.beams),
                    "furniture": len(lv.furniture),
                },
            })

        return {
            "building_name": self.metadata.name,
            "project_number": self.metadata.project_number,
            "architect": self.metadata.architect,
            "total_levels": stats.total_levels,
            "total_rooms": stats.total_rooms,
            "gross_floor_area_m2": stats.gross_floor_area_m2,
            "net_floor_area_m2": stats.net_floor_area_m2,
            "area_by_program_m2": stats.area_by_program,
            "elevators": len(self.elevators),
            "levels": levels_summary,
        }

    def validate(self) -> "ValidationReport":
        """Check this building for common modelling errors.

        Returns
        -------
        ValidationReport
            Contains a list of :class:`ValidationIssue` items.  An empty
            ``issues`` list means no problems were found.
        """
        issues: list[ValidationIssue] = []

        # --- Level index uniqueness ---
        seen_indices: dict[int, int] = {}
        for lv in self.levels:
            if lv.index in seen_indices:
                issues.append(ValidationIssue(
                    severity="error",
                    element_id=None,
                    message=f"Duplicate level index {lv.index}.",
                ))
            seen_indices[lv.index] = 1

        for lv in self.levels:
            # --- Rooms ---
            for room in lv.rooms:
                if room.area <= 0:
                    issues.append(ValidationIssue(
                        severity="error",
                        element_id=room.id,
                        message=f"Room '{room.name or room.id}' on level {lv.index} has zero or negative area ({room.area:.4f} m²).",
                    ))

            # --- Walls ---
            for wall in lv.walls:
                if hasattr(wall, "length") and wall.length <= 0:
                    issues.append(ValidationIssue(
                        severity="error",
                        element_id=wall.id,
                        message=f"Wall {wall.id} on level {lv.index} has zero or negative length.",
                    ))

            # --- Staircase level links ---
            for stair in lv.staircases:
                if stair.top_level_index is not None:
                    if self.get_level(stair.top_level_index) is None:
                        issues.append(ValidationIssue(
                            severity="warning",
                            element_id=stair.id,
                            message=(
                                f"Staircase {stair.id} on level {lv.index} links to "
                                f"non-existent top_level_index {stair.top_level_index}."
                            ),
                        ))
                if stair.bottom_level_index is not None:
                    if self.get_level(stair.bottom_level_index) is None:
                        issues.append(ValidationIssue(
                            severity="warning",
                            element_id=stair.id,
                            message=(
                                f"Staircase {stair.id} on level {lv.index} links to "
                                f"non-existent bottom_level_index {stair.bottom_level_index}."
                            ),
                        ))

        # --- Room overlap check (requires shapely) ---
        try:
            for lv in self.levels:
                rooms = list(lv.rooms)
                for i in range(len(rooms)):
                    for j in range(i + 1, len(rooms)):
                        ra, rb = rooms[i], rooms[j]
                        try:
                            overlap = (
                                ra.boundary._to_shapely()
                                .intersection(rb.boundary._to_shapely())
                                .area
                            )
                        except Exception:
                            continue
                        if overlap > 0.01:
                            issues.append(ValidationIssue(
                                severity="error",
                                element_id=ra.id,
                                message=(
                                    f"Rooms '{ra.name or ra.program}' and "
                                    f"'{rb.name or rb.program}' overlap by {overlap:.3f} m² "
                                    f"on level {lv.index}. "
                                    f"Remove the overlap from boundary_points."
                                ),
                            ))
        except Exception:
            pass  # shapely unavailable or unexpected geometry error

        # --- Door/opening connectivity check (requires networkx + shapely) ---
        try:
            from archit_app.analysis.topology import build_adjacency_graph
            import networkx as nx

            for lv in self.levels:
                if len(lv.rooms) < 2:
                    continue

                adj = build_adjacency_graph(lv)

                # Build a subgraph where edges only exist when an opening (door)
                # has been placed on the shared wall between two rooms.
                door_graph: "nx.Graph" = nx.Graph()
                door_graph.add_nodes_from(adj.nodes)
                for u, v, data in adj.edges(data=True):
                    if data.get("opening_ids"):
                        door_graph.add_edge(u, v)

                # 1. Every room must have at least one door to a neighbour.
                flagged: set = set()
                for room in lv.rooms:
                    if door_graph.degree(room.id) == 0:
                        flagged.add(room.id)
                        issues.append(ValidationIssue(
                            severity="error",
                            element_id=room.id,
                            message=(
                                f"Room '{room.name or room.program}' on level {lv.index} "
                                f"has no door or opening connecting it to any adjacent room. "
                                f"Call get_walls_for_room to find its walls, then "
                                f"add_opening_to_wall to add a door."
                            ),
                        ))

                # 2. All rooms must be reachable from each other through doors.
                if not nx.is_connected(door_graph):
                    components = list(nx.connected_components(door_graph))
                    largest = max(components, key=len)
                    for comp in components:
                        if comp is largest:
                            continue
                        for rid in comp:
                            if rid in flagged:
                                continue  # already reported as having no door at all
                            room = next((r for r in lv.rooms if r.id == rid), None)
                            if room:
                                issues.append(ValidationIssue(
                                    severity="error",
                                    element_id=room.id,
                                    message=(
                                        f"Room '{room.name or room.program}' on level {lv.index} "
                                        f"is in a disconnected door group — it cannot be reached "
                                        f"from the main floor plan through doors. "
                                        f"Add a door on a shared wall to connect it."
                                    ),
                                ))

        except ImportError:
            pass  # networkx not installed — connectivity check skipped
        except Exception:
            pass  # unexpected geometry or graph error — skip silently

        return ValidationReport(issues=issues)

    def __repr__(self) -> str:
        return (
            f"Building(name={self.metadata.name!r}, "
            f"levels={len(self.levels)}, "
            f"gross_area={self.total_gross_area:.1f}m²)"
        )


class BuildingStats(BaseModel):
    """Structured summary of a building's element counts and areas."""

    model_config = ConfigDict(frozen=True)

    total_levels: int
    total_rooms: int
    total_walls: int
    total_openings: int
    total_columns: int
    total_furniture: int
    gross_floor_area_m2: float
    net_floor_area_m2: float
    area_by_program: dict[str, float]
    element_counts_by_level: list[dict]


class ValidationIssue(BaseModel):
    """A single validation finding from :meth:`Building.validate`."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning", "info"]
    element_id: UUID | None
    message: str


class ValidationReport(BaseModel):
    """Result of :meth:`Building.validate`."""

    model_config = ConfigDict(frozen=True)

    issues: list[ValidationIssue] = []

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def __repr__(self) -> str:
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        return f"ValidationReport(errors={errors}, warnings={warnings})"
