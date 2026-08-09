"""Editing-oriented single-document analysis pipeline tests."""

from fractions import Fraction
from pathlib import Path

import pytest

from semanticvideo.analysis import pipeline
from semanticvideo.analysis.types import ShotDescription
from semanticvideo.schema import (
    AnnotationStatus,
    AudioStream,
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
    assert len(document.segments) == len(document.annotations) == 2
    assert document.segments[0].annotation_ids == ("annotation.scene.0001",)
    first_annotation = document.annotations[0]
    assert isinstance(first_annotation, SceneAnnotation)
    assert first_annotation.value.description is not None
    assert first_annotation.value.description.endswith("zh-CN")
    assert first_annotation.value.actions == ("walking",)
    assert document.analysis_runs[0].capabilities == (
        "media",
        "shots",
        "scene_descriptions",
    )
    assert document.media.bit_rate is None
    assert document.media.metadata == {}


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


def test_analyze_rejects_unknown_optional_information(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown optional"):
        pipeline.analyze_video(
            tmp_path / "clip.mp4", describer=StubDescriber(), include=("faces",)
        )
