"""Command-line interface tests."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from semanticvideo.cli.main import build_parser, main
from semanticvideo.errors import MediaNotFoundError
from semanticvideo.schema import (
    EditClip,
    EditPlan,
    MediaInfo,
    RationalTime,
    Segment,
    SemanticVideoDocument,
    TimeRange,
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


def plannable_document() -> SemanticVideoDocument:
    time_range = TimeRange(
        start=RationalTime(value=0, rate=1),
        duration=RationalTime(value=3, rate=1),
    )
    return SemanticVideoDocument(
        document_id="document.test",
        generated_at=datetime.now(UTC),
        media=media_info(),
        segments=(Segment(id="shot.1", kind="shot", time_range=time_range),),
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


def test_prepare_agent_reports_task_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "task"
    monkeypatch.setattr(
        "semanticvideo.cli.main.prepare_agent_task",
        lambda *_args, **_kwargs: SimpleNamespace(shots=(1, 2)),
    )

    assert main(["prepare-agent", "clip.mp4", "--output", str(output)]) == 0
    assert capsys.readouterr().out == f"Wrote agent task with 2 shots to {output}\n"


def test_agent_provider_requires_response(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", "clip.mp4", "--provider", "agent"]) == 1
    assert "requires --agent-response" in capsys.readouterr().err


def test_plan_updates_manifest_atomically(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "clip.semantic.json"
    manifest.write_text(plannable_document().model_dump_json(), encoding="utf-8")

    assert (
        main(
            [
                "plan",
                str(manifest),
                "--target-duration",
                "2",
                "--maximum-clip-duration",
                "1",
            ]
        )
        == 0
    )
    restored = SemanticVideoDocument.model_validate_json(
        manifest.read_text(encoding="utf-8")
    )
    assert restored.edit_plans[0].duration_seconds == 1
    assert "with 1 clips (1.000s)" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.tmp"))


def test_render_uses_latest_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    document = plannable_document()
    segment = document.segments[0]
    plan = EditPlan(
        id="edit.plan.0001",
        name="test",
        generated_at=datetime.now(UTC),
        strategy="test",
        clips=(
            EditClip(
                id="edit.clip.0001",
                source_segment_id=segment.id,
                source_range=segment.time_range,
                order=0,
            ),
        ),
    )
    document = document.model_copy(update={"edit_plans": (plan,)})
    manifest = tmp_path / "clip.semantic.json"
    manifest.write_text(document.model_dump_json(), encoding="utf-8")
    output = tmp_path / "cut.mp4"
    observed: dict[str, object] = {}

    def render(
        _document: SemanticVideoDocument,
        selected: EditPlan,
        path: Path,
        **options: object,
    ) -> Path:
        observed.update(plan=selected, path=path, options=options)
        return path

    monkeypatch.setattr("semanticvideo.cli.main.render_edit_plan", render)

    assert main(["render", str(manifest), "-o", str(output)]) == 0
    assert observed["plan"] == plan
    assert observed["path"] == output
    assert capsys.readouterr().out == f"Rendered {plan.id} to {output}\n"


def test_gaps_reports_when_focused_inspection_is_needed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "clip.semantic.json"
    manifest.write_text(plannable_document().model_dump_json(), encoding="utf-8")
    assert main(["gaps", str(manifest), "--field", "ocr"]) == 1
    assert json.loads(capsys.readouterr().out) == {"gaps": ["ocr"]}

    assert (
        main(
            [
                "gaps",
                str(manifest),
                "--field",
                "ocr",
                "--start",
                "1",
            ]
        )
        == 1
    )
    assert "supplied together" in capsys.readouterr().err


def test_enrich_merges_supplement_atomically(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "clip.semantic.json"
    manifest.write_text(plannable_document().model_dump_json(), encoding="utf-8")
    supplement = tmp_path / "supplement.json"
    supplement.write_text(
        json.dumps(
            {
                "capabilities": [
                    {
                        "name": "ocr",
                        "status": "complete",
                        "analyzed_fields": ["visible_text"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert main(["enrich", str(manifest), str(supplement)]) == 0
    restored = SemanticVideoDocument.model_validate_json(
        manifest.read_text(encoding="utf-8")
    )
    assert restored.capabilities[0].name == "ocr"
    assert capsys.readouterr().out == f"Enriched {manifest}\n"
