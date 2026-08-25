# Response-model refactor — design

**Status:** approved in brainstorm 2026-08-25, ready for an implementation plan
**Supersedes nothing.** Follow-on from the MariaDB Decimal work (#219, #220, #223, #225).

## 1. Goal

Give every `/api` route a response model that declares the fields it actually returns, so
that the Decimal-as-string class is closed *structurally* rather than by coercion at each
call site — and so the OpenAPI document stops lying about what the API returns.

Non-goals: changing any endpoint's behaviour or field set; performance work; touching the
frontend beyond verifying it still receives what it reads; the `BREAK_TIME` demo-coverage
gap (tracked separately in the S1c spec §2.1).

## 2. Why this, and why now

Five PRs closed the Decimal class by coercing values at the point they enter a response
dict, backed by three AST guards. That works, and it is the wrong shape of fix:

- It requires a guard per *syntactic shape*. Three shapes have already been found the hard
  way — direct dict values (#220), values bound to a local first (#223), and a raw
  `Decimal("0")` literal in an empty-data branch (#225). Each was discovered in production,
  not by the guard written for the previous one.
- The guards are static and narrow by necessity. A wider rule was tried during #220 and
  produced 27 false positives on legitimate internal `Decimal` arithmetic.

The actual mechanism, established in #225 and worth restating because it was described
wrongly for several days:

```
1. MariaDB SUM()/AVG() yields DECIMAL where SQLite yields int/float
2. the route is annotated `-> Dict[str, Any]`, so FastAPI serialises through PYDANTIC,
   not through jsonable_encoder
3. Pydantic v2 renders Decimal as a JSON *string* under `Any`; float does not

   TypeAdapter(Dict[str, Any]).dump_json({"d": Decimal("0"), "f": 0.0})
     -> {"d":"0","f":0.0}
```

`jsonable_encoder(Decimal("0"))` returns the **number** `0` — verified locally and inside
the production container, so this is not version skew. The class therefore requires **both**
MariaDB **and** a route without a precise response model. Declare the field as `float` and
Pydantic coerces the Decimal on the way out. No guard, no call-site discipline, no shapes to
enumerate.

## 3. Measured scope

460 `/api` routes. **160 are loosely typed** (`None` / `Any` / `dict` / `list` / `list[dict]`).
The leaking endpoints were not un-modelled — they had models of `Any` and `dict`, which is
why "add response models" understates the work.

By method: GET 108, DELETE 27, POST 23, PUT 2.

By capture feasibility — this is the constraint that shapes Phase 0:

| | count | golden-master capture |
|---|---:|---|
| paramless GET | 78 | direct |
| GET with path params | 30 | needs an id resolved from seeded rows |
| POST / PUT / PATCH / DELETE | 52 | **requires performing writes** |

Across 43 areas, heavily skewed: `/api/kpi` 24, `/api/workflow` 13, `/api/reports` 11,
`/api/quality` 9, `/api/export` 9, `/api/jobs` 8, `/api/floating-pool` 7, `/api/attendance` 7,
then a long tail of 22 areas holding a single route each.

## 4. Decisions

**D1 — exact models, not permissive ones.** Declare every field an endpoint really
returns, **with its correct type** — `float` where a Decimal arrives, not `Any`. The
field names alone would tidy the contract without closing the Decimal class; it is the
declared type that makes Pydantic coerce on the way out.
A permissive model (`extra="allow"`) would close the Decimal class just as well while leaving
the contract vague and OpenAPI imprecise, which forfeits the main reason to do this at all.

**D2 — all 160, not just the ~48 numeric-risk routes.** The numeric routes are the only ones
that leak today, but the vague contract is the underlying defect and it is worth paying off
once. Sequenced by area so it can be stopped at any boundary with the work so far intact.

**D3 — both safety nets: golden-master key sets AND a frontend usage audit.** They fail
differently. A golden master catches a field that disappears; a frontend audit catches a
field that was already never sent but is read anyway. Neither alone is sufficient.

**D4 — capture against a disposable seeded database, never against the VM.** 52 of the 160
are mutations. Capturing them means issuing real writes, which must not happen against
production. The hermetic pattern already used for the local e2e run applies: temp file →
`alembic upgrade head` → seed → exercise → discard. This also makes the capture repeatable
and independent of whatever state the VM happens to hold.

**D5 — `extra="forbid"` during development, relaxed before merge.** Pydantic's default is to
drop undeclared keys silently, which is exactly the failure this refactor must not cause.
Building each model with `extra="forbid"` turns "I missed a field" into a loud error at
capture time. The setting is removed before the model ships, because a strict model in
production converts a benign extra key into a 500.

**D6 — a ratchet guard with a shrinking allowlist.** A test asserting no `/api` route has a
loose response model, seeded with the 160 as an explicit allowlist that shrinks to empty.
This prevents backsliding while the work is in flight and makes progress a number rather
than a feeling.

## 5. Phases

### Phase 0 — tooling (no route changes)

Nothing is safe to convert before the net exists.

1. **Capture harness.** Boots a disposable seeded database, walks every `/api` route,
   resolves path params from seeded rows, issues the appropriate method (writes included),
   and records `{method path → sorted key set}` — recursively, so nested objects are covered.
   Output committed as a golden master.
2. **Frontend field extractor.** For each endpoint, the fields the UI actually reads —
   from `frontend/src/services/api/*.ts` and the stores/composables that consume them.
   Produces `{endpoint → fields read}`.
3. **Comparison assert.** Re-runs the capture and diffs against the committed golden
   master. A dropped key fails loudly and names the route and the key.

   **It compares KEY SETS, deliberately not value types.** Changing a type is the
   point of the refactor -- `"4"` becoming `4` is success, not regression -- so a
   type-comparing golden master would fail on every intended change and be switched
   off within a day. Type correctness is proven by the live Decimal sweep instead
   (section 7). Whoever builds this must not "improve" it into comparing types.

Phase 0's own exit criterion: run it against unmodified `main` and confirm it reports zero
differences. A net that cannot detect "no change" cannot be trusted to detect a change.

### Phase 1 — models, by area, densest first

`/api/kpi` (24 routes) as the pilot, because it is the highest-traffic area and holds the
routes that actually leaked.

**The pilot's real purpose is measurement.** If a route costs 20 minutes, the remaining 136
are a week; if it costs 5, they are two days. That number decides whether D2 survives
contact — and it is far better learned at route 24 than at route 100. The plan must include
an explicit reassessment point at the end of the pilot, with continuing as one option and
narrowing to the ~48 numeric-risk routes as another.

Then by descending density: `/api/workflow` 13, `/api/reports` 11, `/api/quality` 9,
`/api/export` 9, `/api/jobs` 8, `/api/floating-pool` 7, `/api/attendance` 7, `/api/work-orders`
6, then the tail.

Per route: declare the model from the captured key set, run the comparison assert, check the
frontend extractor for fields read but not declared, commit.

### Phase 2 — the ratchet

Land the guard early (during Phase 1, not after) with the full allowlist, so every subsequent
PR shrinks it visibly and no new loose route can be added meanwhile.

## 6. Risks

**The 52 mutation routes are the risky third.** Their responses carry server-generated
fields — ids, timestamps, computed status — and their shape can vary with the request. Exact
models there need more per-route judgement than the GETs, and the capture must exercise
enough variants to see the whole field set. If a mutation route proves genuinely variable,
recording it as a deliberate exception in the ratchet allowlist is preferable to inventing a
model that is wrong.

**Dynamic frontend reads defeat the extractor.** Code like `row[key]` where `key` is computed
will not appear in a static grep. The golden master is the backstop for exactly this case:
it does not care why a field is read, only that it is still sent.

**DELETE routes are probably trivial and should be checked early.** 27 of the 160 are
DELETEs, which usually return a status message or 204. If they are as uniform as expected,
they are one shared model and the effective route count drops by roughly a sixth. Worth
confirming in Phase 0 rather than assuming.

**Nested Decimals.** `/api/floating-pool/simulation/insights` returns values nested three
levels deep. Models must cover nested structures, not just top-level keys, or the class
survives in the interior.

**Two endpoints must NOT be "fixed".** `/api/metrics/results` and
`/api/floating-pool/simulation/insights` return numeric-looking strings **deliberately** —
a documented str-of-Decimal idiom (`standard_value: str` is declared on the model) and
explicit `str()` calls at `simulation.py:338` and `:423`. Their models must preserve `str`.
Verified 2026-08-24; the tell is the preserved trailing zero in `'13.60'`, which `str(Decimal)`
produces and a leak would not.

## 7. Verification

- Phase 0 harness reports zero differences against unmodified `main`.
- After each area: comparison assert green, backend suite green, `mypy` clean.
- After each area: the live sweep against the VM still reports zero real Decimal leaks.
- The e2e suite (186 specs) green before each merge — it is the only end-to-end proof that
  the frontend still receives what it reads.
- The ratchet allowlist strictly shrinks, and is empty at completion.

## 8. Open question for the plan

Whether to convert `/api/export` and `/api/reports` (20 routes between them) at all. They
return files and generation status rather than data, so they carry no Decimal risk and their
"contract" is largely a download. Cheap to include, but the benefit is close to zero. Decide
at the Phase 1 reassessment rather than now.
