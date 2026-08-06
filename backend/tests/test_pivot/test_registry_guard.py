"""Structural guard pinning the 2026-08-06 ratio-of-sums ruling: every derived
measure MUST be composed of declared Sum/Count components. An average-of-
averages is unrepresentable — this test makes that permanent for any dataset
anyone registers, present or future."""

from backend.pivot.registry import DATASETS, Count, Ratio, Share, Sum


def test_registry_has_sql_path_datasets():
    assert "production" in DATASETS
    assert "downtime" in DATASETS


def test_every_ratio_and_share_references_declared_sum_or_count_components():
    for name, ds in DATASETS.items():
        for mname, m in ds.measures.items():
            if isinstance(m, Ratio):
                for ref in (m.numerator, m.denominator):
                    assert ref in ds.measures, f"{name}.{mname} references undeclared {ref!r}"
                    assert isinstance(ds.measures[ref], (Sum, Count)), (
                        f"{name}.{mname} component {ref!r} must be Sum/Count, "
                        f"got {type(ds.measures[ref]).__name__} — ratios compose "
                        f"summed components only (ratio-of-sums ruling)"
                    )
            if isinstance(m, Share):
                assert m.of in ds.measures, f"{name}.{mname} references undeclared {m.of!r}"
                assert isinstance(ds.measures[m.of], (Sum, Count)), (
                    f"{name}.{mname} component {m.of!r} must be Sum/Count, "
                    f"got {type(ds.measures[m.of]).__name__} — shares compose "
                    f"summed components only (ratio-of-sums ruling)"
                )


def test_every_dataset_declares_scope_and_date_axis():
    for name, ds in DATASETS.items():
        assert ds.date_column is not None, name
        assert ds.client_column is not None, name
        assert "client" in ds.group_bys, name
