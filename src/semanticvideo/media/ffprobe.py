"""Execute ffprobe safely and parse its JSON output into core schema models."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from semanticvideo.errors import (
    FFprobeExecutionError,
    FFprobeNotFoundError,
    FFprobeParseError,
    MediaNotFoundError,
)
from semanticvideo.schema.media import (
    AudioStream,
    MediaInfo,
    Stream,
    SubtitleStream,
    VideoStream,
)
from semanticvideo.schema.time import RationalRate, RationalTime

FFPROBE_ARGUMENTS = (
    "-v",
    "error",
    "-print_format",
    "json",
    "-show_format",
    "-show_streams",
)


def run_ffprobe(
    path: Path,
    *,
    executable: str = "ffprobe",
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    """Run ffprobe without a shell and return its decoded JSON object."""

    command = [executable, *FFPROBE_ARGUMENTS, str(path)]
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
        raise FFprobeNotFoundError(
            f"ffprobe executable was not found: {executable!r}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise FFprobeExecutionError(
            -1, f"ffprobe timed out after {timeout_seconds:g} seconds"
        ) from error

    if completed.returncode != 0:
        raise FFprobeExecutionError(completed.returncode, completed.stderr)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise FFprobeParseError(f"ffprobe returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise FFprobeParseError("ffprobe JSON root must be an object")
    return payload


def inspect_media(
    path: str | Path,
    *,
    executable: str = "ffprobe",
    timeout_seconds: float = 60,
) -> MediaInfo:
    """Inspect one local media file and return validated technical metadata."""

    media_path = Path(path)
    if not media_path.is_file():
        raise MediaNotFoundError(f"media file does not exist: {media_path}")

    payload = run_ffprobe(
        media_path,
        executable=executable,
        timeout_seconds=timeout_seconds,
    )
    stat = media_path.stat()
    return parse_ffprobe_json(
        payload,
        uri=str(media_path),
        asset_id=_asset_id(media_path),
        file_size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def parse_ffprobe_json(
    payload: Mapping[str, Any],
    *,
    uri: str,
    asset_id: str | None = None,
    file_size: int | None = None,
    modified_at: datetime | None = None,
) -> MediaInfo:
    """Purely parse an ffprobe payload without starting external processes."""

    raw_streams = payload.get("streams")
    if not isinstance(raw_streams, Sequence) or isinstance(raw_streams, (str, bytes)):
        raise FFprobeParseError("ffprobe output must contain a streams array")

    streams: list[Stream] = []
    for raw_stream in raw_streams:
        if not isinstance(raw_stream, Mapping):
            raise FFprobeParseError("each ffprobe stream must be an object")
        try:
            parsed = _parse_stream(raw_stream)
        except ValidationError as error:
            raise FFprobeParseError(
                f"ffprobe stream failed schema validation: {error}"
            ) from error
        if parsed is not None:
            streams.append(parsed)

    raw_format = payload.get("format")
    format_info = raw_format if isinstance(raw_format, Mapping) else {}
    duration = _parse_duration(format_info, raw_streams)
    tags = _string_mapping(format_info.get("tags"))

    effective_size = file_size
    if effective_size is None:
        effective_size = _optional_int(format_info.get("size"))

    try:
        return MediaInfo(
            id=asset_id or _asset_id_from_uri(uri),
            uri=uri,
            duration=duration,
            file_size=effective_size,
            modified_at=modified_at,
            created_at=_find_creation_time(tags, raw_streams),
            container_format=_optional_text(format_info.get("format_name")),
            bit_rate=_optional_int(format_info.get("bit_rate")),
            streams=tuple(streams),
            metadata=tags,
        )
    except ValidationError as error:
        raise FFprobeParseError(
            f"ffprobe metadata failed schema validation: {error}"
        ) from error


def _parse_stream(raw: Mapping[str, Any]) -> Stream | None:
    codec_type = _optional_text(raw.get("codec_type"))
    index = _required_int(raw, "index")
    stream_id = f"stream.{codec_type or 'unknown'}.{index}"
    codec = (
        _optional_text(raw.get("codec_name"))
        or _optional_text(raw.get("codec_long_name"))
        or "unknown"
    )
    tags = _string_mapping(raw.get("tags"))

    if codec_type == "video":
        return VideoStream(
            id=stream_id,
            index=index,
            codec=codec,
            bit_rate=_optional_int(raw.get("bit_rate")),
            width=_required_int(raw, "width", positive=True),
            height=_required_int(raw, "height", positive=True),
            pixel_format=_optional_text(raw.get("pix_fmt")),
            frame_rate=_parse_ratio(raw.get("avg_frame_rate")),
            time_base=_parse_ratio(raw.get("time_base")),
            rotation_degrees=_parse_rotation(raw, tags),
            sample_aspect_ratio=_parse_ratio(raw.get("sample_aspect_ratio")),
            color_primaries=_optional_text(raw.get("color_primaries")),
            color_transfer=_optional_text(raw.get("color_transfer")),
            color_space=_optional_text(raw.get("color_space")),
            variable_frame_rate=_detect_variable_frame_rate(raw),
        )
    if codec_type == "audio":
        return AudioStream(
            id=stream_id,
            index=index,
            codec=codec,
            bit_rate=_optional_int(raw.get("bit_rate")),
            sample_rate=_required_int(raw, "sample_rate", positive=True),
            channels=_required_int(raw, "channels", positive=True),
            channel_layout=_optional_text(raw.get("channel_layout")),
            language=tags.get("language"),
            time_base=_parse_ratio(raw.get("time_base")),
        )
    if codec_type == "subtitle":
        return SubtitleStream(
            id=stream_id,
            index=index,
            codec=codec,
            language=tags.get("language"),
        )
    return None


def _parse_duration(
    format_info: Mapping[str, Any], raw_streams: Sequence[Any]
) -> RationalTime:
    format_duration = _decimal_time(format_info.get("duration"))
    if format_duration is not None and format_duration.value > 0:
        return format_duration

    candidates: list[RationalTime] = []
    for raw in raw_streams:
        if not isinstance(raw, Mapping):
            continue
        direct = _decimal_time(raw.get("duration"))
        if direct is not None and direct.value > 0:
            candidates.append(direct)
            continue
        duration_ts = _optional_int(raw.get("duration_ts"))
        time_base = _parse_ratio(raw.get("time_base"))
        if duration_ts is not None and duration_ts > 0 and time_base is not None:
            fraction = Fraction(
                duration_ts * time_base.numerator, time_base.denominator
            )
            candidates.append(_fraction_time(fraction))

    if not candidates:
        raise FFprobeParseError("ffprobe output does not contain a positive duration")
    return max(candidates, key=lambda item: item.fraction)


def _parse_ratio(value: Any) -> RationalRate | None:
    text = _optional_text(value)
    if text is None or text in {"0/0", "N/A"}:
        return None
    separator = "/" if "/" in text else ":" if ":" in text else None
    if separator is None:
        try:
            fraction = Fraction(text)
        except (ValueError, ZeroDivisionError) as error:
            raise FFprobeParseError(f"invalid rational value: {text!r}") from error
    else:
        left, right = text.split(separator, maxsplit=1)
        try:
            fraction = Fraction(int(left), int(right))
        except (ValueError, ZeroDivisionError) as error:
            raise FFprobeParseError(f"invalid rational value: {text!r}") from error
    if fraction <= 0:
        return None
    return RationalRate(numerator=fraction.numerator, denominator=fraction.denominator)


def _decimal_time(value: Any) -> RationalTime | None:
    text = _optional_text(value)
    if text is None or text == "N/A":
        return None
    try:
        decimal = Decimal(text)
    except InvalidOperation as error:
        raise FFprobeParseError(f"invalid duration value: {text!r}") from error
    if not decimal.is_finite() or decimal < 0:
        raise FFprobeParseError(f"invalid duration value: {text!r}")
    return _fraction_time(Fraction(decimal))


def _fraction_time(value: Fraction) -> RationalTime:
    return RationalTime(value=value.numerator, rate=value.denominator)


def _required_int(raw: Mapping[str, Any], key: str, *, positive: bool = False) -> int:
    value = _optional_int(raw.get(key))
    if value is None or (positive and value <= 0):
        qualifier = "positive " if positive else ""
        raise FFprobeParseError(f"stream field {key!r} must be a {qualifier}integer")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _find_creation_time(
    format_tags: Mapping[str, str], raw_streams: Sequence[Any]
) -> datetime | None:
    candidates = [format_tags.get("creation_time")]
    candidates.extend(
        _string_mapping(raw.get("tags")).get("creation_time")
        for raw in raw_streams
        if isinstance(raw, Mapping)
    )
    for candidate in candidates:
        parsed = _parse_datetime(candidate)
        if parsed is not None:
            return parsed
    return None


def _parse_rotation(raw: Mapping[str, Any], tags: Mapping[str, str]) -> float:
    values: list[Any] = []
    side_data = raw.get("side_data_list")
    if isinstance(side_data, Sequence) and not isinstance(side_data, (str, bytes)):
        for item in side_data:
            if isinstance(item, Mapping) and "rotation" in item:
                values.append(item["rotation"])
    if "rotate" in tags:
        values.append(tags["rotate"])
    for value in values:
        try:
            rotation = float(value) % 360
        except (TypeError, ValueError):
            continue
        return 0.0 if rotation == 360 else rotation
    return 0.0


def _detect_variable_frame_rate(raw: Mapping[str, Any]) -> bool | None:
    average = _parse_ratio(raw.get("avg_frame_rate"))
    nominal = _parse_ratio(raw.get("r_frame_rate"))
    if average is None or nominal is None:
        return None
    return average.fraction != nominal.fraction


def _asset_id(path: Path) -> str:
    return _asset_id_from_uri(path.resolve().as_uri())


def _asset_id_from_uri(uri: str) -> str:
    # UUIDv5 makes the ID deterministic without hashing the potentially huge media file.
    digest = uuid5(NAMESPACE_URL, uri).hex
    return f"asset.{digest}"
