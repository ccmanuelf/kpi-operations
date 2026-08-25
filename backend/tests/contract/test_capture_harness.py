def test_capture_records_nested_keys_not_values():
    """The harness records SHAPE. Two responses differing only in values must
    produce an identical record, or the golden master churns on every reseed."""
    from backend.tests.contract.capture import shape_of

    a = {"total": 5, "nested": {"x": 1.5}, "rows": [{"id": "A", "v": 2}]}
    b = {"total": 9, "nested": {"x": 9.9}, "rows": [{"id": "B", "v": 7}]}

    assert shape_of(a) == shape_of(b)
    assert shape_of(a) == ["nested.x", "rows[].id", "rows[].v", "total"]


def test_an_error_response_is_recorded_as_a_status_not_a_shape():
    """A 404's body has keys too. Recording them as the route's shape would
    freeze `{"detail"}` into the golden master and pass forever after."""
    from backend.tests.contract.capture import capture_all

    class _Stub:
        def request(self, method, path, **kw):
            class R:
                status_code = 404

                def json(self):
                    return {"detail": "Not Found"}

            return R()

    result = capture_all(_Stub(), [("GET", "/api/missing", {})])
    assert result == {"GET /api/missing": ["<status:404>"]}


def test_a_value_keyed_map_records_one_stable_entry_not_its_data():
    """/api/alerts/dashboard keys by_severity on alert data, so the SAME endpoint
    with UNCHANGED code recorded a different shape depending on which severities
    happened to be active -- and a severity with zero active alerts looked
    exactly like a dropped field. The harness must not manufacture the signal it
    exists to give."""
    from backend.tests.contract.capture import shape_of

    busy = {"total": 3, "by_severity": {"critical": 2, "high": 1}}
    quiet = {"total": 5, "by_severity": {"high": 5}}

    assert shape_of(busy) == ["by_severity.*", "total"]
    assert shape_of(quiet) == ["by_severity.*", "total"]


def test_map_fields_are_exactly_the_known_five():
    """MAP_FIELDS cannot be derived -- nothing distinguishes {"critical": 2} from
    an object with a "critical" attribute -- so it is listed, and pinned here so
    that adding one is a deliberate act rather than a quiet widening of what the
    golden master stops watching."""
    from backend.tests.contract.capture import MAP_FIELDS

    assert MAP_FIELDS == frozenset(
        {"by_severity", "by_category", "weekly_demand", "pieces_by_product", "fulfillment_by_product"}
    )
