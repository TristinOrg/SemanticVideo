"""Unit tests for ffprobe execution and pure parsing."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from semanticvideo.errors import (
    FFprobeExecutionError,
    FFprobeNotFoundError,
    FFprobeParseError,
    MediaNotFoundError,
)
from semanticvideo.media.ffprobe import inspect_media, parse_ffprobe_json, run_ffprobe
from semanticvideo.schema import VideoStream

FIXTURES = Path(__file__).parent / "fixtures" / "ffprobe"


def load_fixture(name: str) -> dict[str, Any]:
    parsed = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return cast(dict[str, Any], parsed)


def test_parse_standard_mp4() -> None:
    media = parse_ffprobe_json(
        load_fixture("standard_mp4.json"),
        uri="GX010231.MP4",
        asset_id="asset.GX010231",
        modified_at=datetime(2026, 8, 9, tzinfo=UTC),
    )

    assert media.id == "asset.GX010231"
    assert media.duration.seconds == pytest.approx(12.345)
    assert media.file_size == 183_728_192
    assert media.bit_rate == 11_906_168
    assert media.created_at == datetime(2026, 5, 18, 12, 35, 10, tzinfo=UTC)
    assert media.container_format == "mov,mp4,m4a,3gp,3g2,mj2"
    assert media.metadata["major_brand"] == "isom"
    assert len(media.streams) == 2

    video = media.streams[0]
    assert video.kind == "video"
    assert video.frame_rate is not None
    assert (video.frame_rate.numerator, video.frame_rate.denominator) == (30_000, 1001)
    assert video.rotation_degrees == 270
    assert video.bit_rate == 11_800_000
    assert video.variable_frame_rate is False

    audio = media.streams[1]
    assert audio.kind == "audio"
    assert audio.sample_rate == 48_000
    assert audio.bit_rate == 128_000
    assert audio.language == "jpn"


def test_parse_video_only_with_duration_ts_fallback() -> None:
    media = parse_ffprobe_json(
        load_fixture("video_only_duration_ts.json"), uri="clip.mkv"
    )

    assert media.duration.seconds == 3
    assert media.file_size == 2048
    assert media.created_at == datetime(2026, 5, 18, 12, 35, 10, tzinfo=UTC)
    assert media.bit_rate == 5461
    video = media.streams[0]
    assert isinstance(video, VideoStream)
    assert video.rotation_degrees == 90
    assert video.variable_frame_rate is True


def test_parse_uses_long_codec_name_and_direct_stream_duration() -> None:
    payload = {
        "streams": [
            {
                "index": "0",
                "codec_long_name": "Example codec",
                "codec_type": "video",
                "width": "640",
                "height": "360",
                "duration": "1.25",
                "avg_frame_rate": "0/0",
                "r_frame_rate": "0/0",
                "time_base": "1/1000",
            }
        ]
    }

    media = parse_ffprobe_json(payload, uri="clip.example")

    assert media.duration.seconds == 1.25
    video = media.streams[0]
    assert isinstance(video, VideoStream)
    assert video.codec == "Example codec"
    assert video.frame_rate is None
    assert video.variable_frame_rate is None


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "streams array"),
        ({"streams": ["invalid"]}, "stream must be an object"),
        (
            {"streams": [{"index": 0, "codec_type": "video", "width": 1, "height": 1}]},
            "positive duration",
        ),
        (
            {
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "audio",
                        "sample_rate": 48000,
                        "channels": 2,
                        "duration": 1,
                    }
                ]
            },
            "at least one video stream",
        ),
        (
            {
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "width": 0,
                        "height": 1,
                        "duration": 1,
                    }
                ]
            },
            "positive integer",
        ),
        (
            {
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "width": 1,
                        "height": 1,
                        "duration": "invalid",
                    }
                ]
            },
            "invalid duration",
        ),
        (
            {
                "format": {"duration": 1},
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "width": 1,
                        "height": 1,
                        "avg_frame_rate": "broken",
                    }
                ],
            },
            "invalid rational",
        ),
        (
            {
                "format": {"duration": 1},
                "streams": [
                    {
                        "index": -1,
                        "codec_type": "video",
                        "width": 1,
                        "height": 1,
                    }
                ],
            },
            "stream failed schema validation",
        ),
    ],
)
def test_invalid_ffprobe_payloads_are_rejected(
    payload: dict[str, Any], message: str
) -> None:
    with pytest.raises(FFprobeParseError, match=message):
        parse_ffprobe_json(payload, uri="invalid.mp4")


def test_run_ffprobe_decodes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str] = []

    def fake_run(command: list[str], **_: Any) -> SimpleNamespace:
        observed.extend(command)
        return SimpleNamespace(returncode=0, stdout='{"streams": []}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert run_ffprobe(Path("clip.mp4"), executable="custom-ffprobe") == {"streams": []}
    assert observed[0] == "custom-ffprobe"
    assert observed[-1] == "clip.mp4"


def test_run_ffprobe_maps_expected_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_: Any, **__: Any) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(FFprobeNotFoundError, match="was not found"):
        run_ffprobe(Path("clip.mp4"))

    def timeout(*_: Any, **__: Any) -> None:
        raise subprocess.TimeoutExpired("ffprobe", 2)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(FFprobeExecutionError, match="timed out"):
        run_ffprobe(Path("clip.mp4"), timeout_seconds=2)


@pytest.mark.parametrize(
    ("result", "error_type", "message"),
    [
        (
            SimpleNamespace(returncode=7, stdout="", stderr="bad input"),
            FFprobeExecutionError,
            "bad input",
        ),
        (
            SimpleNamespace(returncode=0, stdout="not-json", stderr=""),
            FFprobeParseError,
            "invalid JSON",
        ),
        (
            SimpleNamespace(returncode=0, stdout="[]", stderr=""),
            FFprobeParseError,
            "root must be an object",
        ),
    ],
)
def test_run_ffprobe_rejects_bad_results(
    monkeypatch: pytest.MonkeyPatch,
    result: SimpleNamespace,
    error_type: type[Exception],
    message: str,
) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: result)
    with pytest.raises(error_type, match=message):
        run_ffprobe(Path("clip.mp4"))


def test_inspect_media_requires_file(tmp_path: Path) -> None:
    with pytest.raises(MediaNotFoundError, match="does not exist"):
        inspect_media(tmp_path / "missing.mp4")


def test_inspect_media_adds_filesystem_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_path = tmp_path / "clip.mp4"
    media_path.write_bytes(b"fixture")
    payload = load_fixture("standard_mp4.json")
    monkeypatch.setattr(
        "semanticvideo.media.ffprobe.run_ffprobe", lambda *_args, **_kwargs: payload
    )

    media = inspect_media(media_path)

    assert media.file_size == 7
    assert media.modified_at is not None
    assert media.id.startswith("asset.")
    assert inspect_media(media_path).id == media.id
