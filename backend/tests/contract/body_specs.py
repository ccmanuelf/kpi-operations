"""Request bodies for the routes the capture cannot reach without one.

Same rule as `param_specs.py` and `query_specs.py`: DERIVE, do not hardcode.
Ids come from the resolver's own specs so a body cannot reference a row the
rest of the harness does not; enums are imported from the module the route
validates against; values that are genuinely free inputs are literals with
their reasoning written down.

A body is built by a callable rather than stored as a literal because most of
them embed a seeded id. `build(resolver)` is handed the SAME `Resolver` the
path and query layers use, so its cache -- keyed on spec key -- is shared and
one SELECT answers for every layer that needs the same entity.

TWO ENVELOPES. Most routes take an object. Two take a bare JSON ARRAY,
because their single body param is an un-embedded `List[...]`:
`POST /api/attendance/bulk` and
`POST /api/floating-pool/simulation/optimize-allocation`. Wrapping either in
`{"records": ...}` / `{"shift_requirements": ...}` re-records the
`<status:422>` this layer exists to remove.

WHAT A 2xx DOES NOT PROVE, for two of these routes. `attendance/bulk` catches
every per-row exception and returns 201 regardless, and `workflow/bulk-
transition` answers 200 for ids that matched nothing. For both, the evidence
is in the SHAPE -- a populated `created_ids[]` / a success-branch row -- not
in the status code. `test_write_capture.py` asserts on that, not on 2xx.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict

from backend.orm.work_order import WorkOrderStatus
from backend.schemas.qr import QREntityType
from backend.schemas.workflow import ClosureTriggerEnum


@dataclass(frozen=True)
class BodySpec:
    """One route's request body, and why it is that body."""

    key: str
    build: Callable[[Any], Any]
    note: str


def _forgot_password(resolver: Any) -> Dict[str, Any]:
    return {"email": "contract-harness@example.com"}


def _workflow_config(resolver: Any) -> Dict[str, Any]:
    return {"workflow_closure_trigger": ClosureTriggerEnum.AT_SHIPMENT.value}


def _kpi_thresholds(resolver: Any) -> Dict[str, Any]:
    client_id = resolver.resolve_query("client_id", "/api/kpi-thresholds")
    return {"client_id": client_id, "thresholds": {"fpy": {"target_value": 85.0}}}


def _change_password(resolver: Any) -> Dict[str, Any]:
    from backend.seed.scenarios import DEMO_PASSWORD

    return {"current_password": DEMO_PASSWORD, "new_password": DEMO_PASSWORD}


def _qr_image(resolver: Any) -> Dict[str, Any]:
    work_order_id = resolver.resolve("work_order_id", "/api/qr/generate/image")
    return {"entity_type": QREntityType.WORK_ORDER.value, "entity_id": work_order_id}


def _work_order_transition(resolver: Any) -> Dict[str, Any]:
    return {"to_status": WorkOrderStatus.CLOSED.value}


def _optimize_allocation(resolver: Any) -> Any:
    shift_id = resolver.resolve_query("shift_id", "/api/floating-pool/simulation/optimize-allocation")
    return [
        {
            "shift_id": int(shift_id),
            "shift_name": "Contract Capture Shift",
            "required_employees": 10,
            "regular_employees": 8,
        }
    ]


