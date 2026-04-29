# Agent Protocol — `archit_app.protocol`

`archit_app.protocol` is a versioned, strict-Pydantic message layer that standardises how AI agents share floorplan state, declare design decisions, log mutations, and report analysis results.

All models use `ConfigDict(frozen=True, extra="forbid")` — unknown fields are rejected at parse time, and every message is immutable after construction.

```python
from archit_app.protocol import (
    PROTOCOL_VERSION,          # "1.0.0"
    FloorplanSnapshot,
    AgentHandoff,
    MutationEnvelope,
    ProtocolReport,
    ElementRef,
    parse_message,
    dump_message,
)
```

---

## Version

```python
from archit_app.protocol.version import PROTOCOL_VERSION, is_compatible, assert_compatible

print(PROTOCOL_VERSION)          # "1.0.0"

# Check compatibility before accepting a remote message
is_compatible("1.0.0")           # True  — same major
is_compatible("1.2.0")           # True  — minor bump (additive)
is_compatible("2.0.0")           # False — major bump, raises IncompatibleProtocolError

assert_compatible("1.0.0")       # no-op if compatible, raises otherwise
```

**Versioning rules:**

| Change | Version bump | Backwards compatible |
|--------|-------------|----------------------|
| Add optional field | minor | yes |
| Rename / remove field | major | no |
| Tighten validator | major | no |
| New `message_type` literal | minor | yes |

---

## ElementRef

A typed pointer to any building element, with an optional revision number for staleness detection.

```python
from archit_app.protocol import ElementRef

ref = ElementRef(
    id="a1b2c3d4-...",
    kind="room",          # see full list below
    level_index=0,        # None for building-level elements
    revision=5,           # building_revision at time of reference
)
```

**`kind` literals:**

`"room"` · `"wall"` · `"opening"` · `"column"` · `"beam"` · `"slab"` · `"staircase"` · `"ramp"` · `"elevator"` · `"furniture"` · `"annotation"` · `"level"` · `"building"` · `"land"` · `"grid"`

---

## FloorplanSnapshot

A validated snapshot of the building at a point in time. Produced by `Building.to_protocol_snapshot()`.

```python
snap = building.to_protocol_snapshot(
    mode="compact",       # "compact" | "detailed"
    level_index=None,     # None → all levels
    building_revision=0,
)

print(snap.message_type)    # "floorplan_snapshot"
print(snap.mode)            # "compact"
print(snap.total_rooms)     # 4
print(snap.protocol_version) # "1.0.0"
```

**Compact vs detailed:**

| Field | compact | detailed |
|-------|---------|---------|
| `levels[].room_refs` | ✓ | ✓ |
| `levels[].walls` | — | ✓ |
| `levels[].columns` | — | ✓ |
| `levels[].furniture` | — | ✓ |
| `zoning` | ✓ | ✓ |

**Budget hints** (prevent oversized snapshots):

```python
from archit_app.protocol import BudgetHints

snap = building.to_protocol_snapshot(
    mode="detailed",
    budget=BudgetHints(max_elements_per_level=50),
)
if snap.budget.truncated:
    print("Some elements were elided:", snap.budget.elided_kinds)
```

**JSON round-trip:**

```python
json_str = snap.model_dump_json(exclude_none=True)
restored = parse_message(json_str)   # → FloorplanSnapshot
```

---

## AgentHandoff

Structured envelope each agent emits at task completion. Captures decisions, mutations, open questions, and hints for the next agent.

```python
from archit_app.protocol import AgentHandoff
from archit_app.protocol.handoff import Decision, OpenQuestion, NextAgentHint

handoff = AgentHandoff(
    agent_role="architect",                       # see roles below
    summary="Placed 6 rooms on level 0 (90 m²).", # ≤500 chars
    decisions=(
        Decision(
            title="Compact footprint",
            rationale="10×9 m fits the programme with 20% circulation margin.",
        ),
    ),
    changes=(
        ElementRef(id="...", kind="room", level_index=0),
    ),
    open_questions=(
        OpenQuestion(question="Client prefers open-plan kitchen/dining — merge?"),
    ),
    next_agent_hints=(
        NextAgentHint(hint="Structural grid should align with 5 m room bays."),
    ),
)
```

**`agent_role` literals:**

`"architect"` · `"structural_engineer"` · `"compliance_analyst"` · `"interior_designer"` · `"space_programmer"` · `"bim_coordinator"` · `"planner"`

---

## MutationEnvelope

Audit record for every building state change. Tools that mutate the building emit one envelope per operation.

```python
from archit_app.protocol import MutationEnvelope, ElementRef

envelope = MutationEnvelope(
    agent_role="architect",
    operation="create",          # see operations below
    target_ref=ElementRef(id="...", kind="room", level_index=0),
    before=None,                 # None for create
    after={"name": "Living", "program": "living", "area_m2": 20.0},
    justification="Added living room per client brief (min 18 m²).",  # ≥20 chars
    constraints_respected=("min_area", "tiling"),
)
```

