"""Concrete, reviewable edit decisions that can be rendered deterministically."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction

from pydantic import Field, JsonValue, model_validator

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.media import Identifier
from semanticvideo.schema.time import RationalTime, TimeRange


class EditClip(SemanticModel):
    """One source interval placed in timeline order."""

    id: Identifier
    source_segment_id: Identifier
    source_range: TimeRange
    order: int = Field(ge=0)
    label: str | None = None
    reason: str | None = None


class EditPlan(SemanticModel):
    """A deterministic list of source clips stored in the semantic manifest."""

    id: Identifier
    name: str = Field(min_length=1)
    generated_at: datetime
    strategy: str = Field(min_length=1)
    target_duration: RationalTime | None = None
    clips: tuple[EditClip, ...]
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_clip_identity_and_order(self) -> EditPlan:
        if not self.clips:
            raise ValueError("edit plan requires at least one clip")
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("edit clip IDs must be unique within a plan")
        orders = [clip.order for clip in self.clips]
        if orders != list(range(len(self.clips))):
            raise ValueError("edit clip order must be contiguous from zero")
        return self

    @property
    def duration_seconds(self) -> float:
        duration = sum(
            (clip.source_range.duration_fraction for clip in self.clips),
            start=Fraction(0),
        )
        return float(duration)
