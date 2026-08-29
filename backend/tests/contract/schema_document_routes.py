"""Batch R5's scope exception for a response whose SHAPE IS data, not a
contract to model: `GET /api/v2/simulation/schema` returns
`SimulationConfig.model_json_schema()` (`routes/simulation_v2.py::
get_input_schema`) verbatim -- Pydantic's own JSON-Schema serialization of
that model, not a payload this route's own code composes.

229 keys -- six times the largest hand-modeled contract in this refactor --
because a JSON-Schema document's own vocabulary (`$defs`, `properties`,
`type`, `title`, `minimum`, `maximum`, `anyOf`, `required[]`, `enum[]`, ...)
IS the payload. A hand-written Pydantic model for it would either
(a) hardcode every current `SimulationConfig` field's schema shape, going
stale -- silently WRONG, not merely incomplete -- the instant
`SimulationConfig` gains, drops, or retypes a field, or (b) redeclare
Pydantic's own JSON-Schema meta-schema, which already exists and is not
this refactor's job to re-author. task-R5-brief.md HAZARD 3, plan spec
section 6: a documented exception beats an invented model.

Not folded into `response_scope.OUT_OF_SCOPE_ROUTES`: that registry's own
domain, per its module docstring, is "no JSON body at all" (a `Response`
subclass, or a 204 DELETE) -- structurally gated by
`classify_non_json_route`, which reads the endpoint's return annotation and
would classify `get_input_schema` (annotated `-> Any`, a real JSON dict) as
NEITHER category. This route's exemption is a different claim entirely: it
DOES have a JSON body, but that body's shape is Pydantic's own schema
output, not a payload to model by hand. Conflating the two registries would
blur what each is actually asserting.

`SCHEMA_DOCUMENT_ROUTES` is gated TWO-SIDED by `test_schema_document_routes.py`:
  * forward -- every declared route's CURRENT golden shape matches
    `shape_of(<model>.model_json_schema())` EXACTLY. If a future edit made
    the route return anything else (a curated subset, an envelope wrapping
    the schema, a hand-modeled contract that happens to still have 229
    keys, ...), this fails: the exemption's whole premise -- "this key set
    is Pydantic's own output, not ours to model" -- would no longer hold.
  * reverse -- the route is confirmed ABSENT from
    `routes_needing_a_response_model`'s remaining output below, i.e. this
    registry, not silent oversight, is why it never reappears in
    `ALLOWLIST`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type

from pydantic import BaseModel

from backend.simulation_v2.models import SimulationConfig


@dataclass(frozen=True)
class SchemaDocumentEntry:
    """`model` is the Pydantic model whose `.model_json_schema()` the route
    returns verbatim -- the thing `test_schema_document_routes.py` replays
    to prove the golden entry is really Pydantic's own output."""

    model: Type[BaseModel]


#: route -> the model whose JSON-Schema serialization it forwards as its
#: response body.
SCHEMA_DOCUMENT_ROUTES: Dict[str, SchemaDocumentEntry] = {
    "GET /api/v2/simulation/schema": SchemaDocumentEntry(model=SimulationConfig),
}


def routes_needing_a_response_model(app) -> list:
    """`response_scope.routes_needing_a_response_model`, further minus the
    routes declared in `SCHEMA_DOCUMENT_ROUTES` above. This is what
    `test_no_loose_response_models.py`'s ratchet actually calls from Batch
    R5 onward -- see that test for why the count it pins drops by one more
    than the number of routes this batch types."""
    from backend.tests.contract.response_scope import routes_needing_a_response_model as _base

    return [
        (method, path, kwargs)
        for method, path, kwargs in _base(app)
        if f"{method} {path}" not in SCHEMA_DOCUMENT_ROUTES
    ]
