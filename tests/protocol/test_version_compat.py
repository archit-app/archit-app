"""Protocol version compatibility helpers."""

from __future__ import annotations

import pytest

from archit_app.protocol import (
    PROTOCOL_VERSION,
    IncompatibleProtocolError,
    assert_compatible,
    is_compatible,
)


def test_same_version_compatible():
    assert is_compatible(PROTOCOL_VERSION) is True
    assert_compatible(PROTOCOL_VERSION)


def test_minor_bump_compatible():
    major, minor, patch = PROTOCOL_VERSION.split(".")
    bumped = f"{major}.{int(minor) + 1}.0"
    assert is_compatible(bumped) is True


def test_major_bump_incompatible():
    major, _, _ = PROTOCOL_VERSION.split(".")
    bumped = f"{int(major) + 1}.0.0"
    assert is_compatible(bumped) is False
    with pytest.raises(IncompatibleProtocolError):
        assert_compatible(bumped)


def test_invalid_version_string_raises():
    with pytest.raises(ValueError):
        is_compatible("not-a-version")
