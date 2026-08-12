"""Provider-neutral visual-description contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import Field, model_validator

from semanticvideo.schema import AnnotationStatus, ProvenanceSource, TimeRange
from semanticvideo.schema._base import SemanticModel


class MomentDescription(SemanticModel):
    """A time-aligned occurrence inside the source shot."""

    time_range: TimeRange
    summary: str = Field(min_length=1)
    subjects: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    visible_text: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)


class ShotDescription(SemanticModel):
    """Editing-oriented facts visible in representative frames of one shot."""

    summary: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    environment: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    objects: tuple[str, ...] = ()
    visible_text: tuple[str, ...] = ()
    location_hint: str | None = None
    shot_type: str | None = None
    camera_movement: str | None = None
    editorial_role: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    moments: tuple[MomentDescription, ...] = ()

    @property
    def resolved_summary(self) -> str:
        """Prefer the new summary field while accepting existing task responses."""

        return self.summary or self.description or ""

    @model_validator(mode="after")
    def require_summary(self) -> ShotDescription:
        """Require prose for review while structured fields remain authoritative."""

        if self.summary is None and self.description is None:
            raise ValueError("shot description requires summary or legacy description")
        return self


class ShotDescriber(Protocol):
    """Small interface implemented by remote, local, and imported providers."""

    name: str
    version: str
    provider: str | None
    model: str | None
    source: ProvenanceSource
    status: AnnotationStatus

    def describe(
        self, shot_id: str, frames: tuple[Path, ...], *, language: str
    ) -> ShotDescription:
        """Describe one shot from one or more representative images."""
