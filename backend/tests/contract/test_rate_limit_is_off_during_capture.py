"""The capture must not be throttled by the application's own rate limiter.

Five auth routes carry `@limiter.limit(RateLimitConfig.AUTH_LIMIT)` -- 10 per
minute -- on register, login, forgot-password, reset-password and
change-password. A capture that trips it records `<status:429>` as the route's
contract: the harness's throttling mistaken for the route's answer, the same
class of defect as the `<status:400>` that sat on `/api/onboarding/status`.

The subtlety, and the reason this file exists rather than a one-line assert:
`disable_rate_limit` in tests/conftest.py IS autouse, but it is FUNCTION-scoped
while `harness` and `captured_shapes` are MODULE-scoped, and pytest builds
higher-scoped fixtures first. So the limiter is live for the capture and
disabled by the time any test body runs. Measured before the fix --

    at module-fixture time : enabled=True, 14 requests -> 10x 200 then 4x 429
    inside a test body     : enabled=False, 14 requests -> 14x 200

-- which means an assertion written in the obvious place proves nothing. Both
moments are checked below, and they must disagree in the right direction.
"""

import pytest

from backend.tests.contract.conftest import _Harness

AUTH_ROUTE = "/api/auth/forgot-password"
OVER_THE_LIMIT = 14


@pytest.fixture(scope="module")
def limiter_state_at_capture_time(harness: _Harness) -> dict:
    """MODULE-scoped on purpose: this is the scope `captured_shapes` runs at,
    so it observes exactly what the real capture observes."""
    from backend.middleware.rate_limit import limiter

    codes = []
    for index in range(OVER_THE_LIMIT):
        response = harness.client.post(AUTH_ROUTE, json={"email": f"capture-probe-{index}@example.com"})
        codes.append(response.status_code)

    return {"enabled": limiter.enabled, "codes": codes}


def test_the_limiter_is_disabled_at_the_moment_the_capture_runs(limiter_state_at_capture_time: dict) -> None:
    assert limiter_state_at_capture_time["enabled"] is False, (
        "the rate limiter is live at module-fixture scope, which is when the capture runs -- "
        "auth routes will start recording <status:429> as their contract"
    )


def test_more_requests_than_the_limit_all_succeed(limiter_state_at_capture_time: dict) -> None:
    """The behavioural half. `limiter.enabled is False` is the mechanism; this
    is the consequence, and it is what actually protects the golden master.

    `OVER_THE_LIMIT` exceeds AUTH_LIMIT (10/minute) deliberately, so a
    re-enabled limiter shows up as 429s here rather than as a mysterious
    entry in the golden master weeks later.
    """
    codes = limiter_state_at_capture_time["codes"]

    assert len(codes) > 10, "probe no longer exceeds AUTH_LIMIT, so it proves nothing"
    assert 429 not in codes, f"rate limited during capture: {codes}"
    assert set(codes) == {200}, codes


def test_the_global_fixture_alone_would_not_have_covered_this() -> None:
    """Pins the reason the harness disables the limiter itself.

    If `disable_rate_limit` ever becomes session- or module-scoped, this
    harness-local handling becomes redundant and can go -- but silently
    keeping both is not the failure mode worth guarding. The failure mode is
    someone deleting the harness-local disable because "conftest already does
    it", which is exactly the reasoning that left the limiter live.
    """
    from backend.tests import conftest as root_conftest

    fixture = root_conftest.disable_rate_limit
    marker = getattr(fixture, "_fixture_function_marker", None)

    assert marker is not None, "disable_rate_limit is no longer a pytest fixture"
    assert marker.autouse is True, "disable_rate_limit stopped being autouse"
    assert marker.scope == "function", (
        f"disable_rate_limit is now {marker.scope}-scoped; if it covers module-scoped capture "
        "fixtures the harness-local disable in contract/conftest.py may be redundant -- verify "
        "by measuring at module-fixture time, not in a test body"
    )
