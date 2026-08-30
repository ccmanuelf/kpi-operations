"""Response contract for `GET /api/onboarding/status`.

The route was `-> Any` and had no declared contract. It also spent time
recorded as `<status:400>` in the golden master -- not the route's answer but
the harness's, which never sent the `client_id` the handler demands in its own
body (see `EFFECTIVELY_REQUIRED_QUERY_PARAMS`). Modelled once the capture
started reaching a real response.
"""

from pydantic import BaseModel


class OnboardingSteps(BaseModel):
    """Five fixed setup milestones, each a `count() > 0` on one table.

    The keys are the milestones themselves, not data, so this is a closed
    model rather than a `Dict[str, bool]`: adding a sixth step is a contract
    change and should fail the golden master, not slip through as another
    dictionary entry.
    """

    shifts_configured: bool
    products_added: bool
    work_orders_created: bool
    production_data_entered: bool
    capacity_plan_created: bool


class OnboardingStatusResponse(BaseModel):
    """`routes/onboarding.py::get_onboarding_status`.

    `completed_count` is `sum(1 for v in steps.values() if v)` and
    `total_steps` is `len(steps)`, so both are ints bounded by the five
    milestones above. `all_complete` is `all(steps.values())`.
    """

    steps: OnboardingSteps
    completed_count: int
    total_steps: int
    all_complete: bool
