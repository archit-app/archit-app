import math
import pytest

from archit_app import Building, Land, Setbacks, ZoningInfo


# A roughly 100m × 60m rectangular parcel in San Francisco
_SF_COORDS = [
    (37.77490, -122.41940),
    (37.77499, -122.41940),
    (37.77499, -122.41872),
    (37.77490, -122.41872),
]


# ---------------------------------------------------------------------------
# from_latlon
# ---------------------------------------------------------------------------


def test_from_latlon_creates_land():
    land = Land.from_latlon(_SF_COORDS, address="123 Main St")
    assert land.address == "123 Main St"
    assert land.latlon_coords == tuple(_SF_COORDS)
    assert land.origin_lat is not None
    assert land.origin_lon is not None


def test_from_latlon_area_reasonable():
    land = Land.from_latlon(_SF_COORDS)
    # Rough rectangle ~10m × 60m = 600 m²; allow ±20%
    assert 400 < land.area_m2 < 800


def test_from_latlon_too_few_coords():
    with pytest.raises(ValueError, match="At least 3"):
        Land.from_latlon([(37.0, -122.0), (37.1, -122.1)])


def test_from_latlon_roundtrip():
    """Projecting back to lat/lon should recover the original coords within ~1 mm."""
    land = Land.from_latlon(_SF_COORDS)
    recovered = land.latlon_boundary
    assert recovered is not None
    for (orig_lat, orig_lon), (rec_lat, rec_lon) in zip(_SF_COORDS, recovered):
        assert abs(orig_lat - rec_lat) < 1e-5
        assert abs(orig_lon - rec_lon) < 1e-5


def test_centroid_latlon():
    land = Land.from_latlon(_SF_COORDS)
    c = land.centroid_latlon
    assert c is not None
    lat, lon = c
    # Centroid should be inside the bounding box of the input coords
    lats = [p[0] for p in _SF_COORDS]
    lons = [p[1] for p in _SF_COORDS]
    assert min(lats) < lat < max(lats)
    assert min(lons) < lon < max(lons)


# ---------------------------------------------------------------------------
# from_polygon
# ---------------------------------------------------------------------------


def test_from_polygon():
    from archit_app import Polygon2D, Point2D, WORLD

    pts = [Point2D(x=x, y=y) for x, y in [(0, 0), (60, 0), (60, 100), (0, 100)]]
    poly = Polygon2D(exterior=tuple(pts), crs=WORLD)
    land = Land.from_polygon(poly, address="Metric lot")
    assert land.area_m2 == pytest.approx(6000.0)
    assert land.latlon_coords is None
    assert land.centroid_latlon is None


# ---------------------------------------------------------------------------
# Setbacks & buildable boundary
# ---------------------------------------------------------------------------


def test_buildable_area_no_setbacks():
    land = Land.from_latlon(_SF_COORDS)
    assert land.buildable_area_m2 == pytest.approx(land.area_m2)


def test_buildable_area_with_setbacks():
    land = Land.from_latlon(_SF_COORDS).with_setbacks(
        Setbacks(front=1.0, back=1.0, left=1.0, right=1.0)
    )
    # Conservative buffer = 1.0 m inward on a ~10m × 60m lot
    assert land.buildable_area_m2 < land.area_m2
    assert land.buildable_area_m2 > 0


def test_setbacks_min_max():
    sb = Setbacks(front=3.0, back=6.0, left=1.5, right=1.5)
    assert sb.min_setback == pytest.approx(1.5)
    assert sb.max_setback == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# ZoningInfo
# ---------------------------------------------------------------------------


def test_zoning_far():
    zoning = ZoningInfo(zone_code="R-2", max_far=1.5)
    assert zoning.max_floor_area_m2(6000.0) == pytest.approx(9000.0)


def test_zoning_lot_coverage():
    zoning = ZoningInfo(max_lot_coverage=0.6)
    assert zoning.max_footprint_m2(6000.0) == pytest.approx(3600.0)


def test_zoning_none_returns_none():
    zoning = ZoningInfo()
    assert zoning.max_floor_area_m2(6000.0) is None
    assert zoning.max_footprint_m2(6000.0) is None


# ---------------------------------------------------------------------------
# Land zoning helpers
# ---------------------------------------------------------------------------


def test_land_max_floor_area():
    land = Land.from_latlon(_SF_COORDS).with_zoning(
        ZoningInfo(zone_code="C-1", max_far=2.0)
    )
    assert land.max_floor_area_m2 == pytest.approx(land.area_m2 * 2.0)


def test_land_no_zoning_returns_none():
    land = Land.from_latlon(_SF_COORDS)
    assert land.max_floor_area_m2 is None
    assert land.max_footprint_m2 is None


# ---------------------------------------------------------------------------
# to_agent_context
# ---------------------------------------------------------------------------


def test_to_agent_context_keys():
    land = (
        Land.from_latlon(_SF_COORDS, address="123 Main St", elevation_m=15.0)
        .with_setbacks(Setbacks(front=1.0, back=1.0, left=0.5, right=0.5))
        .with_zoning(ZoningInfo(zone_code="R-2", max_far=1.5, max_height_m=10.0))
    )
    ctx = land.to_agent_context()

    assert ctx["address"] == "123 Main St"
    assert ctx["elevation_m"] == 15.0
    assert "area_m2" in ctx
    assert "perimeter_m" in ctx
    assert "latlon_coords" in ctx
    assert "centroid_latlon" in ctx
    assert "latlon_boundary" in ctx
    assert ctx["setbacks_m"]["front"] == 1.0
    assert ctx["setbacks_m"]["back"] == 1.0
    assert ctx["zoning"]["zone_code"] == "R-2"
    assert ctx["zoning"]["max_far"] == 1.5
    assert ctx["zoning"]["max_floor_area_m2"] is not None


def test_to_agent_context_json_serialisable():
    import json

    land = Land.from_latlon(_SF_COORDS, address="Test")
    ctx = land.to_agent_context()
    # Must not raise
    json.dumps(ctx)


def test_to_agent_context_no_zoning():
    land = Land.from_latlon(_SF_COORDS)
    ctx = land.to_agent_context()
    assert "zoning" not in ctx


# ---------------------------------------------------------------------------
# Immutability and mutation helpers
# ---------------------------------------------------------------------------


def test_land_frozen():
    land = Land.from_latlon(_SF_COORDS)
    with pytest.raises(Exception):
        land.address = "changed"  # type: ignore


def test_with_helpers_return_new_instance():
    land = Land.from_latlon(_SF_COORDS)
    land2 = land.with_address("New Address")
    assert land2.address == "New Address"
    assert land.address == ""  # original unchanged

    land3 = land.with_elevation(42.0)
    assert land3.elevation_m == 42.0
    assert land.elevation_m == 0.0

    land4 = land.with_north_angle(45.0)
    assert land4.north_angle == 45.0
    assert land.north_angle == 0.0


# ---------------------------------------------------------------------------
# Building integration
# ---------------------------------------------------------------------------


def test_building_with_land():
    land = Land.from_latlon(_SF_COORDS)
    building = Building().with_land(land)
    assert building.land is land


def test_building_land_defaults_none():
    assert Building().land is None
