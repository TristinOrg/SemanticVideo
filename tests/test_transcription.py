"""Timed transcription contracts, audio extraction, and OpenAI adapter tests."""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from semanticvideo.analysis.transcription import (
    TranscriptSegmentResult,
    TranscriptWordResult,
    extract_audio,
)
from semanticvideo.errors import (
    FFmpegExecutionError,
    FFmpegNotFoundError,
    TranscriptionProviderError,
)
from semanticvideo.providers import OpenAITranscriber


class FakeTranscriptions:
    def __init__(self, response: object | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.arguments: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> object:
        self.arguments = kwargs
        if self.error is not None:
            raise self.error
        return self.response or SimpleNamespace(text="", language="en")


def fake_client(transcriptions: FakeTranscriptions) -> SimpleNamespace:
    return SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions))


def test_openai_transcriber_normalizes_word_timestamps(tmp_path: Path) -> None:
    response = SimpleNamespace(
        text="hello world",
        language="en",
        words=[
            SimpleNamespace(word="hello", start=0.0, end=0.5),
            SimpleNamespace(word="world", start=0.5, end=1.0),
        ],
        segments=[SimpleNamespace(text="hello world", start=0.0, end=1.0)],
    )
    calls = FakeTranscriptions(response)
    transcriber = OpenAITranscriber(client=fake_client(calls))
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"mp3")

    result = transcriber.transcribe(audio)

    assert result.text == "hello world"
    assert len(result.segments[0].words) == 2
    assert calls.arguments["model"] == "whisper-1"
    assert calls.arguments["timestamp_granularities"] == ["segment", "word"]


def test_openai_transcriber_falls_back_to_word_span_and_reports_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"mp3")
    response = SimpleNamespace(
        text="hello",
        language="en",
        words=[{"word": "hello", "start": 0.0, "end": 0.5}],
        segments=[],
    )
    result = OpenAITranscriber(
        client=fake_client(FakeTranscriptions(response))
    ).transcribe(audio)
    assert len(result.segments) == 1

    failing = OpenAITranscriber(
        client=fake_client(FakeTranscriptions(error=RuntimeError("offline")))
    )
    with pytest.raises(TranscriptionProviderError, match="offline"):
        failing.transcribe(audio)

    with pytest.raises(TranscriptionProviderError, match="requires whisper-1"):
        OpenAITranscriber(
            model="gpt-4o-transcribe", client=fake_client(calls := FakeTranscriptions())
        )
    assert calls.arguments == {}

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(TranscriptionProviderError, match="OPENAI_API_KEY"):
        OpenAITranscriber()


def test_transcript_time_validation() -> None:
    with pytest.raises(ValidationError, match="word end"):
        TranscriptWordResult(text="bad", start_seconds=1, end_seconds=1)
    with pytest.raises(ValidationError, match="inside its segment"):
        TranscriptSegmentResult(
            text="bad",
            start_seconds=1,
            end_seconds=2,
            words=(TranscriptWordResult(text="bad", start_seconds=0, end_seconds=0.5),),
        )


def test_extract_audio_handles_output_and_process_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "audio.mp3"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    with pytest.raises(FFmpegExecutionError, match="no audio"):
        extract_audio(Path("clip.mp4"), output)
    output.write_bytes(b"mp3")
    extract_audio(Path("clip.mp4"), output)

    def missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(FFmpegNotFoundError):
        extract_audio(Path("clip.mp4"), output)

    def timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("ffmpeg", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(FFmpegExecutionError, match="timed out"):
        extract_audio(Path("clip.mp4"), output)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 2, "", "bad"),
    )
    with pytest.raises(FFmpegExecutionError, match="bad"):
        extract_audio(Path("clip.mp4"), output)
