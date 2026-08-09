"""Automatic edit-planning tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from semanticvideo.editing import add_edit_plan, create_edit_plan
from semanticvideo.errors import EditPlanningError
from semanticvideo.schema import SemanticVideoDocument


def _document() -> SemanticVideoDocument:
    generated = datetime.now(UTC).isoformat()
    segments = []
    annotations = []
    scores = ((0.2, 0.3, "duplicate.a"), (0.9, 0.8, "duplicate.a"), (0.7, 0.6, None))
    for index, (interest, quality, duplicate) in enumerate(scores, start=1):
        start = (index - 1) * 4
        annotation_id = f"annotation.editorial.{index}"
        segments.append(
            {
                "id": f"shot.{index}",
                "kind": "shot",
                "label": f"Shot {index}",
                "time_range": {
                    "start": {"value": start, "rate": 1},
                    "duration": {"value": 4, "rate": 1},
                },
                "annotation_ids": [annotation_id],
            }
        )
        annotations.append(
            {
                "id": annotation_id,
                "kind": "editorial",
                "time_range": segments[-1]["time_range"],
                "status": "human_authored",
                "provenance": [],
                "value": {
                    "interest_score": interest,
                    "quality_score": quality,
                    "usable": True,
                    "duplicate_group": duplicate,
                },
            }
        )
    return SemanticVideoDocument.model_validate(
        {
            "document_id": "document.test",
            "generated_at": generated,
            "media": {
                "id": "asset.test",
                "uri": str(Path("clip.mp4")),
                "duration": {"value": 12, "rate": 1},
                "streams": [
                    {
                        "kind": "video",
                        "id": "stream.video.0",
                        "index": 0,
                        "codec": "h264",
                        "width": 1920,
                        "height": 1080,
                    }
                ],
            },
            "segments": segments,
            "annotations": annotations,
        }
    )


def test_planner_deduplicates_and_restores_source_order() -> None:
    plan = create_edit_plan(_document())

    assert [clip.source_segment_id for clip in plan.clips] == ["shot.2", "shot.3"]
    assert plan.duration_seconds == 8
    assert "interest=" in (plan.clips[0].reason or "")


def test_planner_fits_target_and_can_keep_ranked_order() -> None:
    plan = create_edit_plan(
        _document(), target_duration_seconds=5, preserve_source_order=False
    )

    assert [clip.source_segment_id for clip in plan.clips] == ["shot.2", "shot.3"]
    assert [clip.source_range.duration.seconds for clip in plan.clips] == [4, 1]
    assert plan.duration_seconds == 5
    assert "trimmed" in (plan.clips[-1].reason or "")


def test_planner_rejects_invalid_constraints_and_empty_candidates() -> None:
    with pytest.raises(ValueError, match="target duration"):
        create_edit_plan(_document(), target_duration_seconds=0)
    with pytest.raises(ValueError, match="minimum clip"):
        create_edit_plan(_document(), minimum_clip_seconds=0)
    with pytest.raises(EditPlanningError, match="no usable"):
        empty = _document().model_copy(update={"segments": ()})
        create_edit_plan(empty)
    with pytest.raises(EditPlanningError, match="removed every"):
        create_edit_plan(
            _document(), target_duration_seconds=0.25, minimum_clip_seconds=0.5
        )


def test_add_edit_plan_revalidates_manifest() -> None:
    document = _document()
    updated = add_edit_plan(document, create_edit_plan(document))

    assert len(document.edit_plans) == 0
    assert len(updated.edit_plans) == 1
