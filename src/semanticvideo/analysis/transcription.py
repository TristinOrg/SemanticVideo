"""Provider-neutral timed transcription and audio extraction contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from pydantic import Field, model_validator

from semanticvideo.errors import FFmpegExecutionError, FFmpegNotFoundError
from semanticvideo.schema import AnnotationStatus, ProvenanceSource
from semanticvideo.schema._base import SemanticModel


class TranscriptWordResult(SemanticModel):
    text: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> TranscriptWordResult:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("transcript word end must follow start")
        return self


class TranscriptSegmentResult(SemanticModel):
    text: str = Field(min_length=1)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    speaker: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    words: tuple[TranscriptWordResult, ...] = ()

    @model_validator(mode="after")
    def validate_segment_times(self) -> TranscriptSegmentResult:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("transcript segment end must follow start")
        for word in self.words:
            if not (
                self.start_seconds <= word.start_seconds
                and word.end_seconds <= self.end_seconds
            ):
                raise ValueError("transcript word must be inside its segment")
        return self


class TranscriptResult(SemanticModel):
    language: str = Field(min_length=2)
    text: str = ""
    segments: tuple[TranscriptSegmentResult, ...] = ()


class Transcriber(Protocol):
    name: str
    version: str
    provider: str | None
    model: str | None
    source: ProvenanceSource
    status: AnnotationStatus

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Transcribe one compressed local audio file with source-relative times."""


def extract_audio(
    path: Path,
    output: Path,
    *,
    executable: str = "ffmpeg",
    timeout_seconds: float = 300,
) -> None:
    """Create a small mono MP3 suitable for agents and transcription APIs."""

    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(output),
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
            "audio extraction", -1, f"timed out after {timeout_seconds:g} seconds"
        ) from error
    if completed.returncode != 0:
        raise FFmpegExecutionError(
            "audio extraction", completed.returncode, completed.stderr
        )
    if not output.is_file() or output.stat().st_size == 0:
        raise FFmpegExecutionError("audio extraction", 0, "no audio file was written")