#: Keyed by golden route. Gated two-sided by `test_write_capture.py`: a route
#: needing a body without an entry, and an entry for a route that needs none,
#: both fail by name.
BODY_REGISTRY: Dict[str, BodySpec] = {
    "POST /api/auth/forgot-password": BodySpec(
        key="POST /api/auth/forgot-password",
        build=_forgot_password,
        note="A literal address, deliberately NOT a seeded one. The route answers identically for "
        "a matched and an unmatched email -- that is its documented anti-enumeration property -- "
        "so a seeded address would buy nothing and would couple this entry to the seeder. Every "
        "seeded email is `.invalid` anyway, which EmailStr rejects. Writes nothing but a security-"
        "event log line.",
    ),
    "PUT /api/workflow/config/{client_id}": BodySpec(
        key="PUT /api/workflow/config/{client_id}",
        build=_workflow_config,
        note="One scalar, and no list field. Sending `workflow_statuses` or `workflow_transitions` "
        "would REPLACE the seeded config with whatever was sent, and the response echoes what is "
        "stored -- so a short list would record a short shape. Omitting them leaves the fully "
        "populated row to be echoed. `ClosureTriggerEnum` is imported, not retyped, and the value "
        "matches what the seeder already stores, so the write is value-preserving.",
    ),
    "PUT /api/kpi-thresholds": BodySpec(
        key="PUT /api/kpi-thresholds",
        build=_kpi_thresholds,
        note="`fpy`, not `efficiency`, and never a null client_id. DELETE /api/kpi-thresholds/"
        "{client_id}/{kpi_key} resolves (client, efficiency); sharing that pair would couple two "
        "captures through one row. A null client_id writes a GLOBAL threshold row, which is "
        "precisely what GET /api/kpi-thresholds reads -- its golden `thresholds` is currently an "
        "empty key and would silently gain entries. `thresholds` must be non-empty or "
        "`updated_kpis` comes back empty and records no shape.",
    ),
    "POST /api/auth/change-password": BodySpec(
        key="POST /api/auth/change-password",
        build=_change_password,
        note="Re-sends the SAME password as both current and new, deliberately. The route "
        "verifies `current_password` against the principal's hash and then rehashes the new one, "
        "so a different value would leave the seeded credential unusable for any later capture "
        "that logs in. `DEMO_PASSWORD` is imported from the seeder, not pasted.\n\n"
        "This route answered 500 until the harness's mock principal gained a `password_hash`: it "
        "is a SimpleNamespace, and the route reads that attribute. The route handles a None hash "
        "and cannot handle a MISSING one, so the AttributeError surfaced as a 500 that the "
        "golden master recorded as the route's answer. Fixed at the mock, not deferred -- the "
        "500 was ours.",
    ),
    "POST /api/qr/generate/image": BodySpec(
        key="POST /api/qr/generate/image",
        build=_qr_image,
        note="`entity_id` is the seeded work order, resolved through the path registry rather "
        "than invented -- the encoder embeds it, and a made-up id would be a made-up contract. "
        "`QREntityType` is imported. Returns a PNG, so the entry is `<non-json>` -- a SUCCESS, "
        "not a gap. It "
        "was briefly deferred on the reasoning that 'the response is a stream so a body buys "
        "nothing', and that was wrong: without a body the route 422s, and a 422 is the harness's "
        "omission recorded as the route's answer. `<non-json>` is the honest entry and only a "
        "valid body reaches it.",
    ),
    "POST /api/workflow/work-orders/{work_order_id}/transition": BodySpec(
        key="POST /api/workflow/work-orders/{work_order_id}/transition",
        build=_work_order_transition,
        note="CLOSED, because the seeded work order this route resolves is COMPLETED and the "
        "state machine allows only CANCELLED or CLOSED from there -- IN_PROGRESS answers 400 and "
        "would record THAT as the shape. `WorkOrderStatus` is imported, not retyped. This is the "
        "route whose 500-after-commit was found by giving it a body in the first place; it is "
        "isolated, so the transition is rolled back with the snapshot.",
    ),
    "POST /api/floating-pool/simulation/optimize-allocation": BodySpec(
        key="POST /api/floating-pool/simulation/optimize-allocation",
        build=_optimize_allocation,
        note="A bare ARRAY -- the body param is an un-embedded `List[...]`. Pure simulation: it "
        "reads no row it did not receive and writes nothing, so the numbers are free inputs. "
        "KNOWN GAP: `allocation_suggestions` comes back empty against this seed (no employee "
        "carries is_floating_pool and FLOATING_POOL has no rows), so its inner shape is NOT "
        "captured. Recorded rather than papered over -- see test_write_capture.py.",
    ),
}