**`operation` literals:**

`"create"` · `"update"` · `"delete"` · `"move"` · `"split"` · `"merge"`

**Validation rules:**

| Operation | `before` | `after` |
|-----------|---------|---------|
| `create` | must be `None` | required |
| `delete` | required | must be `None` |
| `update` / `move` / `split` / `merge` | required | required |

---

## ProtocolReport

Unified analysis report replacing the five inconsistent analysis return shapes. Produced by adapter functions (see below).

```python
from archit_app.protocol import ProtocolReport
from archit_app.protocol.report import ProtocolCheck, Suggestion

report = ProtocolReport(
    kind="compliance",           # see kinds below
    level_index=None,
    checks=(
        ProtocolCheck(
            code="compliance.far",
            passed=True,
            severity="info",
            message="FAR 0.45 within limit 0.5",
            metric={"actual": 0.45, "limit": 0.5},
        ),
    ),
    summary=ProtocolReport.summarize(checks),  # classmethod helper
    suggestions=(),
)
```

**`kind` literals:**

`"egress"` · `"daylighting"` · `"accessibility"` · `"area"` · `"compliance"` · `"custom"`

**`severity` literals:**

`"info"` · `"warn"` · `"error"`

---

## Adapters

Pure functions that convert existing analysis dataclass/dict results into `ProtocolReport`:

```python
from archit_app.protocol import (
    circulation_egress_to_report,    # egress_report() dict → ProtocolReport(kind="egress")
    daylight_results_to_report,      # list[RoomDaylightResult] → ProtocolReport(kind="daylighting")
    accessibility_report_to_protocol, # AccessibilityReport → ProtocolReport(kind="accessibility")
    compliance_report_to_protocol,   # ComplianceReport → ProtocolReport(kind="compliance")
    program_area_to_report,          # list[ProgramAreaResult] → ProtocolReport(kind="area")
)

# Example
from archit_app.analysis.compliance import check_compliance
raw = check_compliance(building, land)
report = compliance_report_to_protocol(raw)
```

---

## ProtocolMessage union

`ProtocolMessage` is a discriminated union over all four message types. `parse_message` dispatches by `message_type`:

```python
from archit_app.protocol import parse_message, dump_message

# Parse from JSON string
msg = parse_message('{"message_type": "floorplan_snapshot", ...}')

# Parse from dict
msg = parse_message({"message_type": "agent_handoff", ...})

# Serialise back to dict
d = dump_message(msg)
```

| `message_type` | Python type |
|----------------|-------------|
| `"floorplan_snapshot"` | `FloorplanSnapshot` |
| `"agent_handoff"` | `AgentHandoff` |
| `"mutation_envelope"` | `MutationEnvelope` |
| `"protocol_report"` | `ProtocolReport` |

---

## JSON Schema export

Export JSON Schemas for all four message types (useful for UI rendering, OpenAPI spec generation, or LLM tool definitions):

```bash
# CLI (installed by archit-app)
archit-app-export-protocol ./schemas/

# Python
from archit_app.protocol.schema_export import export_schemas
export_schemas("./schemas/")
```

This writes five files:

```
schemas/
├── FloorplanSnapshot.schema.json
├── AgentHandoff.schema.json
├── MutationEnvelope.schema.json
├── ProtocolReport.schema.json
└── ProtocolMessage.schema.json
```

---

## Using the protocol in agents

### Read-only context (compact snapshot)

```python
snap = building.to_protocol_snapshot(mode="compact", building_revision=state.building_revision)
agent_input = snap.model_dump_json(exclude_none=True)
# Pass agent_input as context to the next LLM call
```

### Recording a mutation

```python
from archit_app.protocol import MutationEnvelope, ElementRef

before_dict = {"name": old_room.name, "area_m2": old_room.area}
state.update(new_building)
after_dict  = {"name": new_room.name, "area_m2": new_room.area}

envelope = MutationEnvelope(
    agent_role="architect",
    operation="update",
    target_ref=ElementRef(id=str(room_id), kind="room", level_index=0,
                          revision=state.building_revision),
    before=before_dict,
    after=after_dict,
    justification="Expanded bedroom to meet 12 m² minimum.",
)
state.protocol_log.append(envelope)
```

### Emitting a handoff

```python
handoff = AgentHandoff(
    agent_role="compliance_analyst",
    summary="All compliance checks passed. FAR 0.45/0.5, egress ≤30 m on all levels.",
    decisions=(
        Decision(title="Egress compliant", rationale="All rooms within 30 m of a lobby exit."),
    ),
)
state.protocol_log.append(handoff)
```
