"""SemanticVideo document aggregate and integrity validation."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.annotation import (
    Annotation,
    EditorialAnnotation,
    EventAnnotation,
    LocationAnnotation,
    SpeechAnnotation,
    SubjectAnnotation,
)
from semanticvideo.schema.edit import EditPlan
from semanticvideo.schema.entity import Entity
from semanticvideo.schema.media import Identifier, MediaInfo
from semanticvideo.schema.segment import Segment
from semanticvideo.schema.time import TimeRange


class Artifact(SemanticModel):
    """Reference to a derived file kept outside the human-readable manifest."""

    id: Identifier
    type: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    media_type: str | None = None
    checksum: str | None = None
    time_range: "TimeRange | None" = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class SummaryLevel(StrEnum):
    """Granularity of a human- and machine-readable semantic summary."""

    VIDEO = "video"
    CHAPTER = "chapter"
    SHOT = "shot"


class SemanticSummary(SemanticModel):
    """A hierarchical summary that links back to precise source ranges."""

    id: Identifier
    level: SummaryLevel
    text: str = Field(min_length=1)
    time_range: "TimeRange"
    child_ids: tuple[Identifier, ...] = ()
    language: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class SemanticMoment(SemanticModel):
    """A meaningful change or occurrence inside a broader structural shot."""

    id: Identifier
    time_range: "TimeRange"
    summary: str = Field(min_length=1)
    subjects: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    visible_text: tuple[str, ...] = ()
    parent_segment_id: Identifier | None = None
    annotation_ids: tuple[Identifier, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)


class AnalysisRun(SemanticModel):
    """One resumable analysis execution and the outputs it produced."""

    id: Identifier
    analyzer: str = Field(min_length=1)
    analyzer_version: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime | None = None
    capabilities: tuple[str, ...] = ()
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    annotation_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def completion_must_follow_start(self) -> "AnalysisRun":
        """Reject impossible run timestamps."""

        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("analysis completion cannot precede its start")
        return self


class CapabilityStatus(StrEnum):
    """Whether an analysis capability produced usable information."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    OMITTED = "omitted"
    FAILED = "failed"


class CapabilityReport(SemanticModel):
    """Explicitly distinguish absent, failed, and intentionally omitted data."""

    name: str = Field(min_length=1)
    status: CapabilityStatus
    required: bool = False
    provider: str | None = None
    message: str | None = None
    analyzed_fields: tuple[str, ...] = ()
    covered_ranges: tuple["TimeRange", ...] = ()


class SegmentRelationType(StrEnum):
    """Editing-relevant relationships between structural segments."""

    SAME_SCENE = "same_scene"
    CONTINUATION = "continuation"
    DUPLICATE = "duplicate"
    ALTERNATIVE = "alternative"
    CONTRAST = "contrast"
    SUPPORTS = "supports"


class SegmentRelation(SemanticModel):
    """A directional or symmetric relationship between two segments."""

    id: Identifier
    type: SegmentRelationType
    source_segment_id: Identifier
    target_segment_id: Identifier
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasons: tuple[str, ...] = ()


