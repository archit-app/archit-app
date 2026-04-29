"""Floorplan Agent Protocol — versioned, strict Pydantic models for LLM agents.

Four message kinds form a discriminated union (:class:`ProtocolMessage`):

* :class:`FloorplanSnapshot` — read-only view of the current building.
* :class:`AgentHandoff`      — emitted by an agent when its turn ends.
* :class:`MutationEnvelope`  — wraps every state change an agent proposes.
* :class:`ProtocolReport`    — unified analysis report (egress, daylight, etc.).

See ``docs/protocol.md`` (in archit-studio) for the wider integration picture.
"""

from __future__ import annotations

from archit_app.protocol.adapters import (
    accessibility_report_to_protocol,
    circulation_egress_to_report,
    compliance_report_to_protocol,
    daylight_results_to_report,
    program_area_to_report,
)
from archit_app.protocol.handoff import (
    AgentHandoff,
    AgentRole,
    Decision,
    NextAgentHint,
    OpenQuestion,
    Priority,
    Telemetry,
)
from archit_app.protocol.message import ProtocolMessage, dump_message, parse_message
from archit_app.protocol.mutation import MutationEnvelope, Operation
from archit_app.protocol.refs import ElementKind, ElementRef
from archit_app.protocol.report import (
    ProtocolCheck,
    ProtocolReport,
    ReportKind,
    ReportSummary,
    Severity,
    Suggestion,
)
from archit_app.protocol.schema_export import export_schemas
from archit_app.protocol.snapshot import (
    BudgetHints,
    FloorplanSnapshot,
    LevelSummary,
    SnapshotMode,
    ZoningSummary,
)
from archit_app.protocol.version import (
    PROTOCOL_VERSION,
    IncompatibleProtocolError,
    assert_compatible,
    is_compatible,
)

__all__ = [
    # Versioning
    "PROTOCOL_VERSION",
    "IncompatibleProtocolError",
    "assert_compatible",
    "is_compatible",
    # References
    "ElementRef",
    "ElementKind",
    # Snapshot
    "FloorplanSnapshot",
    "LevelSummary",
    "ZoningSummary",
    "BudgetHints",
    "SnapshotMode",
    # Handoff
    "AgentHandoff",
    "AgentRole",
    "Decision",
    "OpenQuestion",
    "NextAgentHint",
    "Priority",
    "Telemetry",
    # Mutation
    "MutationEnvelope",
    "Operation",
    # Report
    "ProtocolReport",
    "ProtocolCheck",
    "ReportSummary",
    "ReportKind",
    "Severity",
    "Suggestion",
    # Message union
    "ProtocolMessage",
    "parse_message",
    "dump_message",
    # Schema export
    "export_schemas",
    # Adapters
    "circulation_egress_to_report",
    "daylight_results_to_report",
    "accessibility_report_to_protocol",
    "compliance_report_to_protocol",
    "program_area_to_report",
]
