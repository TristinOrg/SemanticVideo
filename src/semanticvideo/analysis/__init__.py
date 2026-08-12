"""High-level video analysis pipeline."""

from semanticvideo.analysis.agent_task import (
    AgentResponse,
    AgentTaskBundle,
    prepare_agent_task,
)
from semanticvideo.analysis.pipeline import analyze_video
from semanticvideo.analysis.shots import (
    adaptive_representative_times,
    build_shot_ranges,
    detect_shot_boundaries,
    extract_frame,
    representative_time,
    representative_times,
)
from semanticvideo.analysis.transcription import (
    Transcriber,
    TranscriptResult,
    TranscriptSegmentResult,
    TranscriptWordResult,
)
from semanticvideo.analysis.types import ShotDescriber, ShotDescription

__all__ = [
    "AgentResponse",
    "AgentTaskBundle",
    "ShotDescriber",
    "ShotDescription",
    "Transcriber",
    "TranscriptResult",
    "TranscriptSegmentResult",
    "TranscriptWordResult",
    "analyze_video",
    "adaptive_representative_times",
    "build_shot_ranges",
    "detect_shot_boundaries",
    "extract_frame",
    "prepare_agent_task",
    "representative_time",
    "representative_times",
]
