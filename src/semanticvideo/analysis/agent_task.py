"""Portable task bundles that any capable AI agent can complete without an API key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from semanticvideo.analysis.shots import (
    adaptive_representative_times,
    build_shot_ranges,
    detect_shot_boundaries,
    extract_frame,
    representative_times,
)
from semanticvideo.analysis.transcription import TranscriptResult, extract_audio
from semanticvideo.analysis.types import ShotDescription
from semanticvideo.errors import AgentTaskError
from semanticvideo.media import inspect_media
from semanticvideo.schema import AudioStream, LocationInfo, TimeRange
from semanticvideo.schema._base import SemanticModel


class AgentShotTask(SemanticModel):
    id: str = Field(pattern=r"^shot\.\d{4}$")
    time_range: TimeRange
    frame_uris: tuple[str, ...]


class AgentTaskBundle(SemanticModel):
    task_version: Literal["0.1.0"] = "0.1.0"
    source_uri: str
    language: str
    instructions: tuple[str, ...]
    shots: tuple[AgentShotTask, ...]
    audio_uri: str | None = None
    response_template_uri: str = "response.template.json"
    response_schema_uri: str = "response.schema.json"


class AgentResponse(SemanticModel):
    response_version: Literal["0.1.0"] = "0.1.0"
    shots: dict[str, ShotDescription]
    transcript: TranscriptResult | None = None
    location: LocationInfo | None = None


def prepare_agent_task(
    path: Path,
    output_directory: Path,
    *,
    language: str = "en",
    ffprobe_executable: str = "ffprobe",
    ffmpeg_executable: str = "ffmpeg",
    timeout_seconds: float = 300,
    scene_threshold: float = 0.3,
    minimum_shot_duration: float = 0.5,
    frames_per_shot: int = 3,
    adaptive_frames: bool = False,
    maximum_frame_interval_seconds: float = 8.0,
) -> AgentTaskBundle:
    """Extract bounded evidence plus schemas for Codex or another external agent."""

    if output_directory.exists() and any(output_directory.iterdir()):
        raise AgentTaskError(f"agent task directory is not empty: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    frames_directory = output_directory / "frames"
    frames_directory.mkdir()

    media = inspect_media(
        path, executable=ffprobe_executable, timeout_seconds=timeout_seconds
    )
    boundaries = detect_shot_boundaries(
        path,
        executable=ffmpeg_executable,
        threshold=scene_threshold,
        timeout_seconds=timeout_seconds,
    )
    ranges = build_shot_ranges(
        media.duration,
        boundaries,
        minimum_duration=minimum_shot_duration,
    )
    shots: list[AgentShotTask] = []
    template_shots: dict[str, dict[str, object]] = {}
    for index, time_range in enumerate(ranges, start=1):
        shot_id = f"shot.{index:04d}"
        frame_uris: list[str] = []
        timestamps = (
            adaptive_representative_times(
                time_range,
                minimum_count=frames_per_shot,
                maximum_interval_seconds=maximum_frame_interval_seconds,
            )
            if adaptive_frames
            else representative_times(time_range, count=frames_per_shot)
        )
        for frame_index, timestamp in enumerate(timestamps, start=1):
            filename = f"{shot_id}.{frame_index:02d}.jpg"
            output = frames_directory / filename
            extract_frame(
                path,
                timestamp,
                output,
                executable=ffmpeg_executable,
                timeout_seconds=timeout_seconds,
            )
            frame_uris.append(f"frames/{filename}")
        shots.append(
            AgentShotTask(
                id=shot_id,
                time_range=time_range,
                frame_uris=tuple(frame_uris),
            )
        )
        template_shots[shot_id] = {
            "summary": "TODO: describe visible content",
            "environment": [],
            "subjects": [],
            "actions": [],
            "objects": [],
            "visible_text": [],
            "moments": [],
        }

    audio_uri = None
    if any(isinstance(stream, AudioStream) for stream in media.streams):
        audio = output_directory / "audio.mp3"
        extract_audio(
            path,
            audio,
            executable=ffmpeg_executable,
            timeout_seconds=timeout_seconds,
        )
        audio_uri = audio.name

    bundle = AgentTaskBundle(
        source_uri=str(path),
        language=language,
        instructions=(
            "Inspect every frame listed for each shot; report only visible facts.",
            "Use structured subjects, actions, objects, environment, text, "
            "and framing.",
            "Use summary only as a concise human-readable review field.",
            "Use moments with exact source ranges for important changes inside a shot.",
            "If audio exists, add timed transcript segments only when speech "
            "is audible.",
            "Do not guess identity or location; location needs visible or "
            "metadata evidence.",
            "Write the completed object as response.json and validate against "
            "the schema.",
        ),
        shots=tuple(shots),
        audio_uri=audio_uri,
    )
    (output_directory / "task.json").write_text(
        f"{bundle.model_dump_json(indent=2)}\n", encoding="utf-8"
    )
    (output_directory / "response.schema.json").write_text(
        f"{json.dumps(AgentResponse.model_json_schema(), indent=2)}\n",
        encoding="utf-8",
    )
    template = {"response_version": "0.1.0", "shots": template_shots}
    (output_directory / "response.template.json").write_text(
        f"{json.dumps(template, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
    return bundle
