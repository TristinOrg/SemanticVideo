"""FFmpeg edit-plan renderer tests."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from semanticvideo.editing import find_edit_plan, render_edit_plan
from semanticvideo.errors import RenderError
from semanticvideo.schema import EditClip, EditPlan, SemanticVideoDocument


def _document(source: Path, *, audio: bool = True) -> SemanticVideoDocument:
    streams: list[dict[str, Any]] = [
        {
            "kind": "video",
            "id": "stream.video.0",
            "index": 0,
            "codec": "h264",
            "width": 1920,
            "height": 1080,
        }
    ]
    if audio:
        streams.append(
            {
                "kind": "audio",
                "id": "stream.audio.0",
                "index": 1,
                "codec": "aac",
                "sample_rate": 48000,
                "channels": 2,
            }
        )
    return SemanticVideoDocument.model_validate(
        {
            "document_id": "document.test",
            "generated_at": datetime.now(UTC),
            "media": {
                "id": "asset.test",
                "uri": str(source),
                "duration": {"value": 10, "rate": 1},
                "streams": streams,
            },
            "segments": [
                {
                    "id": "shot.1",
                    "kind": "shot",
                    "time_range": {
                        "start": {"value": 1, "rate": 1},
                        "duration": {"value": 4, "rate": 1},
                    },
                }
            ],
        }
    )


def _plan(plan_id: str = "edit.plan.0001") -> EditPlan:
    return EditPlan(
        id=plan_id,
        name="test",
        generated_at=datetime.now(UTC),
        strategy="test",
        clips=(
            EditClip(
                id="edit.clip.0001",
                source_segment_id="shot.1",
                source_range={
                    "start": {"value": 3, "rate": 2},
                    "duration": {"value": 2, "rate": 1},
                },
                order=0,
            ),
        ),
    )


@pytest.mark.parametrize("audio", [True, False])
def test_renderer_builds_one_safe_ffmpeg_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audio: bool
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "cut.mp4"
    observed: list[str] = []

    def run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        observed.extend(command)
        Path(command[-1]).write_bytes(b"rendered")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("semanticvideo.editing.renderer.subprocess.run", run)

    assert render_edit_plan(_document(source, audio=audio), _plan(), output) == output
    assert output.read_bytes() == b"rendered"
    filter_graph = observed[observed.index("-filter_complex") + 1]
    assert "trim=start=1.500000:end=3.500000" in filter_graph
    assert ("atrim=" in filter_graph) is audio
    assert ("[outa]" in observed) is audio
    assert observed[0] == "ffmpeg"
    assert "-nostdin" in observed


def test_renderer_rejects_unsafe_or_missing_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    output = tmp_path / "cut.mp4"
    with pytest.raises(RenderError, match="does not exist"):
        render_edit_plan(_document(missing), _plan(), output)

    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output.write_bytes(b"existing")
    with pytest.raises(RenderError, match="already exists"):
        render_edit_plan(_document(source), _plan(), output)
    with pytest.raises(RenderError, match="cannot overwrite source"):
        render_edit_plan(_document(source), _plan(), source, overwrite=True)


@pytest.mark.parametrize("failure", ["missing", "timeout", "returncode", "empty"])
def test_renderer_cleans_up_expected_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    output = tmp_path / "cut.mp4"

    def run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        if failure == "missing":
            raise FileNotFoundError
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if failure == "returncode":
            return SimpleNamespace(returncode=2, stderr="bad filter")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("semanticvideo.editing.renderer.subprocess.run", run)
    message = {
        "missing": "was not found",
        "timeout": "timed out",
        "returncode": "bad filter",
        "empty": "without producing",
    }[failure]
    with pytest.raises(RenderError, match=message):
        render_edit_plan(_document(source), _plan(), output)
    assert not output.exists()
    assert not list(tmp_path.glob(".cut.*.mp4"))


def test_find_edit_plan_resolves_latest_or_explicit(tmp_path: Path) -> None:
    document = _document(tmp_path / "source.mp4")
    with pytest.raises(RenderError, match="no edit plan"):
        find_edit_plan(document, None)

    first = _plan()
    second = _plan("edit.plan.0002").model_copy(
        update={
            "clips": (_plan().clips[0].model_copy(update={"id": "edit.clip.0002"}),)
        }
    )
    document = document.model_copy(update={"edit_plans": (first, second)})
    assert find_edit_plan(document, None).id == "edit.plan.0002"
    assert find_edit_plan(document, "edit.plan.0001") == first
    with pytest.raises(RenderError, match="no edit plan 'unknown'"):
        find_edit_plan(document, "unknown")
