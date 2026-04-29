"""Floorplan snapshot — a token-budgeted, validated view of the current building."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from archit_app.protocol._base import ProtocolBase
from archit_app.protocol.refs import ElementRef
from archit_app.protocol.version import PROTOCOL_VERSION

SnapshotMode = Literal["compact", "detailed"]


class BudgetHints(ProtocolBase):
    """Caps applied while building a snapshot, and what got trimmed."""

    max_elements_per_level: int = Field(default=200, ge=1)
    truncated: bool = False
    elided_kinds: tuple[str, ...] = ()


class ZoningSummary(ProtocolBase):
    """Subset of :class:`archit_app.building.land.ZoningInfo` relevant to agents."""

    zone_code: str | None = None
    max_height_m: float | None = None
    max_far: float | None = None
    max_lot_coverage: float | None = None
    min_lot_area_m2: float | None = None
    allowed_uses: tuple[str, ...] = ()
    notes: str | None = None
    source: str | None = None
    max_floor_area_m2: float | None = None
    max_footprint_m2: float | None = None
    setbacks_m: dict[str, float | None] = Field(default_factory=dict)
    address: str | None = None
    area_m2: float | None = None
    buildable_area_m2: float | None = None
    north_angle_deg: float | None = None


class LevelSummary(ProtocolBase):
    """Per-level data inside a :class:`FloorplanSnapshot`.

    In compact mode, only ``index``, ``name``, ``elevation_m``, ``room_refs``,
    ``wall_count``, and ``area_m2`` are populated.  In detailed mode, the
    raw ``walls``/``furniture``/``columns`` arrays may also be present.
    """

    index: int
    name: str
    elevation_m: float
    floor_height_m: float | None = None
    room_refs: tuple[ElementRef, ...] = ()
    rooms: tuple[dict[str, Any], ...] = ()
    wall_count: int = 0
    area_m2: float = 0.0
    walls: tuple[dict[str, Any], ...] | None = None
    furniture: tuple[dict[str, Any], ...] | None = None
    columns: tuple[dict[str, Any], ...] | None = None
    bounding_box: dict[str, Any] | None = None


class FloorplanSnapshot(ProtocolBase):
    """A read-only, JSON-serializable view of a building for agent consumption.

    Two modes:
      - ``compact``  — counts and per-room summaries only; cheap on tokens.
      - ``detailed`` — adds wall geometry, columns, furniture per level.
    """

    message_type: Literal["floorplan_snapshot"] = "floorplan_snapshot"
    protocol_version: str = PROTOCOL_VERSION
    snapshot_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: SnapshotMode
    building_id: str
    building_revision: int = 0
    units: Literal["m", "mm", "ft"] = "m"
    building_name: str | None = None
    project_number: str | None = None
    architect: str | None = None
    total_levels: int = 0
    total_rooms: int = 0
    gross_floor_area_m2: float = 0.0
    net_floor_area_m2: float = 0.0
    area_by_program_m2: dict[str, float] = Field(default_factory=dict)
    elevators_count: int = 0
    levels: tuple[LevelSummary, ...] = ()
    zoning: ZoningSummary | None = None
    budget: BudgetHints = Field(default_factory=BudgetHints)

    @field_validator("created_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @model_validator(mode="after")
    def _check_compact_has_no_raw_arrays(self) -> "FloorplanSnapshot":
        if self.mode == "compact":
            for lv in self.levels:
                if lv.walls is not None or lv.furniture is not None or lv.columns is not None:
                    raise ValueError(
                        "FloorplanSnapshot.mode='compact' must not include raw "
                        "walls/furniture/columns arrays; use mode='detailed'."
                    )
        return self
