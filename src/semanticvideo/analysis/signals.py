"""Deterministic frame, audio, location, and similarity signals for editing."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import cast

from PIL import Image, ImageFilter, ImageStat

from semanticvideo.errors import FFmpegExecutionError, FFmpegNotFoundError
from semanticvideo.schema import (
    GeoPoint,
    LocationInfo,
    MediaInfo,
    RationalTime,
    TimeRange,
)

_MEAN_VOLUME = re.compile(r"mean_volume:\s*(?P<value>-?(?:\d+(?:\.\d+)?|inf))\s*dB")
_MAX_VOLUME = re.compile(r"max_volume:\s*(?P<value>-?(?:\d+(?:\.\d+)?|inf))\s*dB")
_ISO_6709 = re.compile(
    r"(?P<latitude>[+-]\d+(?:\.\d+)?)(?P<longitude>[+-]\d+(?:\.\d+)?)"
)


@dataclass(frozen=True)
class FrameSignals:
    """Small deterministic feature set derived from representative images."""

    quality_score: float
    exposure_score: float
    sharpness_score: float
    motion_score: float
    average_hash: int


@dataclass(frozen=True)
class AudioLevels:
    """FFmpeg volume statistics for one source interval."""

    mean_dbfs: float
    peak_dbfs: float

    @property
    def is_silence(self) -> bool:
        return self.mean_dbfs <= -50


@dataclass(frozen=True)
class LocationFinding:
    """Location parsed from embedded metadata with the supporting tag names."""

    info: LocationInfo
    metadata_keys: tuple[str, ...]


def analyze_representative_frames(frames: tuple[Path, ...]) -> FrameSignals:
    """Measure exposure, edge energy, temporal variation, and average hash."""

    if not frames:
        raise ValueError("at least one representative frame is required")
    exposure_scores: list[float] = []
    sharpness_scores: list[float] = []
    hashes: list[int] = []
    for frame in frames:
        with Image.open(frame) as image:
            grayscale = image.convert("L")
            statistics = ImageStat.Stat(grayscale)
            mean = statistics.mean[0]
            histogram = grayscale.histogram()
            pixels = max(1, sum(histogram))
            clipped = (sum(histogram[:5]) + sum(histogram[-5:])) / pixels
            centered = 1 - abs(mean - 127.5) / 127.5
            exposure_scores.append(_unit(centered * (1 - clipped)))

            edges = grayscale.filter(ImageFilter.FIND_EDGES)
            edge_rms = ImageStat.Stat(edges).rms[0] / 255
            sharpness_scores.append(_unit(edge_rms * 4))
            hashes.append(_average_hash(grayscale))

    similarities = [hash_similarity(left, right) for left, right in pairwise(hashes)]
    motion = 0.0 if not similarities else 1 - sum(similarities) / len(similarities)
    exposure = sum(exposure_scores) / len(exposure_scores)
    sharpness = sum(sharpness_scores) / len(sharpness_scores)
    quality = _unit(0.45 * exposure + 0.55 * sharpness)
    return FrameSignals(
        quality_score=quality,
        exposure_score=exposure,
        sharpness_score=sharpness,
        motion_score=_unit(motion * 2),
        average_hash=hashes[len(hashes) // 2],
    )


def hash_similarity(left: int, right: int) -> float:
    """Return normalized similarity of two 64-bit average hashes."""

    return 1 - (left ^ right).bit_count() / 64


def recommended_range(time_range: TimeRange) -> TimeRange:
    """Trim unstable handles conservatively while preserving short shots."""

    duration = time_range.duration_fraction
    if duration <= 1:
        return time_range
    handle = min(Fraction(3, 20), duration / 20)
    return TimeRange(
        start=_time(time_range.start_fraction + handle),
        duration=_time(duration - 2 * handle),
    )


def measure_audio_levels(
    path: Path,
    time_range: TimeRange,
    *,
    executable: str = "ffmpeg",
    timeout_seconds: float = 60,
) -> AudioLevels:
    """Measure mean and peak dBFS with FFmpeg's deterministic volume detector."""

    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-v",
        "info",
        "-ss",
        f"{float(time_range.start_fraction):.6f}",
        "-t",
        f"{float(time_range.duration_fraction):.6f}",
        "-i",
        str(path),
        "-vn",
        "-af",
        "volumedetect",
        "-f",
        "null",
        "-",
    ]
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
            f"ffmpeg executable was not found: {executable!r}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise FFmpegExecutionError(
            "audio analysis", -1, f"timed out after {timeout_seconds:g} seconds"
        ) from error
    if completed.returncode != 0:
        raise FFmpegExecutionError(
            "audio analysis", completed.returncode, completed.stderr
        )
    return parse_volume_detect(completed.stderr)


def parse_volume_detect(stderr: str) -> AudioLevels:
    """Parse the stable summary lines written by FFmpeg ``volumedetect``."""

    mean = _MEAN_VOLUME.search(stderr)
    peak = _MAX_VOLUME.search(stderr)
    if mean is None or peak is None:
        raise FFmpegExecutionError(
            "audio analysis", 0, "volumedetect did not report mean and peak volume"
        )
    return AudioLevels(
        mean_dbfs=_volume(mean.group("value")),
        peak_dbfs=_volume(peak.group("value")),
    )


def location_from_metadata(media: MediaInfo) -> LocationFinding | None:
    """Parse QuickTime/ISO-6709 coordinates or named location metadata."""

    coordinate_items: list[tuple[str, str]] = []
    named_items: list[tuple[str, str]] = []
    for key, value in media.metadata.items():
        lowered = key.lower()
        if any(token in lowered for token in ("location", "gps", "latitude")):
            match = _ISO_6709.search(value)
            if match is not None:
                coordinate_items.append((key, value))
            elif value.strip():
                named_items.append((key, value.strip()))
    if coordinate_items:
        key, value = coordinate_items[0]
        match = _ISO_6709.search(value)
        assert match is not None
        return LocationFinding(
            info=LocationInfo(
                name=named_items[0][1] if named_items else "Embedded GPS location",
                point=GeoPoint(
                    latitude=float(match.group("latitude")),
                    longitude=float(match.group("longitude")),
                ),
            ),
            metadata_keys=tuple(item[0] for item in coordinate_items + named_items),
        )
    if named_items:
        return LocationFinding(
            info=LocationInfo(name=named_items[0][1]),
            metadata_keys=tuple(item[0] for item in named_items),
        )
    return None


def _average_hash(image: Image.Image) -> int:
    resized = image.resize((8, 8))
    values = list(cast(Iterable[int], resized.get_flattened_data()))
    mean = sum(values) / len(values)
    result = 0
    for value in values:
        result = (result << 1) | int(value >= mean)
    return result


def _volume(value: str) -> float:
    return -100.0 if value == "-inf" else float(value)


def _unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _time(value: Fraction) -> RationalTime:
    return RationalTime(value=value.numerator, rate=value.denominator)
