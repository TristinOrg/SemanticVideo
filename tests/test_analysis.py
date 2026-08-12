"""Editing-oriented single-document analysis pipeline tests."""

from fractions import Fraction
from pathlib import Path

import pytest

from semanticvideo.analysis import pipeline
from semanticvideo.analysis.signals import AudioLevels, FrameSignals
from semanticvideo.analysis.transcription import (
    TranscriptResult,
    TranscriptSegmentResult,
    TranscriptWordResult,
)
from semanticvideo.analysis.types import ShotDescription
from semanticvideo.errors import FFmpegExecutionError
from semanticvideo.schema import (
    AnnotationStatus,
    AudioStream,
    LocationInfo,
    MediaInfo,
    ProvenanceSource,
    RationalRate,
    RationalTime,
    SceneAnnotation,
    VideoStream,
)


class StubDescriber:
    name = "stub"
    version = "1"
    provider: str | None = "tests"
    model: str | None = "stub-vision"
    source = ProvenanceSource.LOCAL_MODEL
    status = AnnotationStatus.MACHINE_GENERATED

    def describe(
        self, shot_id: str, frames: tuple[Path, ...], *, language: str
    ) -> ShotDescription:
        assert frames[0].is_file()
        return ShotDescription(
            description=f"{shot_id} described in {language}",
            subjects=("traveler",),
            actions=("walking",),
            confidence=0.8,
        )


class StubTranscriber:
    name = "stub-transcriber"
    version = "1"
    provider: str | None = "tests"
    model: str | None = "stub-audio"
    source = ProvenanceSource.LOCAL_MODEL
    status = AnnotationStatus.MACHINE_GENERATED

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        assert audio_path.is_file()
        return TranscriptResult(
            language="en",
            segments=(
                TranscriptSegmentResult(
                    text="timed speech", start_seconds=0.5, end_seconds=1.5
                ),
            ),
        )


def inspected_media(path: Path) -> MediaInfo:
    return MediaInfo(
        id="asset.test",
        uri=str(path),
        duration=RationalTime(value=10, rate=1),
        file_size=4,
        bit_rate=1000,
        metadata={"title": "Trip"},
        streams=(
            VideoStream(
                id="stream.video.0",
                index=0,
                codec="h264",
                bit_rate=900,
                width=720,
                height=1280,
                frame_rate=RationalRate(numerator=30),
                pixel_format="yuv420p",
            ),
            AudioStream(
                id="stream.audio.1",
                index=1,
                codec="aac",
                bit_rate=100,
                sample_rate=48000,
                channels=2,
                channel_layout="stereo",
            ),
        ),
    )


def configure_pipeline(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(
        pipeline, "inspect_media", lambda *_args, **_kwargs: inspected_media(path)
    )
    monkeypatch.setattr(
        pipeline,
        "detect_shot_boundaries",
        lambda *_args, **_kwargs: (Fraction(4),),
    )

    def extract(
        _path: Path, _timestamp: RationalTime, output: Path, **_kwargs: object
    ) -> None:
        output.write_bytes(b"jpeg")

    monkeypatch.setattr(pipeline, "extract_frame", extract)
    monkeypatch.setattr(
        pipeline,
        "analyze_representative_frames",
        lambda _frames: FrameSignals(
            quality_score=0.8,
            exposure_score=0.7,
            sharpness_score=0.9,
            motion_score=0.2,
            average_hash=1,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "measure_audio_levels",
        lambda *_args, **_kwargs: AudioLevels(mean_dbfs=-20, peak_dbfs=-2),
    )


def test_analyze_video_generates_required_editing_information(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)

    document = pipeline.analyze_video(
        media_path, describer=StubDescriber(), language="zh-CN"
    )

    assert document.document_id == "document.test"
    assert len(document.segments) == 2
    assert len(document.annotations) == 6
    assert document.segments[0].annotation_ids == (
        "annotation.scene.0001",
        "annotation.editorial.0001",
        "annotation.audio.0001",
    )
    first_annotation = document.annotations[0]
    assert isinstance(first_annotation, SceneAnnotation)
    assert first_annotation.value.summary is not None
    assert first_annotation.value.summary.endswith("zh-CN")
    assert first_annotation.value.actions == ("walking",)
    assert document.analysis_runs[0].capabilities == (
        "media",
        "shots",
        "scene_descriptions",
        "editing_signals",
        "segment_relations",
        "transcript",
        "audio_levels",
        "location",
    )
    assert document.media.bit_rate is None
    assert document.media.metadata == {}
    assert {relation.type for relation in document.relations} == {
        "same_scene",
        "duplicate",
    }


def test_optional_information_stays_in_same_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)
    monkeypatch.setattr(
        pipeline, "run_ffprobe", lambda *_args, **_kwargs: {"raw": True}
    )

    document = pipeline.analyze_video(
        media_path,
        describer=StubDescriber(),
        include=("technical", "metadata", "checksum", "raw"),
    )

    assert document.media.bit_rate == 1000
    assert document.media.metadata == {"title": "Trip"}
    assert document.media.checksum is not None
    assert document.media.checksum.value == (
        "67905ad3cc2dd52b1f5f6a6d2814de0396618b29b4238b9af5207aeb69936e6d"
    )
    assert document.extensions["org.semanticvideo.ffprobe"] == {"raw": True}


def test_analysis_can_persist_reusable_frame_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)
    evidence_directory = tmp_path / "trip.semantic" / "keyframes"

    document = pipeline.analyze_video(
        media_path,
        describer=StubDescriber(),
        adaptive_frames=True,
        evidence_directory=evidence_directory,
    )

    assert len(document.artifacts) == 6
    assert all(Path(item.uri).is_file() for item in document.artifacts)
    assert all(item.checksum for item in document.artifacts)
    scene = next(item for item in document.annotations if item.kind == "scene")
    assert all(item.artifact_id for item in scene.evidence)
    assert document.analysis_runs[0].parameters["adaptive_frames"] is True


