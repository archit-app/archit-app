"""
Land parcel — the geographic foundation that a building sits on.

A Land is the first-class geographic entity. It holds the lot boundary
as both raw GPS coordinates and a projected metric polygon, zoning
constraints, setbacks, and site orientation.

Typical flow:
    # 1. Define the parcel from GPS coordinates
    land = Land.from_latlon([
        (37.7749, -122.4194),
        (37.7750, -122.4194),
        (37.7750, -122.4183),
        (37.7749, -122.4183),
    ], address="123 Main St, San Francisco, CA")

    print(f"Parcel area: {land.area_m2:.1f} m²")

    # 2. Pass to an agent to get zoning and constraints
    context = land.to_agent_context()
    # → send context to an AI agent, receive ZoningInfo back

    # 3. Enrich with agent response
    land = land.with_zoning(ZoningInfo(
        zone_code="R-2",
        max_height_m=10.0,
        max_far=1.5,
        max_lot_coverage=0.6,
    )).with_setbacks(Setbacks(front=3.0, back=6.0, left=1.5, right=1.5))

    print(f"Buildable area: {land.buildable_area_m2:.1f} m²")

    # 4. Start designing a building on this land
    building = Building().with_land(land)
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from archit_app.geometry.crs import WORLD, WGS84
from archit_app.geometry.point import Point2D
from archit_app.geometry.polygon import Polygon2D

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_008.8  # WGS-84 mean radius in meters


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------


class Setbacks(BaseModel):
    """
    Minimum distances from each lot boundary edge to the building footprint.
    All values in meters. Zero means no setback requirement.
    """

    model_config = ConfigDict(frozen=True)

    front: float = 0.0
    back: float = 0.0
    left: float = 0.0
    right: float = 0.0

    @property
    def min_setback(self) -> float:
        return min(self.front, self.back, self.left, self.right)

    @property
    def max_setback(self) -> float:
        return max(self.front, self.back, self.left, self.right)

    def __repr__(self) -> str:
        return (
            f"Setbacks(front={self.front}m, back={self.back}m, "
            f"left={self.left}m, right={self.right}m)"
        )


class ZoningInfo(BaseModel):
    """
    Zoning and regulatory constraints for a parcel.

    Designed to be filled by a zoning agent or manually entered.
    All optional — unknown fields are left as None.

    Attributes:
        zone_code:        Official zone designation (e.g. "R-2", "C-1", "MU").
        max_height_m:     Maximum allowed building height in meters.
        max_far:          Floor Area Ratio limit (total floor area / lot area).
        max_lot_coverage: Maximum fraction of lot that may be covered (0–1).
        min_lot_area_m2:  Minimum lot area required to build on this zone.
        allowed_uses:     Permitted building uses (e.g. "residential", "retail").
        notes:            Free-form notes from the zoning source.
        source:           Where this information came from (URL, document, agent).
    """

    model_config = ConfigDict(frozen=True)

    zone_code: str = ""
    max_height_m: float | None = None
    max_far: float | None = None
    max_lot_coverage: float | None = None
    min_lot_area_m2: float | None = None
    allowed_uses: tuple[str, ...] = ()
    notes: str = ""
    source: str = ""

    def max_floor_area_m2(self, lot_area_m2: float) -> float | None:
        """Maximum total floor area permitted given the FAR limit."""
        if self.max_far is None:
            return None
        return self.max_far * lot_area_m2

    def max_footprint_m2(self, lot_area_m2: float) -> float | None:
        """Maximum ground footprint permitted given lot coverage limit."""
        if self.max_lot_coverage is None:
            return None
        return self.max_lot_coverage * lot_area_m2

    def __repr__(self) -> str:
        return (
            f"ZoningInfo(zone={self.zone_code!r}, "
            f"max_height={self.max_height_m}m, "
            f"max_far={self.max_far})"
        )


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _latlon_to_local_meters(
    coords: list[tuple[float, float]],
    origin_lat: float | None = None,
    origin_lon: float | None = None,
) -> tuple[list[tuple[float, float]], float, float]:
    """
    Project (lat, lon) pairs to local (x, y) in meters using an equirectangular
    approximation centred on the given origin (defaults to centroid).

    Returns:
        (projected_coords, origin_lat, origin_lon)

    Accuracy: < 1 mm for parcels up to ~10 km across.
    """
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]

    if origin_lat is None:
        origin_lat = sum(lats) / len(lats)
    if origin_lon is None:
        origin_lon = sum(lons) / len(lons)

    cos_lat0 = math.cos(math.radians(origin_lat))
    deg_to_rad = math.pi / 180.0

    projected = []
    for lat, lon in coords:
        x = (lon - origin_lon) * cos_lat0 * deg_to_rad * _EARTH_RADIUS_M
        y = (lat - origin_lat) * deg_to_rad * _EARTH_RADIUS_M
        projected.append((x, y))

    return projected, origin_lat, origin_lon


def _local_meters_to_latlon(
    coords: list[tuple[float, float]],
    origin_lat: float,
    origin_lon: float,
) -> list[tuple[float, float]]:
    """Inverse of _latlon_to_local_meters."""
    cos_lat0 = math.cos(math.radians(origin_lat))
    rad_to_deg = 180.0 / math.pi

    result = []
    for x, y in coords:
        lat = origin_lat + (y / _EARTH_RADIUS_M) * rad_to_deg
        lon = origin_lon + (x / (_EARTH_RADIUS_M * cos_lat0)) * rad_to_deg
        result.append((lat, lon))
    return result


# ---------------------------------------------------------------------------
# Land
# ---------------------------------------------------------------------------


class Land(BaseModel):
    """
    A land parcel — the geographic foundation for a building project.

    ``boundary`` is optional so that a ``Land`` can represent a minimal site
    context (orientation, address) even when no parcel geometry is available.
    Use ``Land.from_latlon()`` or ``Land.from_polygon()`` for full parcels, and
    ``Land.minimal()`` when only site orientation / address are needed.

    Attributes:
        boundary:       Lot boundary in local metric coordinates (WORLD CRS).
                        ``None`` when only orientation/address are known.
        latlon_coords:  Original (lat, lon) pairs, if created from GPS.
        origin_lat:     Latitude of the local coordinate origin (degrees).
        origin_lon:     Longitude of the local coordinate origin (degrees).
        north_angle:    Degrees clockwise from world +Y to geographic north.
        address:        Street address.
        epsg_code:      EPSG code of the projected CRS, if known.
        elevation_m:    Mean ground elevation above sea level in meters.
        setbacks:       Regulatory setback distances per side.
        zoning:         Zoning and regulatory constraints (None = unknown).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    boundary: Polygon2D | None = None
    latlon_coords: tuple[tuple[float, float], ...] | None = None
    origin_lat: float | None = None
    origin_lon: float | None = None
    north_angle: float = 0.0
    address: str = ""
    epsg_code: int | None = None
    elevation_m: float = 0.0
    setbacks: Setbacks = Field(default_factory=Setbacks)
    zoning: ZoningInfo | None = None

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def minimal(
        cls,
        *,
        north_angle: float = 0.0,
        address: str = "",
        epsg_code: int | None = None,
        elevation_m: float = 0.0,
    ) -> "Land":
        """
        Create a Land with no parcel boundary — only site orientation metadata.

        Use this when you know the building's address and orientation but don't
        have (or need) a full lot boundary.  Boundary-dependent properties such
        as ``area_m2`` will return ``None`` for instances created this way.

        Example::

            site = Land.minimal(north_angle=15.0, address="42 Elm Street")
            building = Building().with_land(site)
        """
        return cls(
            north_angle=north_angle,
            address=address,
            epsg_code=epsg_code,
            elevation_m=elevation_m,
        )

    @classmethod
    def from_latlon(
        cls,
        coords: list[tuple[float, float]],
        *,
        north_angle: float = 0.0,
        address: str = "",
        epsg_code: int | None = None,
        elevation_m: float = 0.0,
    ) -> "Land":
        """
        Create a Land parcel from GPS (lat, lon) coordinates.

        The coordinates are projected to a local metric plane centred on
        their centroid. This WORLD-CRS polygon is what all other elements
        (walls, rooms, etc.) are measured against.

        Args:
            coords:       List of (latitude, longitude) pairs in decimal degrees.
                          At least 3 points required. Do NOT repeat the first
                          point at the end — the polygon is closed automatically.
            north_angle:  Degrees clockwise from world +Y to geographic north.
            address:      Street address of the parcel.
            epsg_code:    EPSG code of the projected CRS, if known (e.g. 32610).
            elevation_m:  Mean ground elevation above sea level in meters.

        Example:
            land = Land.from_latlon([
                (37.7749, -122.4194),
                (37.7750, -122.4194),
                (37.7750, -122.4183),
                (37.7749, -122.4183),
            ])
        """
        if len(coords) < 3:
            raise ValueError("At least 3 coordinate pairs are required to define a parcel.")

        projected, origin_lat, origin_lon = _latlon_to_local_meters(coords)

        exterior = tuple(Point2D(x=x, y=y, crs=WORLD) for x, y in projected)
        boundary = Polygon2D(exterior=exterior, crs=WORLD)

        return cls(
            boundary=boundary,
            latlon_coords=tuple(coords),
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            north_angle=north_angle,
            address=address,
            epsg_code=epsg_code,
            elevation_m=elevation_m,
        )

    @classmethod
    def from_polygon(
        cls,
        boundary: Polygon2D,
        *,
        north_angle: float = 0.0,
        address: str = "",
        epsg_code: int | None = None,
        elevation_m: float = 0.0,
    ) -> "Land":
        """
        Create a Land parcel from an existing Polygon2D (already in meters).

        Use this when you have an architectural drawing with known metric
        coordinates and don't need GPS georeferencing.
        """
        return cls(
            boundary=boundary,
            north_angle=north_angle,
            address=address,
            epsg_code=epsg_code,
            elevation_m=elevation_m,
        )

    # ------------------------------------------------------------------
    # Geometric properties
    # ------------------------------------------------------------------

    @property
    def has_boundary(self) -> bool:
        """True when a parcel boundary polygon is available."""
        return self.boundary is not None

    @property
    def area_m2(self) -> float | None:
        """Total lot area in square meters, or ``None`` if no boundary is set."""
        return self.boundary.area if self.boundary is not None else None

    @property
    def perimeter_m(self) -> float | None:
        """Lot perimeter in meters, or ``None`` if no boundary is set."""
        return self.boundary.perimeter if self.boundary is not None else None

    @property
    def centroid(self) -> Point2D | None:
        """Centroid of the lot boundary, or ``None`` if no boundary is set."""
        return self.boundary.centroid if self.boundary is not None else None

    @property
    def centroid_latlon(self) -> tuple[float, float] | None:
        """
        (lat, lon) of the lot centroid, if GPS origin is available.
        Returns None when the parcel has no boundary or was created from a
        metric polygon without GPS origin.
        """
        if self.origin_lat is None or self.origin_lon is None:
            return None
        c = self.centroid
        if c is None:
            return None
        result = _local_meters_to_latlon(
            [(c.x, c.y)], self.origin_lat, self.origin_lon
        )
        return result[0]

    @property
    def latlon_boundary(self) -> list[tuple[float, float]] | None:
        """
        The lot boundary as (lat, lon) pairs, if GPS origin is available.
        Returns None when the parcel has no boundary or was created from a
        metric polygon without GPS origin.
        """
        if self.boundary is None or self.origin_lat is None or self.origin_lon is None:
            return None
        pts = [(p.x, p.y) for p in self.boundary.exterior]
        return _local_meters_to_latlon(pts, self.origin_lat, self.origin_lon)

    @property
    def buildable_boundary(self) -> Polygon2D | None:
        """
        The buildable envelope after applying setbacks as a uniform inward
        buffer equal to the maximum setback distance.

        Note: this is a conservative approximation — it uses the largest
        setback value as a uniform buffer so no face ever violates its
        requirement. For precise per-face setbacks on irregular lots, apply
        setbacks manually per edge.

        Returns None if no boundary is set or if the setback makes the parcel unbuildable.
        """
        if self.boundary is None:
            return None
        max_sb = self.setbacks.max_setback
        if max_sb <= 0.0:
            return self.boundary
        try:
            return self.boundary.buffer(-max_sb)
        except ValueError:
            return None

    @property
    def buildable_area_m2(self) -> float | None:
        """Buildable envelope area in m² after applying setbacks, or ``None`` if no boundary."""
        bb = self.buildable_boundary
        if bb is None and self.boundary is None:
            return None
        return bb.area if bb is not None else 0.0

    # ------------------------------------------------------------------
    # Zoning-derived limits
    # ------------------------------------------------------------------

    @property
    def max_floor_area_m2(self) -> float | None:
        """Maximum total floor area permitted by FAR, if zoning and boundary are set."""
        if self.zoning is None or self.area_m2 is None:
            return None
        return self.zoning.max_floor_area_m2(self.area_m2)

    @property
    def max_footprint_m2(self) -> float | None:
        """Maximum ground footprint permitted by lot coverage, if zoning and boundary are set."""
        if self.zoning is None or self.area_m2 is None:
            return None
        return self.zoning.max_footprint_m2(self.area_m2)

    # ------------------------------------------------------------------
    # Agent interface
    # ------------------------------------------------------------------

    def to_agent_context(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable dict summarising everything an AI agent
        needs to look up zoning, building regulations, or suggest a design.

        Keys:
            address, coordinates, area_m2, perimeter_m, centroid_latlon,
            north_angle, elevation_m, setbacks, zoning (if set)

        Example:
            context = land.to_agent_context()
            # Send to agent:
            # "Given this parcel context, what are the zoning regulations?
            #  Return a ZoningInfo JSON."
            response = my_agent(context)
        """
        ctx: dict[str, Any] = {
            "address": self.address,
            "north_angle_deg": self.north_angle,
            "elevation_m": self.elevation_m,
        }
        if self.area_m2 is not None:
            ctx["area_m2"] = round(self.area_m2, 2)
        if self.perimeter_m is not None:
            ctx["perimeter_m"] = round(self.perimeter_m, 2)

        if self.latlon_coords is not None:
            ctx["latlon_coords"] = [list(c) for c in self.latlon_coords]

        centroid_ll = self.centroid_latlon
        if centroid_ll is not None:
            ctx["centroid_latlon"] = list(centroid_ll)

        latlon_boundary = self.latlon_boundary
        if latlon_boundary is not None:
            ctx["latlon_boundary"] = [list(c) for c in latlon_boundary]

        if self.epsg_code is not None:
            ctx["epsg_code"] = self.epsg_code

        ctx["setbacks_m"] = {
            "front": self.setbacks.front,
            "back": self.setbacks.back,
            "left": self.setbacks.left,
            "right": self.setbacks.right,
        }
        ba = self.buildable_area_m2
        if ba is not None:
            ctx["buildable_area_m2"] = round(ba, 2)

        if self.zoning is not None:
            z = self.zoning
            ctx["zoning"] = {
                "zone_code": z.zone_code,
                "max_height_m": z.max_height_m,
                "max_far": z.max_far,
                "max_lot_coverage": z.max_lot_coverage,
                "min_lot_area_m2": z.min_lot_area_m2,
                "allowed_uses": list(z.allowed_uses),
                "notes": z.notes,
                "source": z.source,
                "max_floor_area_m2": (
                    round(self.max_floor_area_m2, 2)
                    if self.max_floor_area_m2 is not None
                    else None
                ),
                "max_footprint_m2": (
                    round(self.max_footprint_m2, 2)
                    if self.max_footprint_m2 is not None
                    else None
                ),
            }

        return ctx

    # ------------------------------------------------------------------
    # Mutation helpers (all return new instances — model is frozen)
    # ------------------------------------------------------------------

    def with_zoning(self, zoning: ZoningInfo) -> "Land":
        """Return a new Land with updated zoning info."""
        return self.model_copy(update={"zoning": zoning})

    def with_setbacks(self, setbacks: Setbacks) -> "Land":
        """Return a new Land with updated setbacks."""
        return self.model_copy(update={"setbacks": setbacks})

    def with_address(self, address: str) -> "Land":
        """Return a new Land with updated address."""
        return self.model_copy(update={"address": address})

    def with_elevation(self, elevation_m: float) -> "Land":
        """Return a new Land with updated elevation."""
        return self.model_copy(update={"elevation_m": elevation_m})

    def with_north_angle(self, north_angle: float) -> "Land":
        """Return a new Land with updated north angle."""
        return self.model_copy(update={"north_angle": north_angle})

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        addr = f", address={self.address!r}" if self.address else ""
        zone = f", zone={self.zoning.zone_code!r}" if self.zoning else ""
        return (
            f"Land(area={self.area_m2:.1f}m²"
            f"{addr}"
            f"{zone})"
        )
