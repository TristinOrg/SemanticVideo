"""Evidence and provenance for semantic claims."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, JsonValue, model_validator

from semanticvideo.schema._base import SemanticModel


class ProvenanceSource(StrEnum):
    """Broad source categories independent of a particular provider."""

    MANUAL = "manual"
    EMBEDDED_METADATA = "embedded_metadata"
    SIGNAL_ANALYSIS = "signal_analysis"
    LOCAL_MODEL = "local_model"
    REMOTE_MODEL = "remote_model"
    IMPORT = "import"


class GeneratorInfo(SemanticModel):
    """Software or model that produced a claim."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: str | None = None
    model: str | None = None


class Evidence(SemanticModel):
    """A concrete observation supporting an annotation."""

    type: str = Field(min_length=1)
    value: JsonValue | None = None
    artifact_id: str | None = None
    annotation_ids: tuple[str, ...] = ()


class Provenance(SemanticModel):
    """Traceability record for a generated or human-authored claim."""

    source: ProvenanceSource
    generated_at: datetime
    generator: GeneratorInfo | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def require_generator_for_automation(self) -> "Provenance":
        """Automated sources must identify the generating implementation."""

        automated = {
            ProvenanceSource.SIGNAL_ANALYSIS,
            ProvenanceSource.LOCAL_MODEL,
            ProvenanceSource.REMOTE_MODEL,
        }
        if self.source in automated and self.generator is None:
            raise ValueError("automated provenance requires generator details")
        return self
