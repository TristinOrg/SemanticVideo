"""Optional word-timestamp transcription through the OpenAI Audio API."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from semanticvideo.analysis.transcription import (
    TranscriptResult,
    TranscriptSegmentResult,
    TranscriptWordResult,
)
from semanticvideo.errors import TranscriptionProviderError
from semanticvideo.schema import AnnotationStatus, ProvenanceSource


class OpenAITranscriber:
    """Transcribe compressed audio with Whisper word and segment timestamps."""

    name: str = "semanticvideo-openai-transcription"
    version: str = "1"
    provider: str | None = "openai"
    source: ProvenanceSource = ProvenanceSource.REMOTE_MODEL
    status: AnnotationStatus = AnnotationStatus.MACHINE_GENERATED

    def __init__(
        self,
        *,
        model: str = "whisper-1",
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model: str | None = model
        if model != "whisper-1":
            raise TranscriptionProviderError(
                "word timestamp transcription currently requires whisper-1"
            )
        if client is not None:
            self._client = client
            return
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise TranscriptionProviderError(
                "OPENAI_API_KEY is required for OpenAI transcription; use an "
                "agent response to work without an API key"
            )
        try:
            module = importlib.import_module("openai")
        except ImportError as error:
            raise TranscriptionProviderError(
                "OpenAI transcription requires `uv sync --extra openai`"
            ) from error
        self._client = module.OpenAI(api_key=key)

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Request verbose JSON and normalize SDK objects into core contracts."""

        try:
            with audio_path.open("rb") as audio_file:
                response = self._client.audio.transcriptions.create(
                    file=audio_file,
                    model=self.model,
                    response_format="verbose_json",
                    timestamp_granularities=["segment", "word"],
                )
            words = tuple(
                _word(item) for item in (getattr(response, "words", None) or ())
            )
            segments = tuple(
                _segment(item, words)
                for item in (getattr(response, "segments", None) or ())
            )
            text = str(getattr(response, "text", "") or "")
            language = str(getattr(response, "language", "und") or "und")
            if not segments and words:
                segments = (
                    TranscriptSegmentResult(
                        text=text or " ".join(item.text for item in words),
                        start_seconds=words[0].start_seconds,
                        end_seconds=words[-1].end_seconds,
                        words=words,
                    ),
                )
            return TranscriptResult(language=language, text=text, segments=segments)
        except TranscriptionProviderError:
            raise
        except Exception as error:
            raise TranscriptionProviderError(
                f"OpenAI transcription failed: {error}"
            ) from error


def _word(item: Any) -> TranscriptWordResult:
    return TranscriptWordResult(
        text=str(_value(item, "word", _value(item, "text", ""))).strip(),
        start_seconds=float(_value(item, "start", 0)),
        end_seconds=float(_value(item, "end", 0)),
    )


def _segment(
    item: Any, words: tuple[TranscriptWordResult, ...]
) -> TranscriptSegmentResult:
    start = float(_value(item, "start", 0))
    end = float(_value(item, "end", 0))
    contained = tuple(
        word
        for word in words
        if start <= word.start_seconds and word.end_seconds <= end
    )
    return TranscriptSegmentResult(
        text=str(_value(item, "text", "")).strip(),
        start_seconds=start,
        end_seconds=end,
        speaker=_optional_text(_value(item, "speaker", None)),
        words=contained,
    )


def _value(item: Any, key: str, default: Any) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
