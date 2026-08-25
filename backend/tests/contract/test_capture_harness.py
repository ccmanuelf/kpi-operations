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
