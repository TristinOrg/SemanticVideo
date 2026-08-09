"""Command-line interface tests."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from semanticvideo.cli.main import build_parser, main
from semanticvideo.errors import MediaNotFoundError
from semanticvideo.schema import (
    MediaInfo,
    RationalTime,
    SemanticVideoDocument,
    VideoStream,
)


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


def test_analyze_writes_one_semantic_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "trip.semantic.json"
    document = SemanticVideoDocument(
        document_id="document.test",
        generated_at=datetime.now(UTC),
        media=media_info(),
    )
    provider = SimpleNamespace()
    monkeypatch.setattr(
        "semanticvideo.cli.main.JsonFileShotDescriber", lambda _path: provider
    )
    monkeypatch.setattr(
        "semanticvideo.cli.main.analyze_video",
        lambda *_args, **_kwargs: document,
    )

    assert (
        main(
            [
                "analyze",
                "trip.mp4",
                "--descriptions",
                "descriptions.json",
                "--include",
                "technical",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8"))["document_id"] == (
        "document.test"
    )
    assert capsys.readouterr().out == f"Wrote {output}\n"


def test_analyze_provider_arguments_are_validated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["analyze", "trip.mp4", "--provider", "json"]) == 1
    assert "requires --descriptions" in capsys.readouterr().err

    assert (
        main(
            [
                "analyze",
                "trip.mp4",
                "--provider",
                "openai",
                "--descriptions",
                "descriptions.json",
            ]
        )
        == 1
    )
    assert "cannot be combined" in capsys.readouterr().err

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["analyze", "trip.mp4"]) == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_scene_threshold_must_be_a_unit_float() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze", "clip.mp4", "--scene-threshold", "1"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze", "clip.mp4", "--frames-per-shot", "10"])
