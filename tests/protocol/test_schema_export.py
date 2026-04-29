"""Schema export writes valid JSON Schema files."""

from __future__ import annotations

import json
from pathlib import Path

from archit_app.protocol import export_schemas


def test_export_schemas_writes_five_files(tmp_path: Path):
    paths = export_schemas(tmp_path)
    expected = {
        "floorplan_snapshot.schema.json",
        "agent_handoff.schema.json",
        "mutation_envelope.schema.json",
        "protocol_report.schema.json",
        "protocol_message.schema.json",
    }
    assert set(paths) == expected
    for name, p in paths.items():
        assert p.exists(), name
        schema = json.loads(p.read_text())
        # Each top-level model schema is an object with properties or a discriminator (union).
        assert isinstance(schema, dict)
        assert (
            "properties" in schema
            or "oneOf" in schema
            or "$ref" in schema
        ), f"{name} schema has no recognized top-level keys"


def test_export_schemas_idempotent(tmp_path: Path):
    paths1 = export_schemas(tmp_path)
    paths2 = export_schemas(tmp_path)
    for name in paths1:
        assert paths1[name].read_text() == paths2[name].read_text()
