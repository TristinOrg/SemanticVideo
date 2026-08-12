"""Focused semantic enrichment tests."""

from typing import Any

from semanticvideo import SemanticVideoDocument
from semanticvideo.analysis.incremental import (
    SemanticSupplement,
    apply_supplement,
    capability_gaps,
)
from semanticvideo.schema import AnnotationStatus, RationalTime, TimeRange


def test_capability_gaps_respect_field_and_range_coverage(
    valid_document_data: dict[str, Any],
) -> None:
    valid_document_data["capabilities"] = [
        {
            "name": "actions",
            "status": "partial",
            "analyzed_fields": ["moments.actions"],
            "covered_ranges": [
                {
                    "start": {"value": 0, "rate": 1},
                    "duration": {"value": 5, "rate": 1},
                }
            ],
        }
    ]
    document = SemanticVideoDocument.model_validate(valid_document_data)
    covered = TimeRange(
        start=RationalTime(value=1, rate=1),
        duration=RationalTime(value=2, rate=1),
    )
    missing = TimeRange(
        start=RationalTime(value=6, rate=1),
        duration=RationalTime(value=2, rate=1),
    )
    assert capability_gaps(document, ("moments.actions",), time_range=covered) == ()
    assert capability_gaps(document, ("moments.actions",), time_range=missing) == (
        "moments.actions",
    )
    assert capability_gaps(document, ("ocr",)) == ("ocr",)


def test_supplement_preserves_human_claims_and_adds_moments(
    valid_document_data: dict[str, Any],
) -> None:
    document = SemanticVideoDocument.model_validate(valid_document_data)
    supplement = SemanticSupplement.model_validate(
        {
            "capabilities": [
                {
                    "name": "actions",
                    "status": "partial",
                    "analyzed_fields": ["moments.actions"],
                }
            ],
            "annotations": [
                document.annotations[0]
                .model_copy(update={"status": AnnotationStatus.MACHINE_GENERATED})
                .model_dump()
            ],
            "moments": [
                {
                    "id": "moment.1",
                    "time_range": {
                        "start": {"value": 1, "rate": 1},
                        "duration": {"value": 1, "rate": 1},
                    },
                    "summary": "Host adjusts hair",
                    "actions": ["adjusting hair"],
                    "parent_segment_id": "shot.1",
                }
            ],
        }
    )
    updated = apply_supplement(document, supplement)
    assert updated.annotations[0].status == "human_authored"
    assert updated.moments[0].actions == ("adjusting hair",)
    assert updated.analysis_runs[-1].capabilities == ("actions",)
