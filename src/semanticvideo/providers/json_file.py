"""Import reviewed or externally generated shot descriptions from JSON."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from semanticvideo.analysis.types import ShotDescription
from semanticvideo.errors import DescriptionProviderError
from semanticvideo.schema import AnnotationStatus, ProvenanceSource


class JsonFileShotDescriber:
    """Resolve shot descriptions from a JSON object keyed by shot ID."""

    name: str = "semanticvideo-json-import"
    version: str = "1"
    provider: str | None = None
    model: str | None = None
    source: ProvenanceSource = ProvenanceSource.IMPORT
    status: AnnotationStatus = AnnotationStatus.HUMAN_AUTHORED

    def __init__(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DescriptionProviderError(
                f"cannot read description JSON {path}: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise DescriptionProviderError(
                "description JSON must be an object keyed by shot ID"
            )
        self._descriptions = payload

    def describe(
        self, shot_id: str, frames: tuple[Path, ...], *, language: str
    ) -> ShotDescription:
        """Return and validate the description assigned to ``shot_id``."""

        del frames, language
        if shot_id not in self._descriptions:
            raise DescriptionProviderError(
                f"description JSON has no entry for {shot_id!r}"
            )
        try:
            return ShotDescription.model_validate(self._descriptions[shot_id])
        except ValidationError as error:
            raise DescriptionProviderError(
                f"invalid description for {shot_id!r}: {error}"
            ) from error
