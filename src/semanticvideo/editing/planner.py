"""Automatic, explainable rough-cut planning from structured editing signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction

from semanticvideo.errors import EditPlanningError
from semanticvideo.schema import (
    EditClip,
    EditorialAnnotation,
    EditPlan,
    RationalTime,
    Segment,
    SemanticVideoDocument,
    TimeRange,
)


@dataclass(frozen=True)
class _Candidate:
    segment: Segment
    source_range: TimeRange
    score: float
    duplicate_group: str | None
    reason: str


def create_edit_plan(
    document: SemanticVideoDocument,
    *,
    target_duration_seconds: float | None = None,
    minimum_clip_seconds: float = 0.5,
    preserve_source_order: bool = True,
    name: str = "Automatic rough cut",
) -> EditPlan:
    """Select usable, non-duplicate shots and satisfy an optional duration target."""

    if target_duration_seconds is not None and target_duration_seconds <= 0:
        raise ValueError("target duration must be greater than zero")
    if minimum_clip_seconds <= 0:
        raise ValueError("minimum clip duration must be greater than zero")

    candidates = _candidates(document)
    if not candidates:
        raise EditPlanningError("manifest contains no usable shot candidates")
    deduplicated = _best_per_duplicate_group(candidates)
    ranked = sorted(deduplicated, key=lambda item: (-item.score, item.segment.id))
    selected = _fit_duration(
        ranked,
        target_duration_seconds=target_duration_seconds,
        minimum_clip_seconds=minimum_clip_seconds,
    )
    if not selected:
        raise EditPlanningError("duration constraints removed every candidate")
    if preserve_source_order:
        selected.sort(key=lambda item: item.source_range.start_fraction)

    clips = tuple(
        EditClip(
            id=f"edit.clip.{index + 1:04d}",
            source_segment_id=item.segment.id,
            source_range=item.source_range,
            order=index,
            label=item.segment.label,
            reason=item.reason,
        )
        for index, item in enumerate(selected)
    )
    target = (
        _time(Fraction(str(target_duration_seconds)))
        if target_duration_seconds is not None
        else None
    )
    return EditPlan(
        id=f"edit.plan.{len(document.edit_plans) + 1:04d}",
        name=name,
        generated_at=datetime.now(UTC),
        strategy="rank-usable-deduplicate",
        target_duration=target,
        clips=clips,
        parameters={
            "minimum_clip_seconds": minimum_clip_seconds,
            "preserve_source_order": preserve_source_order,
        },
    )


def add_edit_plan(
    document: SemanticVideoDocument, plan: EditPlan
) -> SemanticVideoDocument:
    """Return a revalidated manifest containing the additional plan."""

    data = document.model_dump()
    data["edit_plans"] = [
        *(item.model_dump() for item in document.edit_plans),
        plan.model_dump(),
    ]
    return SemanticVideoDocument.model_validate(data)


def _candidates(document: SemanticVideoDocument) -> list[_Candidate]:
    annotations = {annotation.id: annotation for annotation in document.annotations}
    candidates: list[_Candidate] = []
    for segment in document.segments:
        if segment.kind != "shot":
            continue
        editorial = next(
            (
                annotation
                for annotation_id in segment.annotation_ids
                if isinstance(
                    (annotation := annotations.get(annotation_id)),
                    EditorialAnnotation,
                )
            ),
            None,
        )
        if editorial is not None and editorial.value.usable is False:
            continue
        source_range = (
            editorial.value.recommended_range
            if editorial is not None and editorial.value.recommended_range is not None
            else segment.time_range
        )
        interest = (
            editorial.value.interest_score
            if editorial is not None and editorial.value.interest_score is not None
            else 0.5
        )
        quality = (
            editorial.value.quality_score
            if editorial is not None and editorial.value.quality_score is not None
            else 0.5
        )
        score = 0.65 * interest + 0.35 * quality
        duplicate_group = (
            editorial.value.duplicate_group if editorial is not None else None
        )
        candidates.append(
            _Candidate(
                segment=segment,
                source_range=source_range,
                score=score,
                duplicate_group=duplicate_group,
                reason=f"interest={interest:.3f}; quality={quality:.3f}",
            )
        )
    return candidates


def _best_per_duplicate_group(candidates: list[_Candidate]) -> list[_Candidate]:
    best: dict[str, _Candidate] = {}
    unique: list[_Candidate] = []
    for item in candidates:
        if item.duplicate_group is None:
            unique.append(item)
            continue
        previous = best.get(item.duplicate_group)
        if previous is None or item.score > previous.score:
            best[item.duplicate_group] = item
    return [*unique, *best.values()]


def _fit_duration(
    candidates: list[_Candidate],
    *,
    target_duration_seconds: float | None,
    minimum_clip_seconds: float,
) -> list[_Candidate]:
    if target_duration_seconds is None:
        return list(candidates)
    remaining = Fraction(str(target_duration_seconds))
    minimum = Fraction(str(minimum_clip_seconds))
    selected: list[_Candidate] = []
    for item in candidates:
        if remaining < minimum:
            break
        duration = item.source_range.duration_fraction
        if duration <= remaining:
            selected.append(item)
            remaining -= duration
            continue
        selected.append(
            _Candidate(
                segment=item.segment,
                source_range=TimeRange(
                    start=item.source_range.start,
                    duration=_time(remaining),
                ),
                score=item.score,
                duplicate_group=item.duplicate_group,
                reason=f"{item.reason}; trimmed to target duration",
            )
        )
        remaining = Fraction(0)
    return selected


def _time(value: Fraction) -> RationalTime:
    return RationalTime(value=value.numerator, rate=value.denominator)
