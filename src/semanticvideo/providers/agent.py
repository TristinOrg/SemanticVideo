"""Import a validated response produced by Codex or another external agent."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from semanticvideo.analysis.agent_task import AgentResponse
from semanticvideo.analysis.transcription import TranscriptResult
from semanticvideo.analysis.types import ShotDescription
from semanticvideo.errors import AgentTaskError
from semanticvideo.schema import (
    AnnotationStatus,
    LocationInfo,
    ProvenanceSource,
)


class AgentResponseProvider:
    """Use one agent response as visual, transcript, and location input."""

    name: str = "semanticvideo-agent-response"
    version: str = "1"
    provider: str | None = "external-agent"
    model: str | None = None
    source: ProvenanceSource = ProvenanceSource.IMPORT
    status: AnnotationStatus = AnnotationStatus.MACHINE_GENERATED

    def __init__(self, path: Path) -> None:
        try:
            self.response = AgentResponse.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise AgentTaskError(f"invalid agent response {path}: {error}") from error

    @property
    def transcript(self) -> TranscriptResult | None:
        return self.response.transcript

    @property
    def location(self) -> LocationInfo | None:
        return self.response.location

    def describe(
        self, shot_id: str, frames: tuple[Path, ...], *, language: str
    ) -> ShotDescription:
        del frames, language
        try:
            return self.response.shots[shot_id]
        except KeyError as error:
            raise AgentTaskError(
                f"agent response has no description for {shot_id!r}"
            ) from error
