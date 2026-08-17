"""Declarative per-client scenarios: who exists, and what story their data
tells. Pure configuration -- no generation logic, no database.

Four clients, each demonstrating a different failure mode, plus one healthy
control so the dashboards are not uniformly red (spec section 6).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrativeWindow:
    """A scripted episode. Months are negative offsets from the seed's as-of
    date: start_month=-8, end_month=-6 means "eight to six months ago"."""

    kind: str
    start_month: int
    end_month: int


@dataclass(frozen=True)
class ClientScenario:
    client_id: str
    name: str
    pay_model: str
    narrative: tuple


SCENARIOS = (
    ClientScenario(
        client_id="DEMO-PIECE",
        name="Piecework Apparel Co.",
        pay_model="piece",
        narrative=(NarrativeWindow(kind="supplier_quality_crisis", start_month=-8, end_month=-6),),
    ),
    ClientScenario(
        client_id="DEMO-HOURLY",
        name="Hourly Components Ltd.",
        pay_model="hourly",
        narrative=(NarrativeWindow(kind="equipment_reliability_decline", start_month=-5, end_month=-3),),
    ),
    ClientScenario(
        client_id="DEMO-HYBRID",
        name="Hybrid Assembly Group",
        pay_model="hybrid",
        narrative=(NarrativeWindow(kind="labor_disruption", start_month=-4, end_month=-2),),
    ),
    # The control. Every metric stays in specification for the full year, so a
    # demo can show a healthy client beside three troubled ones and the
    # thresholds read as informative rather than broken.
    ClientScenario(
        client_id="SAMPLE_REF",
        name="Reference Manufacturing",
        pay_model="hourly",
        narrative=(),
    ),
)
