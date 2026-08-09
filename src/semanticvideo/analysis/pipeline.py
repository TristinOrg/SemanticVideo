"""Compose technical, temporal, semantic, and deterministic editing analysis."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from semanticvideo import __version__
from semanticvideo.analysis.shots import (
    build_shot_ranges,
    detect_shot_boundaries,
    extract_frame,
    representative_times,
)
from semanticvideo.analysis.signals import (
    AudioLevels,
    FrameSignals,
    analyze_representative_frames,
    hash_similarity,
    location_from_metadata,
    measure_audio_levels,
    recommended_range,
)
from semanticvideo.analysis.transcription import (
    Transcriber,
    TranscriptResult,
    extract_audio,
)
from semanticvideo.analysis.types import ShotDescriber, ShotDescription
from semanticvideo.errors import VideoAnalysisError
from semanticvideo.media import inspect_media
from semanticvideo.media.ffprobe import run_ffprobe
from semanticvideo.schema import (
    AnalysisRun,
    Annotation,
    AnnotationStatus,
    AudioAnnotation,
    AudioContentType,
    AudioInfo,
    AudioStream,
    CapabilityReport,
    CapabilityStatus,
    Checksum,
    EditingSignals,
    EditorialAnnotation,
    Evidence,
    GeneratorInfo,
    LocationAnnotation,
    LocationInfo,
    MediaInfo,
    Provenance,
    ProvenanceSource,
    RationalTime,
    SceneAnnotation,
    SceneInfo,
    Segment,
    SegmentKind,
    SegmentRelation,
    SegmentRelationType,
    SemanticVideoDocument,
    SpeechAnnotation,
    SpeechInfo,
    SpeechWord,
    Stream,
    TimeRange,
    VideoStream,
)

INCLUDE_CHOICES = frozenset({"technical", "metadata", "checksum", "raw"})


@dataclass(frozen=True)
class _ShotObservation:
    index: int
    time_range: TimeRange
    representative_times: tuple[RationalTime, ...]
    description: ShotDescription
    frame_signals: FrameSignals

    @property
    def shot_id(self) -> str:
        return f"shot.{self.index:04d}"


def analyze_video(
    path: str | Path,
    *,
    describer: ShotDescriber,
    ffprobe_executable: str = "ffprobe",
    ffmpeg_executable: str = "ffmpeg",
    timeout_seconds: float = 300,
    scene_threshold: float = 0.3,
    minimum_shot_duration: float = 0.5,
    frames_per_shot: int = 3,
    language: str = "en",
    include: Collection[str] = (),
    transcriber: Transcriber | None = None,
    transcript: TranscriptResult | None = None,
    imported_location: LocationInfo | None = None,
) -> SemanticVideoDocument:
    """Generate one complete editing-oriented SemanticVideo JSON document."""

    invalid = set(include) - INCLUDE_CHOICES
    if invalid:
        raise ValueError(f"unknown optional information: {', '.join(sorted(invalid))}")
    if not 1 <= frames_per_shot <= 9:
        raise ValueError("frames per shot must be between 1 and 9")
    if transcriber is not None and transcript is not None:
        raise ValueError("transcriber and imported transcript are mutually exclusive")

    started_at = datetime.now(UTC)
    media_path = Path(path)
    inspected = inspect_media(
        media_path,
        executable=ffprobe_executable,
        timeout_seconds=timeout_seconds,
    )
    media = _select_media_fields(inspected, set(include))
    boundaries = detect_shot_boundaries(
        media_path,
        executable=ffmpeg_executable,
        threshold=scene_threshold,
        timeout_seconds=timeout_seconds,
    )
    ranges = build_shot_ranges(
        media.duration,
        boundaries,
        minimum_duration=minimum_shot_duration,
    )

    observations: list[_ShotObservation] = []
    transcript_result = transcript
    with tempfile.TemporaryDirectory(prefix="semanticvideo-") as temp_directory:
        frame_directory = Path(temp_directory)
        for index, time_range in enumerate(ranges, start=1):
            shot_id = f"shot.{index:04d}"
            timestamps = representative_times(time_range, count=frames_per_shot)
            frames: list[Path] = []
            for frame_index, timestamp in enumerate(timestamps, start=1):
                frame = frame_directory / f"{shot_id}.{frame_index:02d}.jpg"
                extract_frame(
                    media_path,
                    timestamp,
                    frame,
                    executable=ffmpeg_executable,
                    timeout_seconds=timeout_seconds,
                )
                frames.append(frame)
            frame_tuple = tuple(frames)
            observations.append(
                _ShotObservation(
                    index=index,
                    time_range=time_range,
                    representative_times=timestamps,
                    description=describer.describe(
                        shot_id, frame_tuple, language=language
                    ),
                    frame_signals=analyze_representative_frames(frame_tuple),
                )
            )
        if transcriber is not None:
            audio_file = frame_directory / "transcription.mp3"
            extract_audio(
                media_path,
                audio_file,
                executable=ffmpeg_executable,
                timeout_seconds=timeout_seconds,
            )
            transcript_result = transcriber.transcribe(audio_file)

    relations = _infer_relations(observations)
    duplicate_groups = _duplicate_groups(relations)
    annotations: list[Annotation] = []
    segments: list[Segment] = []
    detector_provenance = _automated_provenance(
        "semanticvideo-ffmpeg", started_at, ProvenanceSource.SIGNAL_ANALYSIS
    )
    signal_provenance = _automated_provenance(
        "semanticvideo-signals", started_at, ProvenanceSource.SIGNAL_ANALYSIS
    )
    description_provenance_base = GeneratorInfo(
        name=describer.name,
        version=describer.version,
        provider=describer.provider,
        model=describer.model,
    )

    audio_capability = CapabilityReport(
        name="audio_levels",
        status=CapabilityStatus.OMITTED,
        message="source has no supported audio stream",
    )
    audio_levels: dict[str, AudioLevels] = {}
    if any(isinstance(stream, AudioStream) for stream in inspected.streams):
        try:
            audio_levels = {
                item.shot_id: measure_audio_levels(
                    media_path,
                    item.time_range,
                    executable=ffmpeg_executable,
                    timeout_seconds=timeout_seconds,
                )
                for item in observations
            }
            audio_capability = CapabilityReport(
                name="audio_levels", status=CapabilityStatus.COMPLETE
            )
        except VideoAnalysisError as error:
            audio_capability = CapabilityReport(
                name="audio_levels",
                status=CapabilityStatus.FAILED,
                message=str(error),
            )

    for item in observations:
        scene_id = f"annotation.scene.{item.index:04d}"
        editorial_id = f"annotation.editorial.{item.index:04d}"
        timestamp_value = [
            {"value": timestamp.value, "rate": timestamp.rate}
            for timestamp in item.representative_times
        ]
        evidence = Evidence(type="representative_frames", value=timestamp_value)
        description_provenance = Provenance(
            source=describer.source,
            generated_at=started_at,
            generator=description_provenance_base,
            confidence=item.description.confidence,
            evidence=(evidence,),
        )
        annotations.append(
            SceneAnnotation(
                id=scene_id,
                time_range=item.time_range,
                status=describer.status,
                confidence=item.description.confidence,
                provenance=(description_provenance,),
                evidence=(evidence,),
                value=SceneInfo(
                    summary=item.description.resolved_summary,
                    environment=item.description.environment,
                    subjects=item.description.subjects,
                    actions=item.description.actions,
                    objects=item.description.objects,
                    visible_text=item.description.visible_text,
                    location_hint=item.description.location_hint,
                    shot_type=item.description.shot_type,
                    camera_movement=item.description.camera_movement,
                ),
            )
        )

        richness = min(
            1.0,
            sum(
                len(values)
                for values in (
                    item.description.subjects,
                    item.description.actions,
                    item.description.objects,
                    item.description.environment,
                )
            )
            / 8,
        )
        interest = _unit(
            0.55 * item.frame_signals.quality_score
            + 0.25 * item.frame_signals.motion_score
            + 0.20 * richness
        )
        usable = item.frame_signals.quality_score >= 0.25
        annotations.append(
            EditorialAnnotation(
                id=editorial_id,
                time_range=item.time_range,
                status=AnnotationStatus.MACHINE_GENERATED,
                provenance=(signal_provenance,),
                value=EditingSignals(
                    quality_score=item.frame_signals.quality_score,
                    interest_score=interest,
                    usable=usable,
                    recommended_range=recommended_range(item.time_range),
                    editorial_role=item.description.editorial_role,
                    duplicate_group=duplicate_groups.get(item.shot_id),
                    reasons=(
                        f"exposure={item.frame_signals.exposure_score:.3f}",
                        f"sharpness={item.frame_signals.sharpness_score:.3f}",
                        f"visual_change={item.frame_signals.motion_score:.3f}",
                    ),
                    warnings=() if usable else ("low deterministic image quality",),
                ),
            )
        )

        annotation_ids = [scene_id, editorial_id]
        levels = audio_levels.get(item.shot_id)
        if levels is not None:
            audio_id = f"annotation.audio.{item.index:04d}"
            annotations.append(
                AudioAnnotation(
                    id=audio_id,
                    time_range=item.time_range,
                    status=AnnotationStatus.MACHINE_GENERATED,
                    provenance=(signal_provenance,),
                    value=AudioInfo(
                        type=(
                            AudioContentType.SILENCE
                            if levels.is_silence
                            else AudioContentType.MIXED
                        ),
                        summary=(
                            "Silent or near-silent audio"
                            if levels.is_silence
                            else "Audio present; semantic class requires a provider"
                        ),
                        mean_volume_dbfs=levels.mean_dbfs,
                        peak_volume_dbfs=levels.peak_dbfs,
                    ),
                )
            )
            annotation_ids.append(audio_id)

        segments.append(
            Segment(
                id=item.shot_id,
                kind=SegmentKind.SHOT,
                time_range=item.time_range,
                representative_times=item.representative_times,
                annotation_ids=tuple(annotation_ids),
                provenance=(detector_provenance,),
            )
        )

    location = location_from_metadata(inspected)
    location_capability = CapabilityReport(
        name="location",
        status=CapabilityStatus.OMITTED,
        message="no embedded or agent-supplied location evidence",
    )
    if location is not None or imported_location is not None:
        location_info = location.info if location is not None else imported_location
        assert location_info is not None
        location_evidence: tuple[Evidence, ...]
        if location is not None:
            location_id = "annotation.location.embedded"
            location_source = ProvenanceSource.EMBEDDED_METADATA
            location_evidence = (
                Evidence(type="metadata_keys", value=list(location.metadata_keys)),
            )
        else:
            location_id = "annotation.location.agent"
            location_source = ProvenanceSource.IMPORT
            location_evidence = ()
        annotations.append(
            LocationAnnotation(
                id=location_id,
                time_range=TimeRange(
                    start=media.duration.model_copy(update={"value": 0}),
                    duration=media.duration,
                ),
                status=AnnotationStatus.MACHINE_GENERATED,
                provenance=(
                    Provenance(
                        source=location_source,
                        generated_at=started_at,
                        evidence=location_evidence,
                    ),
                ),
                value=location_info,
            )
        )
        location_capability = CapabilityReport(
            name="location", status=CapabilityStatus.COMPLETE
        )

    transcription_capability = CapabilityReport(
        name="transcript",
        status=CapabilityStatus.OMITTED,
        message="no transcriber or agent transcript supplied",
    )
    if transcript_result is not None:
        if transcriber is None:
            transcript_generator = GeneratorInfo(
                name="semanticvideo-agent-response", version="1", provider="agent"
            )
            transcript_source = ProvenanceSource.IMPORT
            transcript_status = AnnotationStatus.MACHINE_GENERATED
            transcript_provider = "external-agent"
        else:
            transcript_generator = GeneratorInfo(
                name=transcriber.name,
                version=transcriber.version,
                provider=transcriber.provider,
                model=transcriber.model,
            )
            transcript_source = transcriber.source
            transcript_status = transcriber.status
            transcript_provider = transcriber.provider or transcriber.name
        transcript_annotations = _speech_annotations(
            transcript_result,
            media.duration.fraction,
            started_at,
            transcript_generator,
            transcript_source,
            transcript_status,
        )
        annotations.extend(transcript_annotations)
        transcription_capability = CapabilityReport(
            name="transcript",
            status=(
                CapabilityStatus.COMPLETE
                if transcript_result.segments
                else CapabilityStatus.PARTIAL
            ),
            provider=transcript_provider,
            message=None
            if transcript_result.segments
            else "transcript has no segments",
        )

    extensions: dict[str, JsonValue] = {}
    if "raw" in include:
        raw = run_ffprobe(
            media_path,
            executable=ffprobe_executable,
            timeout_seconds=timeout_seconds,
        )
        extensions["org.semanticvideo.ffprobe"] = cast(JsonValue, raw)

    capabilities = (
        CapabilityReport(name="media", status=CapabilityStatus.COMPLETE, required=True),
        CapabilityReport(name="shots", status=CapabilityStatus.COMPLETE, required=True),
        CapabilityReport(
            name="scene_descriptions",
            status=CapabilityStatus.COMPLETE,
            required=True,
            provider=describer.provider or describer.name,
        ),
        CapabilityReport(
            name="editing_signals", status=CapabilityStatus.COMPLETE, required=True
        ),
        CapabilityReport(name="segment_relations", status=CapabilityStatus.COMPLETE),
        transcription_capability,
        audio_capability,
        location_capability,
    )
    completed_at = datetime.now(UTC)
    all_annotation_ids = tuple(annotation.id for annotation in annotations)
    run = AnalysisRun(
        id=f"run.{started_at.strftime('%Y%m%dT%H%M%S%fZ')}",
        analyzer="semanticvideo-analyze",
        analyzer_version=__version__,
        started_at=started_at,
        completed_at=completed_at,
        capabilities=tuple(item.name for item in capabilities),
        parameters={
            "scene_threshold": scene_threshold,
            "minimum_shot_duration": minimum_shot_duration,
            "frames_per_shot": frames_per_shot,
            "language": language,
            "include": sorted(include),
        },
        annotation_ids=all_annotation_ids,
    )
    return SemanticVideoDocument(
        document_id=media.id.replace("asset.", "document.", 1),
        generated_at=completed_at,
        media=media,
        segments=tuple(segments),
        annotations=tuple(annotations),
        analysis_runs=(run,),
        capabilities=capabilities,
        relations=relations,
        extensions=extensions,
    )


def _speech_annotations(
    transcript: TranscriptResult,
    media_end: Fraction,
    generated_at: datetime,
    generator: GeneratorInfo,
    source: ProvenanceSource,
    status: AnnotationStatus,
) -> tuple[SpeechAnnotation, ...]:
    annotations: list[SpeechAnnotation] = []
    provenance = Provenance(
        source=source,
        generated_at=generated_at,
        generator=generator,
    )
    for index, segment in enumerate(transcript.segments, start=1):
        start = max(Fraction(0), Fraction(str(segment.start_seconds)))
        end = min(media_end, Fraction(str(segment.end_seconds)))
        if end <= start:
            continue
        segment_range = TimeRange(
            start=_fraction_time(start), duration=_fraction_time(end - start)
        )
        words: list[SpeechWord] = []
        for word in segment.words:
            word_start = Fraction(str(word.start_seconds))
            word_end = Fraction(str(word.end_seconds))
            if not (start <= word_start < word_end <= end):
                continue
            words.append(
                SpeechWord(
                    text=word.text,
                    time_range=TimeRange(
                        start=_fraction_time(word_start),
                        duration=_fraction_time(word_end - word_start),
                    ),
                    confidence=word.confidence,
                )
            )
        annotations.append(
            SpeechAnnotation(
                id=f"annotation.speech.{index:04d}",
                time_range=segment_range,
                confidence=segment.confidence,
                status=status,
                provenance=(provenance,),
                tags=(f"speaker:{segment.speaker}",) if segment.speaker else (),
                value=SpeechInfo(
                    text=segment.text,
                    language=transcript.language,
                    words=tuple(words),
                ),
            )
        )
    return tuple(annotations)


def _fraction_time(value: Fraction) -> RationalTime:
    return RationalTime(value=value.numerator, rate=value.denominator)


def _infer_relations(
    observations: list[_ShotObservation],
) -> tuple[SegmentRelation, ...]:
    relations: list[SegmentRelation] = []
    relation_index = 1
    for left_index, left in enumerate(observations):
        for right in observations[left_index + 1 :]:
            semantic = _semantic_similarity(left.description, right.description)
            visual = hash_similarity(
                left.frame_signals.average_hash, right.frame_signals.average_hash
            )
            if right.index == left.index + 1 and semantic >= 0.35:
                relations.append(
                    SegmentRelation(
                        id=f"relation.{relation_index:04d}",
                        type=SegmentRelationType.SAME_SCENE,
                        source_segment_id=left.shot_id,
                        target_segment_id=right.shot_id,
                        confidence=semantic,
                        reasons=("overlapping structured visual semantics",),
                    )
                )
                relation_index += 1
            if semantic >= 0.6 and visual >= 0.96:
                relations.append(
                    SegmentRelation(
                        id=f"relation.{relation_index:04d}",
                        type=SegmentRelationType.DUPLICATE,
                        source_segment_id=left.shot_id,
                        target_segment_id=right.shot_id,
                        confidence=(semantic + visual) / 2,
                        reasons=(
                            "high representative-frame similarity",
                            "high structured-semantic overlap",
                        ),
                    )
                )
                relation_index += 1
    return tuple(relations)


def _duplicate_groups(relations: tuple[SegmentRelation, ...]) -> dict[str, str]:
    parents: dict[str, str] = {}

    def find(item: str) -> str:
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for relation in relations:
        if relation.type is not SegmentRelationType.DUPLICATE:
            continue
        left = find(relation.source_segment_id)
        right = find(relation.target_segment_id)
        parents[right] = left
    roots = sorted({find(item) for item in parents})
    root_names = {root: f"duplicate.{index:04d}" for index, root in enumerate(roots, 1)}
    return {item: root_names[find(item)] for item in parents}


def _semantic_similarity(left: ShotDescription, right: ShotDescription) -> float:
    left_values = _semantic_values(left)
    right_values = _semantic_values(right)
    if not left_values and not right_values:
        return 0.0
    return len(left_values & right_values) / len(left_values | right_values)


def _semantic_values(description: ShotDescription) -> set[str]:
    values = (
        *description.environment,
        *description.subjects,
        *description.actions,
        *description.objects,
    )
    return {value.casefold() for value in values}


def _automated_provenance(
    name: str, generated_at: datetime, source: ProvenanceSource
) -> Provenance:
    return Provenance(
        source=source,
        generated_at=generated_at,
        generator=GeneratorInfo(name=name, version=__version__),
    )


def _select_media_fields(media: MediaInfo, include: set[str]) -> MediaInfo:
    if "checksum" in include:
        checksum = Checksum(value=_sha256(Path(media.uri)))
    else:
        checksum = None

    streams: list[Stream] = []
    for stream in media.streams:
        if "technical" in include:
            streams.append(stream)
        elif isinstance(stream, VideoStream):
            streams.append(
                stream.model_copy(
                    update={
                        "bit_rate": None,
                        "pixel_format": None,
                        "time_base": None,
                        "sample_aspect_ratio": None,
                        "color_primaries": None,
                        "color_transfer": None,
                        "color_space": None,
                        "variable_frame_rate": None,
                    }
                )
            )
        elif isinstance(stream, AudioStream):
            streams.append(
                stream.model_copy(
                    update={
                        "bit_rate": None,
                        "channel_layout": None,
                        "time_base": None,
                    }
                )
            )
        else:
            streams.append(stream)

    keep_metadata = "metadata" in include
    return media.model_copy(
        update={
            "modified_at": media.modified_at if keep_metadata else None,
            "created_at": media.created_at if keep_metadata else None,
            "metadata": media.metadata if keep_metadata else {},
            "bit_rate": media.bit_rate if "technical" in include else None,
            "checksum": checksum,
            "streams": tuple(streams),
        }
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unit(value: float) -> float:
    return max(0.0, min(1.0, value))