class SemanticVideoDocument(SemanticModel):
    """Root object for one source media asset's semantic sidecar."""

    schema_version: Literal["0.1.0", "0.2.0", "0.3.0"] = "0.3.0"
    document_id: Identifier
    generated_at: datetime
    media: MediaInfo
    entities: tuple[Entity, ...] = ()
    segments: tuple[Segment, ...] = ()
    annotations: tuple[Annotation, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    analysis_runs: tuple[AnalysisRun, ...] = ()
    edit_plans: tuple[EditPlan, ...] = ()
    capabilities: tuple[CapabilityReport, ...] = ()
    relations: tuple[SegmentRelation, ...] = ()
    moments: tuple[SemanticMoment, ...] = ()
    summaries: tuple[SemanticSummary, ...] = ()
    extensions: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_integrity(self) -> "SemanticVideoDocument":
        """Validate IDs, references, parent links, and media time bounds."""

        self._require_unique_ids("entity", [item.id for item in self.entities])
        self._require_unique_ids("segment", [item.id for item in self.segments])
        self._require_unique_ids("annotation", [item.id for item in self.annotations])
        self._require_unique_ids("artifact", [item.id for item in self.artifacts])
        self._require_unique_ids(
            "analysis run", [item.id for item in self.analysis_runs]
        )
        self._require_unique_ids("edit plan", [item.id for item in self.edit_plans])
        self._require_unique_ids("relation", [item.id for item in self.relations])
        self._require_unique_ids("moment", [item.id for item in self.moments])
        self._require_unique_ids("summary", [item.id for item in self.summaries])
        self._require_unique_ids(
            "capability", [item.name for item in self.capabilities]
        )

        entity_ids = {item.id for item in self.entities}
        segment_ids = {item.id for item in self.segments}
        annotation_ids = {item.id for item in self.annotations}
        artifact_ids = {item.id for item in self.artifacts}
        stream_ids = {item.id for item in self.media.streams}
        media_end = self.media.duration.fraction

        for segment in self.segments:
            if segment.time_range.end_fraction > media_end:
                raise ValueError(f"segment {segment.id!r} exceeds media duration")
            if segment.parent_id is not None:
                self._require_reference(
                    "segment parent", segment.parent_id, segment_ids
                )
                if segment.parent_id == segment.id:
                    raise ValueError("segment cannot be its own parent")
            for annotation_id in segment.annotation_ids:
                self._require_reference(
                    "segment annotation", annotation_id, annotation_ids
                )
            for record in segment.provenance:
                self._validate_evidence_artifacts(record.evidence, artifact_ids)

        for annotation in self.annotations:
            if annotation.time_range.end_fraction > media_end:
                raise ValueError(f"annotation {annotation.id!r} exceeds media duration")
            if annotation.stream_id is not None:
                self._require_reference(
                    "annotation stream", annotation.stream_id, stream_ids
                )
            self._validate_evidence_artifacts(annotation.evidence, artifact_ids)
            for record in annotation.provenance:
                self._validate_evidence_artifacts(record.evidence, artifact_ids)

            if isinstance(annotation, EventAnnotation):
                for entity_id in annotation.value.participant_entity_ids:
                    self._require_reference("event participant", entity_id, entity_ids)
            elif isinstance(annotation, (SubjectAnnotation, LocationAnnotation)):
                if annotation.value.entity_id is not None:
                    self._require_reference(
                        "annotation entity", annotation.value.entity_id, entity_ids
                    )
            elif isinstance(annotation, SpeechAnnotation):
                if annotation.value.speaker_entity_id is not None:
                    self._require_reference(
                        "speech speaker",
                        annotation.value.speaker_entity_id,
                        entity_ids,
                    )
                for word in annotation.value.words:
                    if not (
                        annotation.time_range.start_fraction
                        <= word.time_range.start_fraction
                        and word.time_range.end_fraction
                        <= annotation.time_range.end_fraction
                    ):
                        raise ValueError(
                            "speech word range must be inside its utterance range"
                        )
            elif isinstance(annotation, EditorialAnnotation):
                recommended = annotation.value.recommended_range
                if recommended is not None and not (
                    annotation.time_range.start_fraction <= recommended.start_fraction
                    and recommended.end_fraction <= annotation.time_range.end_fraction
                ):
                    raise ValueError(
                        "editorial recommended range must be inside annotation range"
                    )

        for artifact in self.artifacts:
            if artifact.time_range is not None and artifact.time_range.end_fraction > media_end:
                raise ValueError(f"artifact {artifact.id!r} exceeds media duration")

        for capability in self.capabilities:
            for covered in capability.covered_ranges:
                if covered.end_fraction > media_end:
                    raise ValueError(
                        f"capability {capability.name!r} exceeds media duration"
                    )

        for moment in self.moments:
            if moment.time_range.end_fraction > media_end:
                raise ValueError(f"moment {moment.id!r} exceeds media duration")
            if moment.parent_segment_id is not None:
                self._require_reference(
                    "moment parent segment", moment.parent_segment_id, segment_ids
                )
                parent = next(
                    item for item in self.segments if item.id == moment.parent_segment_id
                )
                if not (
                    parent.time_range.start_fraction <= moment.time_range.start_fraction
                    and moment.time_range.end_fraction <= parent.time_range.end_fraction
                ):
                    raise ValueError("moment range must be inside its parent segment")
            for annotation_id in moment.annotation_ids:
                self._require_reference(
                    "moment annotation", annotation_id, annotation_ids
                )

        summary_ids = {item.id for item in self.summaries}
        for summary in self.summaries:
            if summary.time_range.end_fraction > media_end:
                raise ValueError(f"summary {summary.id!r} exceeds media duration")
            for child_id in summary.child_ids:
                self._require_reference("summary child", child_id, summary_ids)
                if child_id == summary.id:
                    raise ValueError("summary cannot be its own child")
        for run in self.analysis_runs:
            for annotation_id in run.annotation_ids:
                self._require_reference(
                    "analysis annotation", annotation_id, annotation_ids
                )

        for relation in self.relations:
            self._require_reference(
                "relation source", relation.source_segment_id, segment_ids
            )
            self._require_reference(
                "relation target", relation.target_segment_id, segment_ids
            )
            if relation.source_segment_id == relation.target_segment_id:
                raise ValueError("segment relation cannot reference one segment twice")

        for plan in self.edit_plans:
            for clip in plan.clips:
                self._require_reference(
                    "edit clip segment", clip.source_segment_id, segment_ids
                )
                source_segment = next(
                    item for item in self.segments if item.id == clip.source_segment_id
                )
                if not (
                    source_segment.time_range.start_fraction
                    <= clip.source_range.start_fraction
                    and clip.source_range.end_fraction
                    <= source_segment.time_range.end_fraction
                ):
                    raise ValueError(
                        "edit clip source range must be inside its source segment"
                    )

        return self

    @staticmethod
    def _require_unique_ids(label: str, values: list[str]) -> None:
        if len(values) != len(set(values)):
            raise ValueError(f"{label} IDs must be unique")

    @staticmethod
    def _require_reference(label: str, value: str, valid: set[str]) -> None:
        if value not in valid:
            raise ValueError(f"unknown {label} reference: {value!r}")

    @staticmethod
    def _validate_evidence_artifacts(
        evidence: tuple[object, ...], artifact_ids: set[str]
    ) -> None:
        for item in evidence:
            artifact_id = getattr(item, "artifact_id", None)
            if artifact_id is not None and artifact_id not in artifact_ids:
                raise ValueError(
                    f"unknown evidence artifact reference: {artifact_id!r}"
                )
