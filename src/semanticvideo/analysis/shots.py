"""Deterministic FFmpeg shot detection and representative-frame extraction."""

from __future__ import annotations

import re
import subprocess
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

from semanticvideo.errors import FFmpegExecutionError, FFmpegNotFoundError
from semanticvideo.schema import RationalTime, TimeRange

_PTS_TIME = re.compile(r"pts_time:(?P<seconds>[0-9]+(?:\.[0-9]+)?)")


def detect_shot_boundaries(
    path: Path,
    *,
    executable: str = "ffmpeg",
    threshold: float = 0.3,
    timeout_seconds: float = 300,
) -> tuple[Fraction, ...]:
    """Return FFmpeg scene-change timestamps, excluding media start and end."""

    if not 0 < threshold < 1:
        raise ValueError("scene threshold must be between zero and one")
    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-v",
        "info",
        "-i",
        str(path),
        "-an",
        "-vf",
        f"select='gt(scene,{threshold:g})',showinfo",
        "-f",
        "null",
        "-",
    ]
    completed = _run_ffmpeg(command, "shot detection", timeout_seconds)
    boundaries = {
        Fraction(match.group("seconds"))
        for match in _PTS_TIME.finditer(completed.stderr)
    }
    return tuple(sorted(boundary for boundary in boundaries if boundary > 0))


def build_shot_ranges(
    duration: RationalTime,
    boundaries: tuple[Fraction, ...],
    *,
    minimum_duration: float = 0.5,
) -> tuple[TimeRange, ...]:
    """Convert noisy scene changes into contiguous, minimum-length shot ranges."""

    if minimum_duration <= 0:
        raise ValueError("minimum shot duration must be greater than zero")
    end = duration.fraction
    minimum = Fraction(str(minimum_duration))
    cuts = [Fraction(0)]
    for boundary in boundaries:
        if boundary >= end or boundary - cuts[-1] < minimum:
            continue
        cuts.append(boundary)
    if len(cuts) > 1 and end - cuts[-1] < minimum:
        cuts.pop()
    cuts.append(end)
    return tuple(
        TimeRange(start=_time(start), duration=_time(stop - start))
        for start, stop in pairwise(cuts)
    )


def representative_time(time_range: TimeRange) -> RationalTime:
    """Choose the temporal midpoint as a stable representative frame."""

    return _time(time_range.start_fraction + time_range.duration_fraction / 2)


def extract_frame(
    path: Path,
    timestamp: RationalTime,
    output: Path,
    *,
    executable: str = "ffmpeg",
    timeout_seconds: float = 60,
) -> None:
    """Extract one JPEG frame without invoking a shell."""

    seconds = f"{timestamp.seconds:.6f}"
    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-ss",
        seconds,
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    _run_ffmpeg(command, "frame extraction", timeout_seconds)
    if not output.is_file() or output.stat().st_size == 0:
        raise FFmpegExecutionError("frame extraction", 0, "no frame was written")


def _run_ffmpeg(
    command: list[str], operation: str, timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        raise FFmpegNotFoundError(
            f"ffmpeg executable was not found: {command[0]!r}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise FFmpegExecutionError(
            operation, -1, f"timed out after {timeout_seconds:g} seconds"
        ) from error
    if completed.returncode != 0:
        raise FFmpegExecutionError(operation, completed.returncode, completed.stderr)
    return completed


def _time(value: Fraction) -> RationalTime:
    return RationalTime(value=value.numerator, rate=value.denominator)
