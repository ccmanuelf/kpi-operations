"""Records the SHAPE of an API response — its key paths, never its values.

Values change on every reseed; shapes do not. A value-sensitive record would
churn constantly and be ignored within a week.
"""

from typing import Any, List


def shape_of(payload: Any, prefix: str = "") -> List[str]:
    """Sorted dotted key paths. A list contributes `name[]` and recurses into
    its FIRST element only — homogeneous collections are the norm here, and
    walking every row would make the record depend on how much data was seeded.
    """
    keys: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            child = shape_of(value, path)
            keys.extend(child if child else [path])
    elif isinstance(payload, list):
        if payload:
            child = shape_of(payload[0], f"{prefix}[]")
            keys.extend(child if child else [f"{prefix}[]"])
    return sorted(set(keys))


def capture_all(client, routes) -> dict:
    """Exercise every route and record its shape.

    `routes` is a list of (method, path, kwargs) prepared by the caller, which
    owns id resolution — the harness deliberately does not guess ids, because a
    wrong id yields a 404 whose shape is recorded as if it were the real answer.
    """
    captured = {}
    for method, path, kwargs in routes:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            captured[f"{method} {path}"] = [f"<status:{response.status_code}>"]
            continue
        try:
            captured[f"{method} {path}"] = shape_of(response.json())
        except ValueError:
            captured[f"{method} {path}"] = ["<non-json>"]
    return captured
