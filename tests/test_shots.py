"""FFmpeg shot detection and frame extraction tests."""

import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from semanticvideo.analysis import shots
from semanticvideo.errors import FFmpegExecutionError, FFmpegNotFoundError
from semanticvideo.schema import RationalTime


def completed(
    *, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, "", stderr)


def test_detect_shot_boundaries_parses_unique_sorted_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stderr = "pts_time:2.5 x\npts_time:1.25 x\npts_time:2.5 x\npts_time:0 x"
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: completed(stderr=stderr)
    )

    assert shots.detect_shot_boundaries(Path("clip.mp4")) == (
        Fraction(5, 4),
        Fraction(5, 2),
    )


def test_shot_detection_validates_threshold() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        shots.detect_shot_boundaries(Path("clip.mp4"), threshold=1)


def test_ffmpeg_failures_are_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(FFmpegNotFoundError):
        shots.detect_shot_boundaries(Path("clip.mp4"))

    def timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("ffmpeg", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(FFmpegExecutionError, match="timed out"):
        shots.detect_shot_boundaries(Path("clip.mp4"))

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: completed(returncode=2, stderr="bad filter"),
    )
    with pytest.raises(FFmpegExecutionError, match="bad filter"):
        shots.detect_shot_boundaries(Path("clip.mp4"))


def test_build_shot_ranges_merges_short_ranges() -> None:
    ranges = shots.build_shot_ranges(
        RationalTime(value=10, rate=1),
        (Fraction(1, 10), Fraction(2), Fraction(39, 4)),
        minimum_duration=0.5,
    )

    assert [(item.start_fraction, item.end_fraction) for item in ranges] == [
        (Fraction(0), Fraction(2)),
        (Fraction(2), Fraction(10)),
    ]
    assert shots.representative_time(ranges[0]).fraction == 1


def test_build_shot_ranges_rejects_non_positive_minimum() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        shots.build_shot_ranges(RationalTime(value=1, rate=1), (), minimum_duration=0)


def test_representative_times_sample_inside_shot() -> None:
    time_range = shots.build_shot_ranges(RationalTime(value=4, rate=1), ())[0]
    assert [item.fraction for item in shots.representative_times(time_range)] == [
        Fraction(1),
        Fraction(2),
        Fraction(3),
    ]
    with pytest.raises(ValueError, match="between 1 and 9"):
        shots.representative_times(time_range, count=0)


def test_extract_frame_requires_written_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: completed())
    output = tmp_path / "frame.jpg"
    with pytest.raises(FFmpegExecutionError, match="no frame was written"):
        shots.extract_frame(Path("clip.mp4"), RationalTime(value=1, rate=2), output)

    output.write_bytes(b"jpeg")
    shots.extract_frame(Path("clip.mp4"), RationalTime(value=1, rate=2), output)