def test_analyze_rejects_unknown_optional_information(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown optional"):
        pipeline.analyze_video(
            tmp_path / "clip.mp4", describer=StubDescriber(), include=("faces",)
        )
    with pytest.raises(ValueError, match="frames per shot"):
        pipeline.analyze_video(
            tmp_path / "clip.mp4", describer=StubDescriber(), frames_per_shot=0
        )


def test_pipeline_reports_audio_failure_and_embedded_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)
    located = inspected_media(media_path).model_copy(
        update={"metadata": {"location": "+35.0+139.0/"}}
    )
    monkeypatch.setattr(pipeline, "inspect_media", lambda *_args, **_kwargs: located)

    def fail_audio(*_args: object, **_kwargs: object) -> AudioLevels:
        raise FFmpegExecutionError("audio analysis", 2, "bad audio")

    monkeypatch.setattr(pipeline, "measure_audio_levels", fail_audio)

    document = pipeline.analyze_video(media_path, describer=StubDescriber())

    capability = {item.name: item for item in document.capabilities}
    assert capability["audio_levels"].status == "failed"
    assert capability["location"].status == "complete"
    assert any(annotation.kind == "location" for annotation in document.annotations)


def test_pipeline_imports_agent_transcript_and_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)
    transcript = TranscriptResult(
        language="en",
        text="hello",
        segments=(
            TranscriptSegmentResult(
                text="hello",
                start_seconds=1,
                end_seconds=2,
                speaker="host",
                words=(
                    TranscriptWordResult(
                        text="hello", start_seconds=1, end_seconds=1.5
                    ),
                ),
            ),
        ),
    )

    document = pipeline.analyze_video(
        media_path,
        describer=StubDescriber(),
        transcript=transcript,
        imported_location=LocationInfo(name="Tokyo"),
    )

    assert any(annotation.kind == "speech" for annotation in document.annotations)
    assert any(annotation.kind == "location" for annotation in document.annotations)
    capability = {item.name: item for item in document.capabilities}
    assert capability["transcript"].status == "complete"
    assert capability["transcript"].provider == "external-agent"


def test_pipeline_runs_configured_transcriber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "trip.mp4"
    media_path.write_bytes(b"clip")
    configure_pipeline(monkeypatch, media_path)

    def audio(_path: Path, output: Path, **_kwargs: object) -> None:
        output.write_bytes(b"mp3")

    monkeypatch.setattr(pipeline, "extract_audio", audio)
    document = pipeline.analyze_video(
        media_path, describer=StubDescriber(), transcriber=StubTranscriber()
    )
    transcript_capability = next(
        item for item in document.capabilities if item.name == "transcript"
    )
    assert transcript_capability.provider == "tests"

    with pytest.raises(ValueError, match="mutually exclusive"):
        pipeline.analyze_video(
            media_path,
            describer=StubDescriber(),
            transcriber=StubTranscriber(),
            transcript=TranscriptResult(language="en"),
        )
