"""Typed, overlapping, time-aligned semantic annotations."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.media import Identifier
from semanticvideo.schema.provenance import Evidence, Provenance
from semanticvideo.schema.time import TimeRange


class AnnotationStatus(StrEnum):
    """Review state for probabilistic or human-authored observations."""

    MACHINE_GENERATED = "machine_generated"
    HUMAN_AUTHORED = "human_authored"
    HUMAN_REVIEWED = "human_reviewed"
    REJECTED = "rejected"


class SpatialRegion(SemanticModel):
    """Normalized top-left-origin rectangle within a video frame."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def require_region_inside_frame(self) -> "SpatialRegion":
        """Reject rectangles extending beyond normalized frame bounds."""

        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("spatial region must fit within the frame")
        return self


class SceneInfo(SemanticModel):
    """Perceptual and editorial description of a visual scene."""

    description: str = Field(min_length=1)
    environment: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    visible_text: tuple[str, ...] = ()
    location_hint: str | None = None
    shot_type: str | None = None
    camera_movement: str | None = None
    editorial_role: str | None = None


class QualityMetrics(SemanticModel):
    """Normalized quality signals; higher is better unless named ``level``."""

    sharpness: float | None = Field(default=None, ge=0, le=1)
    stability: float | None = Field(default=None, ge=0, le=1)
    exposure_quality: float | None = Field(default=None, ge=0, le=1)
    noise_level: float | None = Field(default=None, ge=0, le=1)
    audio_quality: float | None = Field(default=None, ge=0, le=1)
    usable: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_metric(self) -> "QualityMetrics":
        """Prevent empty quality annotations."""

        values = self.model_dump(exclude_none=True)
        if not values:
            raise ValueError("at least one quality metric is required")
        return self


class EventInfo(SemanticModel):
    """An action or occurrence involving zero or more entities."""

    type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    participant_entity_ids: tuple[Identifier, ...] = ()


class SubjectInfo(SemanticModel):
    """A visible or audible subject and its current action."""

    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    entity_id: Identifier | None = None
    action: str | None = None


class SpeechWord(SemanticModel):
    """A word with a range relative to the source media."""

    text: str = Field(min_length=1)
    time_range: TimeRange
    confidence: float | None = Field(default=None, ge=0, le=1)


class SpeechInfo(SemanticModel):
    """A timestamped utterance."""

    text: str = Field(min_length=1)
    language: str = Field(min_length=2)
    speaker_entity_id: Identifier | None = None
    words: tuple[SpeechWord, ...] = ()


class GeoPoint(SemanticModel):
    """A WGS84 coordinate."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_meters: float | None = None


class LocationInfo(SemanticModel):
    """A place observation with optional stable entity and coordinates."""

    name: str = Field(min_length=1)
    entity_id: Identifier | None = None
    point: GeoPoint | None = None


class AnnotationBase(SemanticModel):
    """Fields common to every semantic claim."""

    id: Identifier
    time_range: TimeRange
    stream_id: Identifier | None = None
    spatial_region: SpatialRegion | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: AnnotationStatus
    provenance: tuple[Provenance, ...]
    evidence: tuple[Evidence, ...] = ()
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_traceability(self) -> "AnnotationBase":
        """Machine output must be traceable to at least one generation run."""

        if self.status is AnnotationStatus.MACHINE_GENERATED and not self.provenance:
            raise ValueError("machine-generated annotation requires provenance")
        return self


class SceneAnnotation(AnnotationBase):
    kind: Literal["scene"] = "scene"
    value: SceneInfo


class QualityAnnotation(AnnotationBase):
    kind: Literal["quality"] = "quality"
    value: QualityMetrics


class EventAnnotation(AnnotationBase):
    kind: Literal["event"] = "event"
    value: EventInfo


class SubjectAnnotation(AnnotationBase):
    kind: Literal["subject"] = "subject"
    value: SubjectInfo


class SpeechAnnotation(AnnotationBase):
    kind: Literal["speech"] = "speech"
    value: SpeechInfo


class LocationAnnotation(AnnotationBase):
    kind: Literal["location"] = "location"
    value: LocationInfo


class CustomAnnotation(AnnotationBase):
    """Namespaced extension point for experimental annotation types."""

    kind: Literal["custom"] = "custom"
    namespace: str = Field(
        min_length=3,
        pattern=r"^[a-z][a-z0-9]*(\.[a-z0-9][a-z0-9-]*)+$",
    )
    type: str = Field(min_length=1)
    value: dict[str, JsonValue]


Annotation = Annotated[
    SceneAnnotation
    | QualityAnnotation
    | EventAnnotation
    | SubjectAnnotation
    | SpeechAnnotation
    | LocationAnnotation
    | CustomAnnotation,
    Field(discriminator="kind"),
]
