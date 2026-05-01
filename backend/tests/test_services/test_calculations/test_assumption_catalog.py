"""Catalog allow-list and value-validation rules for the v1 assumption set."""

import pytest

from backend.services.calculations.assumption_catalog import (
    KNOWN_ASSUMPTION_NAMES,
    MAX_CATALOG_SIZE,
    V1_CATALOG,
    is_known,
    validate_value,
)


class TestCatalogShape:
    def test_size_within_v1_cap(self):
        # Spec § Configuration scope
        assert len(V1_CATALOG) <= MAX_CATALOG_SIZE

    def test_six_v1_names_present(self):
        # Ratified set per Phase 0 audit reconciliation
        for name in (
            "planned_production_time_basis",
            "ideal_cycle_time_source",
            "setup_treatment",
            "scrap_classification_rule",
            "otd_carrier_buffer_pct",
            "yield_baseline_source",
        ):
            assert is_known(name)
            assert "description" in V1_CATALOG[name]

    def test_known_names_match_dict_keys(self):
        assert KNOWN_ASSUMPTION_NAMES == frozenset(V1_CATALOG.keys())


class TestValueValidation:
    def test_unknown_name_rejected(self):
        with pytest.raises(ValueError, match="Unknown assumption_name"):
            validate_value("not_real", "x")

    def test_disallowed_value_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_value("ideal_cycle_time_source", "made_up_source")

    def test_allowed_value_accepted(self):
        validate_value("ideal_cycle_time_source", "engineering_standard")
        validate_value("setup_treatment", "count_as_downtime")
        validate_value("yield_baseline_source", "contractual")

    def test_otd_buffer_numeric_in_range(self):
        validate_value("otd_carrier_buffer_pct", 0)
        validate_value("otd_carrier_buffer_pct", 50.5)
        validate_value("otd_carrier_buffer_pct", 100)

    def test_otd_buffer_negative_rejected(self):
        with pytest.raises(ValueError, match="must be in"):
            validate_value("otd_carrier_buffer_pct", -1)

    def test_otd_buffer_over_100_rejected(self):
        with pytest.raises(ValueError, match="must be in"):
            validate_value("otd_carrier_buffer_pct", 200)

    def test_otd_buffer_non_numeric_rejected(self):
        with pytest.raises(ValueError, match="must be numeric"):
            validate_value("otd_carrier_buffer_pct", "ten")


class TestDependencySeeder:
    def test_seeder_idempotent(self, transactional_db):
        from backend.services.calculations.assumption_catalog import (
            CANONICAL_METRIC_DEPENDENCIES,
            seed_metric_dependencies,
        )

        first = seed_metric_dependencies(transactional_db)
        assert first == len(CANONICAL_METRIC_DEPENDENCIES)

        # Second call inserts nothing — idempotent
        second = seed_metric_dependencies(transactional_db)
        assert second == 0

    def test_canonical_assumption_names_are_in_catalog(self):
        from backend.services.calculations.assumption_catalog import (
            CANONICAL_METRIC_DEPENDENCIES,
            KNOWN_ASSUMPTION_NAMES,
        )

        for _, assumption_name, _ in CANONICAL_METRIC_DEPENDENCIES:
            assert assumption_name in KNOWN_ASSUMPTION_NAMES, (
                f"{assumption_name!r} appears in the dependency map but is not in V1_CATALOG"
            )
