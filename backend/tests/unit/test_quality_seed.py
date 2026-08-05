from app.domain.quality import QualityCategory, QualityProjectionSource, QualityResult
from app.integrations.quality_seed import deterministic_quality_projections


def test_quality_seed_covers_generic_decision_safety_and_reliability_cases() -> None:
    projections = deterministic_quality_projections()

    assert {item.case_public_id for item in projections} == {
        "CS-2046",
        "CS-2047",
        "CS-2048",
    }
    assert {item.category for item in projections} == set(QualityCategory)
    assert all(item.result is QualityResult.PASSED for item in projections)
    assert all(
        item.source is QualityProjectionSource.DETERMINISTIC_DEMO
        for item in projections
    )
    material = " ".join(
        f"{item.scenario} {item.expected_decision} {item.observed_decision}"
        for item in projections
    ).lower()
    assert {"airline", "passenger", "booking", "itinerary"}.isdisjoint(
        material.split()
    )
