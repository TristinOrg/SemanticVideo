"""Deterministic frame, audio, location, and recommendation signal tests."""

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from semanticvideo.analysis import signals
from semanticvideo.errors import FFmpegExecutionError, FFmpegNotFoundError
from semanticvideo.schema import MediaInfo, RationalTime, TimeRange, VideoStream


def media_with_metadata(metadata: dict[str, str]) -> MediaInfo:
    return MediaInfo(
        id="asset.test",
        uri="clip.mp4",
        duration=RationalTime(value=10, rate=1),
        streams=(
            VideoStream(
                id="stream.video.0",
                index=0,
                codec="h264",
                width=100,
                height=100,
            ),
        ),
        metadata=metadata,
    )


def test_frame_signals_measure_images_and_similarity(tmp_path: Path) -> None:
    dark = tmp_path / "dark.png"
    bright = tmp_path / "bright.png"
    Image.new("L", (16, 16), 40).save(dark)
    image = Image.new("L", (16, 16), 210)
    for x in range(0, 16, 2):
        for y in range(16):
            image.putpixel((x, y), 20)
    image.save(bright)

    result = signals.analyze_representative_frames((dark, bright))

    assert 0 <= result.quality_score <= 1
    assert result.motion_score > 0
    assert signals.hash_similarity(result.average_hash, result.average_hash) == 1
    with pytest.raises(ValueError, match="at least one"):
        signals.analyze_representative_frames(())


def test_recommended_range_trims_only_long_shots() -> None:
    short = TimeRange(
        start=RationalTime(value=0, rate=1),
        duration=RationalTime(value=1, rate=1),
    )
    long = TimeRange(
        start=RationalTime(value=2, rate=1),
        duration=RationalTime(value=10, rate=1),
    )
    assert signals.recommended_range(short) == short
    assert signals.recommended_range(long).start.seconds == pytest.approx(2.15)
    assert signals.recommended_range(long).duration.seconds == pytest.approx(9.7)


def test_parse_volume_detect_handles_normal_and_silent_audio() -> None:
    normal = signals.parse_volume_detect("mean_volume: -18.5 dB\nmax_volume: -1.0 dB")
    silent = signals.parse_volume_detect("mean_volume: -inf dB\nmax_volume: -inf dB")

    assert normal.mean_dbfs == -18.5
    assert not normal.is_silence
    assert silent.mean_dbfs == -100
    assert silent.is_silence
    with pytest.raises(FFmpegExecutionError, match="did not report"):
        signals.parse_volume_detect("no metrics")


def test_measure_audio_levels_handles_process_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    time_range = TimeRange(
        start=RationalTime(value=0, rate=1),
        duration=RationalTime(value=1, rate=1),
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, "", "mean_volume: -20 dB\nmax_volume: -2 dB"
        ),
    )
    assert signals.measure_audio_levels(Path("clip.mp4"), time_range).peak_dbfs == -2

    def missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(FFmpegNotFoundError):
        signals.measure_audio_levels(Path("clip.mp4"), time_range)

    def timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("ffmpeg", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(FFmpegExecutionError, match="timed out"):
        signals.measure_audio_levels(Path("clip.mp4"), time_range)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 2, "", "bad audio"),
    )
    with pytest.raises(FFmpegExecutionError, match="bad audio"):
        signals.measure_audio_levels(Path("clip.mp4"), time_range)


def test_location_metadata_supports_coordinates_names_and_absence() -> None:
    coordinate = signals.location_from_metadata(
        media_with_metadata(
            {
                "com.apple.quicktime.location.ISO6709": "+35.6812+139.7671/",
                "location-name": "Tokyo Station",
            }
        )
    )
    assert coordinate is not None
    assert coordinate.info.name == "Tokyo Station"
    assert coordinate.info.point is not None
    assert coordinate.info.point.latitude == pytest.approx(35.6812)

    named = signals.location_from_metadata(media_with_metadata({"location": "Kyoto"}))
    assert named is not None
    assert named.info.name == "Kyoto"
    assert (
        signals.location_from_metadata(media_with_metadata({"title": "Trip"})) is None
    )
