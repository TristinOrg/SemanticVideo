"""Entities referenced by time-aligned annotations."""

from enum import StrEnum

from pydantic import Field

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.media import Identifier


class EntityType(StrEnum):
    """Core entity categories; domain-specific categories use annotations."""

    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    OBJECT = "object"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    FOOD = "food"
    LANDMARK = "landmark"


class Entity(SemanticModel):
    """A stable identity that can be referenced across time and assets."""

    id: Identifier
    type: EntityType
    label: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    external_ids: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None
