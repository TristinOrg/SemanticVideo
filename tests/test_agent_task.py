"""Agent-native task bundle and response tests."""

import json
from pathlib import Path

import pytest

from semanticvideo.analysis import agent_task
from semanticvideo.errors import AgentTaskError
from semanticvideo.providers import AgentResponseProvider
from semanticvideo.schema import AudioStream, MediaInfo, RationalTime, VideoStream


def task_media(path: Path) -> MediaInfo:
    return MediaInfo(
        id="asset.task",
        uri=str(path),
        duration=RationalTime(value=4, rate=1),
        streams=(
            VideoStream(
                id="stream.video.0",
                index=0,
                codec="h264",
                width=100,
                height=100,
            ),
            AudioStream(
                id="stream.audio.1",
                index=1,
                codec="aac",
                sample_rate=16000,
                channels=1,
            ),
        ),
    )


def test_prepare_agent_task_writes_portable_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"clip")
    output = tmp_path / "task"
    monkeypatch.setattr(
        agent_task, "inspect_media", lambda *_args, **_kwargs: task_media(video)
    )
    monkeypatch.setattr(
        agent_task, "detect_shot_boundaries", lambda *_args, **_kwargs: ()
    )

    def frame(
        _path: Path, _timestamp: RationalTime, target: Path, **_kwargs: object
    ) -> None:
        target.write_bytes(b"jpeg")

    def audio(_path: Path, target: Path, **_kwargs: object) -> None:
        target.write_bytes(b"mp3")

    monkeypatch.setattr(agent_task, "extract_frame", frame)
    monkeypatch.setattr(agent_task, "extract_audio", audio)

    bundle = agent_task.prepare_agent_task(video, output, language="zh-CN")

    assert len(bundle.shots) == 1
    assert len(bundle.shots[0].frame_uris) == 3
    assert bundle.audio_uri == "audio.mp3"
    assert (output / "task.json").is_file()
    assert (output / "response.schema.json").is_file()
    template = json.loads((output / "response.template.json").read_text())
    assert template["shots"]["shot.0001"]["summary"].startswith("TODO")

    with pytest.raises(AgentTaskError, match="not empty"):
        agent_task.prepare_agent_task(video, output)


def test_agent_response_provider_exposes_all_modalities(tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    response.write_text(
        json.dumps(
            {
                "response_version": "0.1.0",
                "shots": {"shot.0001": {"summary": "Traveler enters a train"}},
                "transcript": {
                    "language": "en",
                    "text": "hello",
                    "segments": [
                        {
                            "text": "hello",
                            "start_seconds": 0,
                            "end_seconds": 1,
                        }
                    ],
                },
                "location": {"name": "Tokyo"},
            }
        ),
        encoding="utf-8",
    )
    provider = AgentResponseProvider(response)

    assert provider.describe("shot.0001", (), language="en").summary is not None
    assert provider.transcript is not None
    assert provider.location is not None
    with pytest.raises(AgentTaskError, match="no description"):
        provider.describe("shot.0002", (), language="en")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}", encoding="utf-8")
    with pytest.raises(AgentTaskError, match="invalid agent response"):
        AgentResponseProvider(invalid)
