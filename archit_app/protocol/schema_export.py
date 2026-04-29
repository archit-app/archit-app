"""Export the Floorplan Agent Protocol JSON Schemas.

Usage from Python::

    from archit_app.protocol import export_schemas
    paths = export_schemas("./schemas")

Usage as CLI (registered in ``archit-app/pyproject.toml``)::

    archit-app-export-protocol ./schemas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archit_app.protocol.handoff import AgentHandoff
from archit_app.protocol.message import _ADAPTER as _MESSAGE_ADAPTER
from archit_app.protocol.mutation import MutationEnvelope
from archit_app.protocol.report import ProtocolReport
from archit_app.protocol.snapshot import FloorplanSnapshot

_MODELS = {
    "floorplan_snapshot.schema.json": FloorplanSnapshot,
    "agent_handoff.schema.json": AgentHandoff,
    "mutation_envelope.schema.json": MutationEnvelope,
    "protocol_report.schema.json": ProtocolReport,
}


def export_schemas(out_dir: str | Path) -> dict[str, Path]:
    """Write one JSON Schema per top-level model + the discriminated union.

    Returns a mapping of filename → absolute path of every file written.
    """
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for filename, model in _MODELS.items():
        schema = model.model_json_schema()
        path = out / filename
        path.write_text(json.dumps(schema, indent=2, sort_keys=True))
        written[filename] = path
    union_path = out / "protocol_message.schema.json"
    union_path.write_text(
        json.dumps(_MESSAGE_ADAPTER.json_schema(), indent=2, sort_keys=True)
    )
    written["protocol_message.schema.json"] = union_path
    return written


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archit-app-export-protocol",
        description="Export Floorplan Agent Protocol JSON Schemas.",
    )
    parser.add_argument(
        "out_dir",
        nargs="?",
        default="./schemas",
        help="Directory to write schema files into (default: ./schemas).",
    )
    args = parser.parse_args(argv)
    written = export_schemas(args.out_dir)
    for name, path in sorted(written.items()):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
