"""Shared schema configuration."""

from pydantic import BaseModel, ConfigDict


class SemanticModel(BaseModel):
    """Strict, immutable base model for persisted semantic data."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )
