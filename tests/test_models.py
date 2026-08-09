"""Local model validation rules."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from semanticvideo import (
    AnalysisRun,
    AudioStream,
    Checksum,
    MediaInfo,
    QualityMetrics,
    RationalTime,
    Segment,
    SegmentKind,
    SpatialRegion,
    TimeRange,
    VideoStream,
)
from semanticvideo.schema.provenance import Provenance


def test_media_requires_video_stream() -> None:
    with pytest.raises(ValidationError, match="at least one video stream"):
        MediaInfo(
            id="asset.test",
            uri="test.wav",
            duration=RationalTime(value=1, rate=1),
            streams=(
                AudioStream(
                    id="audio.0",
                    index=0,
                    codec="pcm_s16le",
                    sample_rate=48_000,
                    channels=2,
                ),
            ),
        )


def test_media_rejects_duplicate_stream_ids_and_indexes() -> None:
    video = VideoStream(id="stream.0", index=0, codec="h264", width=1920, height=1080)
    duplicate = VideoStream(
        id="stream.0", index=0, codec="hevc", width=1920, height=1080
    )
    with pytest.raises(ValidationError, match="stream IDs must be unique"):
        MediaInfo(
            id="asset.test",
            uri="test.mp4",
            duration=RationalTime(value=1, rate=1),
            streams=(video, duplicate),
        )

    same_index = VideoStream(
        id="stream.1", index=0, codec="hevc", width=1920, height=1080
    )
    with pytest.raises(ValidationError, match="stream indexes must be unique"):
        MediaInfo(
            id="asset.test",
            uri="test.mp4",
            duration=RationalTime(value=1, rate=1),
            streams=(video, same_index),
        )


def test_media_rejects_zero_duration() -> None:
    with pytest.raises(ValidationError, match="media duration must be positive"):
        MediaInfo(
            id="asset.test",
            uri="test.mp4",
            duration=RationalTime(value=0, rate=1),
            streams=(
                VideoStream(
                    id="stream.0",
                    index=0,
                    codec="h264",
                    width=1920,
                    height=1080,
                ),
            ),
        )


def test_spatial_region_must_fit_frame() -> None:
    with pytest.raises(ValidationError, match="fit within the frame"):
        SpatialRegion(x=0.8, y=0.1, width=0.3, height=0.2)


def test_segment_representative_must_be_inside() -> None:
    with pytest.raises(ValidationError, match="inside segment"):
        Segment(
            id="shot.1",
            kind=SegmentKind.SHOT,
            time_range=TimeRange(
                start=RationalTime(value=0, rate=1),
                duration=RationalTime(value=2, rate=1),
            ),
            representative_times=(RationalTime(value=2, rate=1),),
        )


def test_quality_metrics_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="at least one quality metric"):
        QualityMetrics()


def test_automated_provenance_requires_generator() -> None:
    with pytest.raises(ValidationError, match="requires generator"):
        Provenance(
            source="local_model",
            generated_at=datetime.now(UTC),
        )


def test_analysis_completion_must_follow_start() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="cannot precede"):
        AnalysisRun(
            id="run.1",
            analyzer="test",
            analyzer_version="1",
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


def test_checksum_is_sha256_hex() -> None:
    assert Checksum(value="a" * 64).algorithm == "sha256"
    with pytest.raises(ValidationError):
        Checksum(value="not-a-checksum")
