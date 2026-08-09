"""Edit-plan schema and aggregate integrity tests."""

import copy
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from semanticvideo.schema import EditClip, EditPlan, RationalTime, SemanticVideoDocument


def _clip(*, clip_id: str = "edit.clip.0001", order: int = 0) -> EditClip:
    return EditClip(
        id=clip_id,
        source_segment_id="shot.1",
        source_range={
            "start": {"value": 1, "rate": 1},
            "duration": {"value": 2, "rate": 1},
        },
        order=order,
    )


def _plan(*clips: EditClip) -> EditPlan:
    return EditPlan(
        id="edit.plan.0001",
        name="Rough cut",
        generated_at=datetime.now(UTC),
        strategy="test",
        clips=clips,
    )


def test_edit_plan_requires_unique_contiguous_clips() -> None:
    with pytest.raises(ValidationError, match="at least one clip"):
        _plan()
    with pytest.raises(ValidationError, match="IDs must be unique"):
        _plan(_clip(), _clip(order=1))
    with pytest.raises(ValidationError, match="contiguous"):
        _plan(_clip(order=1))


def test_edit_plan_duration_is_exact_before_conversion() -> None:
    plan = _plan(_clip())

    assert plan.duration_seconds == 2
    assert plan.target_duration is None
    assert RationalTime(value=1, rate=2).seconds == 0.5


def test_document_validates_edit_clip_references(
    valid_document_data: dict[str, Any],
) -> None:
    valid_document_data["edit_plans"] = [_plan(_clip()).model_dump(mode="json")]
    assert SemanticVideoDocument.model_validate(valid_document_data).edit_plans

    missing = copy.deepcopy(valid_document_data)
    missing["edit_plans"][0]["clips"][0]["source_segment_id"] = "shot.missing"
    with pytest.raises(ValidationError, match="edit clip segment"):
        SemanticVideoDocument.model_validate(missing)

    outside = copy.deepcopy(valid_document_data)
    outside["edit_plans"][0]["clips"][0]["source_range"]["start"] = {
        "value": 4,
        "rate": 1,
    }
    with pytest.raises(ValidationError, match="inside its source segment"):
        SemanticVideoDocument.model_validate(outside)


def test_document_rejects_duplicate_edit_plan_ids(
    valid_document_data: dict[str, Any],
) -> None:
    encoded = _plan(_clip()).model_dump(mode="json")
    valid_document_data["edit_plans"] = [encoded, encoded]

    with pytest.raises(ValidationError, match="edit plan IDs must be unique"):
        SemanticVideoDocument.model_validate(valid_document_data)
