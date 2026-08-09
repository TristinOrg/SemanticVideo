"""Structural media intervals such as shots, scenes, and chapters."""

from enum import StrEnum

from pydantic import model_validator

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.media import Identifier
from semanticvideo.schema.provenance import Provenance
from semanticvideo.schema.time import RationalTime, TimeRange


class SegmentKind(StrEnum):
    """Structural levels that may overlap or nest."""

    SHOT = "shot"
    SCENE = "scene"
    SEQUENCE = "sequence"
    CHAPTER = "chapter"
    CUSTOM = "custom"


class Segment(SemanticModel):
    """A structural range, separate from semantic observations."""

    id: Identifier
    kind: SegmentKind
    time_range: TimeRange
    label: str | None = None
    representative_times: tuple[RationalTime, ...] = ()
    annotation_ids: tuple[Identifier, ...] = ()
    parent_id: Identifier | None = None
    provenance: tuple[Provenance, ...] = ()

    @model_validator(mode="after")
    def representatives_must_be_inside_range(self) -> "Segment":
        """Representative frames must point inside their structural segment."""

        for timestamp in self.representative_times:
            if not (
                self.time_range.start_fraction
                <= timestamp.fraction
                < self.time_range.end_fraction
            ):
                raise ValueError("representative time must be inside segment")
        return self
