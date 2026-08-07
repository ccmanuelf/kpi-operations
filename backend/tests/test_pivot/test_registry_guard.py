"""Structural guard pinning the 2026-08-06 ratio-of-sums ruling: every derived
measure MUST be composed of declared Sum/Count components. An average-of-
averages is unrepresentable — this test makes that permanent for any dataset
anyone registers, present or future."""

import pytest

from backend.pivot.registry import DATASETS, Component, Count, Dataset, Ratio, Share, Sum


def test_registry_has_sql_path_datasets():
    assert "production" in DATASETS
    assert "downtime" in DATASETS


def _validate_dataset(name: str, ds: Dataset) -> None:
    """Per-dataset structural check: every Ratio/Share measure must compose
    declared Sum/Count/Component components only -- an average-of-averages is
    unrepresentable regardless of which path (SQL or fetch hook) produced the
    sum. Extracted so both the full-registry sweep below and the negative
    tests (synthetic datasets never registered in DATASETS) share one
    assertion path -- the failure branches otherwise never fire."""
    for mname, m in ds.measures.items():
        if isinstance(m, Ratio):
            for ref in (m.numerator, m.denominator):
                assert ref in ds.measures, f"{name}.{mname} references undeclared {ref!r}"
                assert isinstance(ds.measures[ref], (Sum, Count, Component)), (
                    f"{name}.{mname} component {ref!r} must be Sum/Count/Component, "
                    f"got {type(ds.measures[ref]).__name__} — ratios compose "
                    f"summed components only (ratio-of-sums ruling)"
                )
        if isinstance(m, Share):
            assert m.of in ds.measures, f"{name}.{mname} references undeclared {m.of!r}"
            assert isinstance(ds.measures[m.of], (Sum, Count, Component)), (
                f"{name}.{mname} component {m.of!r} must be Sum/Count/Component, "
                f"got {type(ds.measures[m.of]).__name__} — shares compose "
                f"summed components only (ratio-of-sums ruling)"
            )


def test_every_ratio_and_share_references_declared_sum_or_count_components():
    # Component is the hook-path counterpart of Sum/Count (Task 5): a summed
    # value a fetch hook produces instead of a SQL expr. Ratio/Share still
    # must compose summed components only -- an average-of-averages is
    # unrepresentable regardless of which path produced the sum.
    for name, ds in DATASETS.items():
        _validate_dataset(name, ds)


def test_validate_dataset_rejects_ratio_referencing_undeclared_name():
    """Negative case: a Ratio naming a component that was never declared on
    the dataset at all. Uses a synthetic Dataset, never registered in
    DATASETS, so this fires only via the extracted helper -- the guard's
    failure branch has never actually run before this test."""
    bad = Dataset(
        name="bad-undeclared-ref",
        model=None,
        date_column=None,
        client_column=None,
        group_bys={},
        measures={
            "inspected": Sum(None),
            "fpy_pct": Ratio("inspected", "not_declared_anywhere"),
        },
    )
    with pytest.raises(AssertionError):
        _validate_dataset(bad.name, bad)


def test_validate_dataset_rejects_ratio_referencing_another_ratio():
    """Negative case: a Ratio referencing another Ratio (average-of-averages)
    instead of a declared Sum/Count/Component -- exactly the class the
    2026-08-06 ruling forbids."""
    bad = Dataset(
        name="bad-ratio-of-ratio",
        model=None,
        date_column=None,
        client_column=None,
        group_bys={},
        measures={
            "inspected": Sum(None),
            "passed": Sum(None),
            "fpy_pct": Ratio("passed", "inspected"),
            "double_fpy_pct": Ratio("fpy_pct", "inspected"),
        },
    )
    with pytest.raises(AssertionError):
        _validate_dataset(bad.name, bad)


def test_every_dataset_declares_scope_and_date_axis():
    for name, ds in DATASETS.items():
        assert ds.date_column is not None, name
        assert ds.client_column is not None, name
        assert "client" in ds.group_bys, name
