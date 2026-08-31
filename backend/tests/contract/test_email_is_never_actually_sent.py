"""No capture may reach an SMTP server.

`POST /api/reports/email-config/test` and `POST /api/reports/send-manual` each
do `from backend.services.email_service import EmailService` INSIDE the handler
and call it. Absent credentials do NOT make that safe: measured from
configuration, SMTP_USER / SMTP_PASSWORD / SENDGRID_API_KEY are all empty while
SMTP_HOST defaults to smtp.gmail.com, and the service's
`if self.smtp_user and self.smtp_password` merely SKIPS the login -- it still
connects and tries to send unauthenticated. Nothing would be delivered; a CI
runner would reach the network and wait.

The routes' own "email service not configured" branch is reached on ImportError
alone, never on missing credentials, so it does not save us either.

The harness therefore substitutes `StubbedEmailService`. Asserting that the
substitution HAPPENED is not enough -- a future code path could construct a
transport some other way and nothing here would notice until CI hung. So the
strongest test below breaks `smtplib.SMTP` itself and requires the routes to
keep working.
"""

from typing import Dict, List

import pytest

from backend.tests.contract.body_specs import BODY_REGISTRY
from backend.tests.contract.capture import StubbedEmailService
from backend.tests.contract.conftest import _Harness
from backend.tests.contract.param_resolution import Resolver

EMAIL_ROUTES = ("POST /api/reports/email-config/test", "POST /api/reports/send-manual")


@pytest.fixture(scope="module")
def calls_made_during_capture(captured_shapes: Dict[str, List[str]]) -> List[str]:
    """A SNAPSHOT of the stub's call log, taken right after the capture.

    `StubbedEmailService.calls` is class-level and the harness resets it once
    per module. Asserting against the live list would make the check
    order-dependent: the SMTP test below drives both routes too, so if it ran
    first its calls would satisfy an assertion meant to be about the capture.
    Snapshotting binds the evidence to the moment that matters.
    """
    return list(StubbedEmailService.calls)


def test_the_capture_reached_the_stub_and_not_the_real_service(
    captured_shapes: Dict[str, List[str]],
    calls_made_during_capture: List[str],
) -> None:
    """Both routes answered, and the stub recorded both calls.

    Asserting the shapes alone would pass if the real service happened to
    return the same keys; asserting the calls alone would pass if the routes
    never ran. Together they say the stub is what answered.
    """
    for route in EMAIL_ROUTES:
        shape = captured_shapes.get(route)
        assert shape and not str(shape[0]).startswith("<"), f"{route} did not answer: {shape}"

    assert "send_test_email" in calls_made_during_capture, calls_made_during_capture
    assert "send_kpi_report" in calls_made_during_capture, calls_made_during_capture


def test_the_routes_still_answer_with_every_transport_made_unusable(harness: _Harness) -> None:
    """The real guarantee: no transport is reached at all.

    Breaking `smtplib.SMTP` alone would prove less than it looks. `EmailService`
    has TWO paths -- SMTP, and SendGrid over HTTPS when SENDGRID_API_KEY is set
    (`use_sendgrid` in its constructor) -- so an SMTP-only patch would pass on a
    CI runner that happened to have that key configured, while the capture
    posted to SendGrid.

    So EVERY transport it can construct is broken here: `smtplib.SMTP`,
    `smtplib.SMTP_SSL`, and the SendGrid client when that package is installed.

    Not `EmailService.__init__`, which would be the obvious single point --
    the harness has already replaced that NAME with the stub, so breaking it
    breaks the stub and the test proves nothing. (Tried; it failed for exactly
    that reason.) The transports are the honest instrument: they are what a
    real send has to reach, whichever class builds it.

    If the stub is doing its job, none of this changes anything.
    """
    import smtplib

    resolver = Resolver(engine=harness.engine)

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("the capture tried to reach a mail transport")

    # `setattr`, not a direct assignment: mypy rejects rebinding a class name,
    # and the point here is to break the transport for the duration, not to
    # convince the type checker that smtplib has a different shape.
    broken: list = []
    for module_name, attribute in (("smtplib", "SMTP"), ("smtplib", "SMTP_SSL")):
        module = smtplib
        broken.append((module, attribute, getattr(module, attribute)))
        setattr(module, attribute, _explode)
    try:
        import sendgrid  # noqa: F401  -- optional dependency

        broken.append((sendgrid, "SendGridAPIClient", sendgrid.SendGridAPIClient))
        setattr(sendgrid, "SendGridAPIClient", _explode)
    except ImportError:
        pass

    try:
        for route in EMAIL_ROUTES:
            harness.restore()
            path = route.split(" ", 1)[1]
            body = BODY_REGISTRY[route].build(resolver)
            response = harness.client.post(path, json=body)
            assert response.status_code == 200, f"{route} -> {response.status_code} {response.text[:160]}"
    finally:
        for module, attribute, original in broken:
            setattr(module, attribute, original)


def test_no_recipient_is_a_real_address(harness: _Harness) -> None:
    """Belt and braces. If the stub were ever removed, the addresses these
    bodies carry are the last thing standing between a capture and somebody's
    inbox -- so they must be literals under a reserved domain, never a seeded
    user's address.
    """
    resolver = Resolver(engine=harness.engine)

    addresses = []
    test_body = BODY_REGISTRY["POST /api/reports/email-config/test"].build(resolver)
    addresses.append(test_body["email"])
    addresses.extend(BODY_REGISTRY["POST /api/reports/send-manual"].build(resolver)["recipient_emails"])

    assert addresses
    for address in addresses:
        assert address.endswith("@example.com"), (
            f"{address!r} is not under a reserved documentation domain -- RFC 2606 keeps "
            "example.com undeliverable, which any other domain does not guarantee"
        )


@pytest.mark.parametrize("route", EMAIL_ROUTES)
def test_each_email_route_has_a_body_spec(route: str) -> None:
    """They were deferred for months on the grounds that they send real email.
    That was true and is now handled; this stops them being quietly dropped
    back out of the registry, which would restore the `<status:422>` they used
    to record."""
    assert route in BODY_REGISTRY
