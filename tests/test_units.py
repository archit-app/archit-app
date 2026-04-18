"""Tests for archit_app.units — unit conversion and parse_dimension."""

from __future__ import annotations

import math
import pytest

from archit_app.units import (
    to_feet, to_inches, to_mm, to_cm,
    from_feet, from_inches, from_mm, from_cm,
    parse_dimension,
)


# ---------------------------------------------------------------------------
# Conversion round-trips
# ---------------------------------------------------------------------------

class TestConversions:

    def test_feet_roundtrip(self):
        assert from_feet(to_feet(3.0)) == pytest.approx(3.0)

    def test_inches_roundtrip(self):
        assert from_inches(to_inches(1.5)) == pytest.approx(1.5)

    def test_mm_roundtrip(self):
        assert from_mm(to_mm(2.5)) == pytest.approx(2.5)

    def test_cm_roundtrip(self):
        assert from_cm(to_cm(4.2)) == pytest.approx(4.2)

    def test_one_meter_in_feet(self):
        assert to_feet(1.0) == pytest.approx(3.28084, rel=1e-4)

    def test_one_foot_in_meters(self):
        assert from_feet(1.0) == pytest.approx(0.3048, rel=1e-6)

    def test_one_inch_in_meters(self):
        assert from_inches(1.0) == pytest.approx(0.0254, rel=1e-6)

    def test_one_mm_in_meters(self):
        assert from_mm(1.0) == pytest.approx(0.001, rel=1e-6)

    def test_one_meter_in_mm(self):
        assert to_mm(1.0) == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# parse_dimension
# ---------------------------------------------------------------------------

class TestParseDimension:

    # Metric
    def test_bare_meters(self):
        assert parse_dimension("3.8m") == pytest.approx(3.8)

    def test_bare_meters_no_unit(self):
        assert parse_dimension("3.8") == pytest.approx(3.8)

    def test_millimeters(self):
        assert parse_dimension("3800mm") == pytest.approx(3.8)

    def test_centimeters(self):
        assert parse_dimension("380cm") == pytest.approx(3.8)

    # Imperial
    def test_decimal_feet(self):
        assert parse_dimension("10ft") == pytest.approx(from_feet(10))

    def test_bare_inches(self):
        assert parse_dimension('36"') == pytest.approx(from_inches(36))

    def test_feet_and_inches(self):
        # 12'-6" = 12 ft + 6 in = 3.81 m
        assert parse_dimension("12'-6\"") == pytest.approx(from_feet(12) + from_inches(6))

    def test_feet_and_inches_no_separator(self):
        assert parse_dimension("12'6\"") == pytest.approx(from_feet(12) + from_inches(6))

    def test_feet_only_apostrophe(self):
        assert parse_dimension("10'") == pytest.approx(from_feet(10))

    def test_whitespace_tolerance(self):
        assert parse_dimension("  3.8 m  ") == pytest.approx(3.8)

    # Edge cases
    def test_zero(self):
        assert parse_dimension("0m") == pytest.approx(0.0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_dimension("not-a-dimension")

    def test_non_string_raises(self):
        with pytest.raises(TypeError):
            parse_dimension(3.8)  # type: ignore[arg-type]
