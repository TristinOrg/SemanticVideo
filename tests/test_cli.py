"""Command-line interface tests."""

import json
from pathlib import Path

import pytest

from semanticvideo.cli.main import build_parser, main
from semanticvideo.errors import MediaNotFoundError
from semanticvideo.schema import MediaInfo, RationalTime, VideoStream


def media_info() -> MediaInfo:
    return MediaInfo(
        id="asset.test",
        uri="clip.mp4",
        duration=RationalTime(value=3, rate=1),
        streams=(
            VideoStream(
                id="stream.video.0",
                index=0,
                codec="h264",
                width=1920,
                height=1080,
            ),
        ),
    )


def test_inspect_prints_scriptable_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "semanticvideo.cli.main.inspect_media", lambda *_args, **_kwargs: media_info()
    )

    assert main(["inspect", "clip.mp4", "--compact"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["id"] == "asset.test"
    assert captured.err == ""


def test_inspect_writes_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "inspection.json"
    monkeypatch.setattr(
        "semanticvideo.cli.main.inspect_media", lambda *_args, **_kwargs: media_info()
    )

    assert main(["inspect", "clip.mp4", "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["duration"] == {
        "value": 3,
        "rate": 1,
    }


def test_inspect_reports_expected_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise MediaNotFoundError("missing clip")

    monkeypatch.setattr("semanticvideo.cli.main.inspect_media", fail)

    assert main(["inspect", "missing.mp4"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: missing clip\n"


def test_output_os_error_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "semanticvideo.cli.main.inspect_media", lambda *_args, **_kwargs: media_info()
    )

    assert main(["inspect", "clip.mp4", "-o", str(tmp_path)]) == 1
    assert "error:" in capsys.readouterr().err


def test_timeout_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["inspect", "clip.mp4", "--timeout", "0"])
