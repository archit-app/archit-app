"""Protocol version and compatibility helpers.

The Floorplan Agent Protocol uses semver and is independent of the on-disk
JSON file format version (``archit_app.io.json_schema.FORMAT_VERSION``).
"""

from __future__ import annotations

PROTOCOL_VERSION: str = "1.0.0"


class IncompatibleProtocolError(ValueError):
    """Raised when a remote protocol version is incompatible with this one."""


def _split(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver string: {version!r}")
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Invalid semver string: {version!r}") from exc


def is_compatible(remote: str, local: str = PROTOCOL_VERSION) -> bool:
    """Return True iff *remote* and *local* share the same major version."""
    return _split(remote)[0] == _split(local)[0]


def assert_compatible(remote: str, local: str = PROTOCOL_VERSION) -> None:
    """Raise :class:`IncompatibleProtocolError` on major-version mismatch."""
    if not is_compatible(remote, local):
        raise IncompatibleProtocolError(
            f"Protocol major version mismatch: remote={remote!r}, local={local!r}"
        )
