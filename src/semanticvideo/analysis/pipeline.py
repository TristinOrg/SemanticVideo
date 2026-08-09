"""Compose technical inspection, shot detection, and scene descriptions."""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Collection
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from semanticvideo import __version__
from semanticvideo.analysis.shots import (
    build_shot_ranges,
    detect_shot_boundaries,
    extract_frame,
    representative_time,
)
from semanticvideo.analysis.types import ShotDescriber
from semanticvideo.media import inspect_media
from semanticvideo.media.ffprobe import run_ffprobe
from semanticvideo.schema import (
    AnalysisRun,
    Annotation,
    AudioStream,
    Checksum,
    Evidence,
    GeneratorInfo,
    MediaInfo,
    Provenance,
    ProvenanceSource,
    SceneAnnotation,
    SceneInfo,
    Segment,
    SegmentKind,
    SemanticVideoDocument,
    Stream,
    VideoStream,
)

INCLUDE_CHOICES = frozenset({"technical", "metadata", "checksum", "raw"})


def analyze_video(
    path: str | Path,
    *,
    describer: ShotDescriber,
    ffprobe_executable: str = "ffprobe",
    ffmpeg_executable: str = "ffmpeg",
    timeout_seconds: float = 300,
    scene_threshold: float = 0.3,
    minimum_shot_duration: float = 0.5,
    language: str = "en",
    include: Collection[str] = (),
) -> SemanticVideoDocument:
    """Generate one complete editing-oriented SemanticVideo JSON document."""

    invalid = set(include) - INCLUDE_CHOICES
    if invalid:
        raise ValueError(f"unknown optional information: {', '.join(sorted(invalid))}")

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

    detector_generator = GeneratorInfo(name="semanticvideo-ffmpeg", version=__version__)
    detector_provenance = Provenance(
        source=ProvenanceSource.SIGNAL_ANALYSIS,
        generated_at=started_at,
        generator=detector_generator,
    )
    description_generator = GeneratorInfo(
        name=describer.name,
        version=describer.version,
        provider=describer.provider,
        model=describer.model,
    )
    segments: list[Segment] = []
    annotations: list[Annotation] = []

    with tempfile.TemporaryDirectory(prefix="semanticvideo-") as temp_directory:
        frame_directory = Path(temp_directory)
        for index, time_range in enumerate(ranges, start=1):
            shot_id = f"shot.{index:04d}"
            annotation_id = f"annotation.scene.{index:04d}"
            timestamp = representative_time(time_range)
            frame = frame_directory / f"{shot_id}.jpg"
            extract_frame(
                media_path,
                timestamp,
                frame,
                executable=ffmpeg_executable,
                timeout_seconds=timeout_seconds,
            )
            description = describer.describe(shot_id, (frame,), language=language)
            evidence = Evidence(
                type="representative_frame",
                value={
                    "timestamp": {
                        "value": timestamp.value,
                        "rate": timestamp.rate,
                    }
                },
            )
            description_provenance = Provenance(
                source=describer.source,
                generated_at=started_at,
                generator=description_generator,
                confidence=description.confidence,
                evidence=(evidence,),
            )
            annotations.append(
                SceneAnnotation(
                    id=annotation_id,
                    time_range=time_range,
                    status=describer.status,
                    confidence=description.confidence,
                    provenance=(description_provenance,),
                    evidence=(evidence,),
                    value=SceneInfo(
                        description=description.description,
                        environment=description.environment,
                        subjects=description.subjects,
                        actions=description.actions,
                        objects=description.objects,
                        visible_text=description.visible_text,
                        location_hint=description.location_hint,
                        shot_type=description.shot_type,
                        camera_movement=description.camera_movement,
                        editorial_role=description.editorial_role,
                    ),
                )
            )
            segments.append(
                Segment(
                    id=shot_id,
                    kind=SegmentKind.SHOT,
                    time_range=time_range,
                    representative_times=(timestamp,),
                    annotation_ids=(annotation_id,),
                    provenance=(detector_provenance,),
                )
            )

    extensions: dict[str, JsonValue] = {}
    if "raw" in include:
        raw = run_ffprobe(
            media_path,
            executable=ffprobe_executable,
            timeout_seconds=timeout_seconds,
        )
        extensions["org.semanticvideo.ffprobe"] = cast(JsonValue, raw)

    annotation_ids = tuple(annotation.id for annotation in annotations)
    completed_at = datetime.now(UTC)
    run = AnalysisRun(
        id=f"run.{started_at.strftime('%Y%m%dT%H%M%S%fZ')}",
        analyzer="semanticvideo-analyze",
        analyzer_version=__version__,
        started_at=started_at,
        completed_at=completed_at,
        capabilities=("media", "shots", "scene_descriptions"),
        parameters={
            "scene_threshold": scene_threshold,
            "minimum_shot_duration": minimum_shot_duration,
            "language": language,
            "include": sorted(include),
        },
        annotation_ids=annotation_ids,
    )
    return SemanticVideoDocument(
        document_id=media.id.replace("asset.", "document.", 1),
        generated_at=completed_at,
        media=media,
        segments=tuple(segments),
        annotations=tuple(annotations),
        analysis_runs=(run,),
        extensions=extensions,
    )


def _select_media_fields(media: MediaInfo, include: set[str]) -> MediaInfo:
    if "checksum" in include:
        digest = _sha256(Path(media.uri))
        checksum = Checksum(value=digest)
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
