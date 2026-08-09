"""High-level video analysis pipeline."""

from semanticvideo.analysis.pipeline import analyze_video
from semanticvideo.analysis.shots import (
    build_shot_ranges,
    detect_shot_boundaries,
    extract_frame,
    representative_time,
    representative_times,
)
from semanticvideo.analysis.types import ShotDescriber, ShotDescription

__all__ = [
    "ShotDescriber",
    "ShotDescription",
    "analyze_video",
    "build_shot_ranges",
    "detect_shot_boundaries",
    "extract_frame",
    "representative_time",
    "representative_times",
]
