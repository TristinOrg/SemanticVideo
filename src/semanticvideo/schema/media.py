"""Source media identity and stream metadata."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from semanticvideo.schema._base import SemanticModel
from semanticvideo.schema.time import RationalRate, RationalTime

Identifier = Annotated[
    str, StringConstraints(min_length=1, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class Checksum(SemanticModel):
    """A content checksum used to detect stale sidecar data."""

    algorithm: Literal["sha256"] = "sha256"
    value: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class VideoStream(SemanticModel):
    """Technical metadata for one video stream."""

    kind: Literal["video"] = "video"
    id: Identifier
    index: int = Field(ge=0)
    codec: str = Field(min_length=1)
    bit_rate: int | None = Field(default=None, ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    pixel_format: str | None = None
    frame_rate: RationalRate | None = None
    time_base: RationalRate | None = None
    rotation_degrees: float = Field(default=0, ge=0, lt=360)
    sample_aspect_ratio: RationalRate | None = None
    color_primaries: str | None = None
    color_transfer: str | None = None
    color_space: str | None = None
    variable_frame_rate: bool | None = None


class AudioStream(SemanticModel):
    """Technical metadata for one audio stream."""

    kind: Literal["audio"] = "audio"
    id: Identifier
    index: int = Field(ge=0)
    codec: str = Field(min_length=1)
    bit_rate: int | None = Field(default=None, ge=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    channel_layout: str | None = None
    language: str | None = None
    time_base: RationalRate | None = None


class SubtitleStream(SemanticModel):
    """Technical metadata for one embedded subtitle stream."""

    kind: Literal["subtitle"] = "subtitle"
    id: Identifier
    index: int = Field(ge=0)
    codec: str = Field(min_length=1)
    language: str | None = None


Stream = Annotated[
    VideoStream | AudioStream | SubtitleStream,
    Field(discriminator="kind"),
]


class MediaInfo(SemanticModel):
    """Identity and technical facts for the source media asset."""

    id: Identifier
    uri: str = Field(min_length=1)
    duration: RationalTime
    file_size: int | None = Field(default=None, ge=0)
    modified_at: datetime | None = None
    created_at: datetime | None = None
    checksum: Checksum | None = None
    container_format: str | None = None
    bit_rate: int | None = Field(default=None, ge=0)
    streams: tuple[Stream, ...]
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_video_and_positive_duration(self) -> "MediaInfo":
        """A SemanticVideo asset must contain positive-duration video."""

        if self.duration.value == 0:
            raise ValueError("media duration must be positive")
        if not any(stream.kind == "video" for stream in self.streams):
            raise ValueError("media must contain at least one video stream")
        stream_ids = [stream.id for stream in self.streams]
        if len(stream_ids) != len(set(stream_ids)):
            raise ValueError("stream IDs must be unique")
        stream_indexes = [stream.index for stream in self.streams]
        if len(stream_indexes) != len(set(stream_indexes)):
            raise ValueError("stream indexes must be unique")
        return self
