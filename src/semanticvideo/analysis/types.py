"""Provider-neutral visual-description contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import Field

from semanticvideo.schema import AnnotationStatus, ProvenanceSource
from semanticvideo.schema._base import SemanticModel


class ShotDescription(SemanticModel):
    """Editing-oriented facts visible in representative frames of one shot."""

    description: str = Field(min_length=1)
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
