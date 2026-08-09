"""Optional OpenAI Responses API visual-description provider."""

from __future__ import annotations

import base64
import importlib
import os
from pathlib import Path
from typing import Any

from semanticvideo.analysis.types import ShotDescription
from semanticvideo.errors import DescriptionProviderError
from semanticvideo.schema import AnnotationStatus, ProvenanceSource


class OpenAIShotDescriber:
    """Describe representative frames with structured OpenAI vision output."""

    name: str = "semanticvideo-openai"
    version: str = "1"
    provider: str | None = "openai"
    source: ProvenanceSource = ProvenanceSource.REMOTE_MODEL
    status: AnnotationStatus = AnnotationStatus.MACHINE_GENERATED

    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model: str | None = model
        if client is not None:
            self._client = client
            return
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise DescriptionProviderError(
                "OPENAI_API_KEY is required for --provider openai; alternatively "
                "use --descriptions with a reviewed JSON file"
            )
        try:
            module = importlib.import_module("openai")
        except ImportError as error:
            raise DescriptionProviderError(
                "OpenAI provider requires the optional dependency; run "
                "`uv sync --extra openai`"
            ) from error
        self._client = module.OpenAI(api_key=key)

    def describe(
        self, shot_id: str, frames: tuple[Path, ...], *, language: str
    ) -> ShotDescription:
        """Send representative JPEGs and validate one structured response."""

        if not frames:
            raise DescriptionProviderError(f"no representative frames for {shot_id}")
        content: list[dict[str, str]] = [
            {
                "type": "input_text",
                "text": _prompt(shot_id, language),
            }
        ]
        for frame in frames:
            encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{encoded}",
                    "detail": "low",
                }
            )
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "shot_description",
                        "strict": True,
                        "schema": _strict_schema(),
                    }
                },
            )
            output_text = getattr(response, "output_text", None)
            if not isinstance(output_text, str) or not output_text.strip():
                raise DescriptionProviderError(
                    f"OpenAI returned no structured text for {shot_id}"
                )
            return ShotDescription.model_validate_json(output_text)
        except DescriptionProviderError:
            raise
        except Exception as error:
            raise DescriptionProviderError(
                f"OpenAI description failed for {shot_id}: {error}"
            ) from error


def _prompt(shot_id: str, language: str) -> str:
    return (
        f"Describe video shot {shot_id} for a professional editor. "
        "Only report facts visible in the supplied representative frame(s); do not "
        "identify unknown people or guess an exact location. Make description a "
        f"concise summary in language {language}. Set legacy description to null. "
        "Use empty arrays or null for "
        "unknown fields. Describe environment, subjects, actions, important objects, "
        "visible text, shot type, camera movement when inferable, and likely editorial "
        "role. Confidence is a number from 0 to 1."
    )


def _strict_schema() -> dict[str, Any]:
    """Adapt Pydantic defaults to the API's all-properties-required subset."""

    schema = ShotDescription.model_json_schema()

    def normalize(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
                node["additionalProperties"] = False
            for value in node.values():
                normalize(value)
        elif isinstance(node, list):
            for value in node:
                normalize(value)

    normalize(schema)
    return schema
