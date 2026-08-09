"""Scriptable SemanticVideo command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from semanticvideo import __version__
from semanticvideo.analysis import analyze_video
from semanticvideo.analysis.pipeline import INCLUDE_CHOICES
from semanticvideo.errors import SemanticVideoError
from semanticvideo.media import inspect_media
from semanticvideo.providers import JsonFileShotDescriber, OpenAIShotDescriber


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI parser."""

    parser = argparse.ArgumentParser(
        prog="semanticvideo",
        description="Inspect and describe video as reusable semantic metadata.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect", help="Extract deterministic technical media metadata."
    )
    inspect_parser.add_argument("input", type=Path, help="Input media file.")
    inspect_parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="ffprobe executable name or path (default: ffprobe).",
    )
    inspect_parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=60.0,
        metavar="SECONDS",
        help="Maximum ffprobe runtime (default: 60).",
    )
    inspect_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON to this file instead of stdout.",
    )
    inspect_parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON instead of indented output.",
    )

    analyze_parser = commands.add_parser(
        "analyze",
        help="Generate one editing-oriented JSON with shots and visual descriptions.",
    )
    analyze_parser.add_argument("input", type=Path, help="Input video file.")
    analyze_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path (default: INPUT.semantic.json).",
    )
    analyze_parser.add_argument(
        "--provider",
        choices=("auto", "openai", "json"),
        default="auto",
        help="Description provider (default: auto).",
    )
    analyze_parser.add_argument(
        "--descriptions",
        type=Path,
        help="Reviewed JSON descriptions keyed by shot ID; selects the JSON provider.",
    )
    analyze_parser.add_argument(
        "--model",
        default="gpt-5.6",
        help="OpenAI vision model (default: gpt-5.6).",
    )
    analyze_parser.add_argument(
        "--language",
        default="en",
        help="Language requested for scene descriptions (default: en).",
    )
    analyze_parser.add_argument(
        "--scene-threshold",
        type=_unit_float,
        default=0.3,
        metavar="NUMBER",
        help="FFmpeg scene-change sensitivity between 0 and 1 (default: 0.3).",
    )
    analyze_parser.add_argument(
        "--minimum-shot-duration",
        type=_positive_float,
        default=0.5,
        metavar="SECONDS",
        help="Merge shorter detected shots (default: 0.5).",
    )
    analyze_parser.add_argument(
        "--include",
        action="append",
        choices=sorted(INCLUDE_CHOICES),
        default=[],
        help=(
            "Add optional information to the same JSON; repeat for technical, "
            "metadata, checksum, or raw."
        ),
    )
    analyze_parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg executable name or path (default: ffmpeg).",
    )
    analyze_parser.add_argument(
        "--ffprobe",
        default="ffprobe",
        help="ffprobe executable name or path (default: ffprobe).",
    )
    analyze_parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=300.0,
        metavar="SECONDS",
        help="Maximum runtime per external command (default: 300).",
    )
    analyze_parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON instead of indented output.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and convert expected failures into concise diagnostics."""

    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            media = inspect_media(
                args.input,
                executable=args.ffprobe,
                timeout_seconds=args.timeout,
            )
            rendered = media.model_dump_json(indent=None if args.compact else 2)
            if args.output is None:
                sys.stdout.write(f"{rendered}\n")
            else:
                args.output.write_text(f"{rendered}\n", encoding="utf-8")
            return 0
        if args.command == "analyze":
            describer = _description_provider(args)
            document = analyze_video(
                args.input,
                describer=describer,
                ffprobe_executable=args.ffprobe,
                ffmpeg_executable=args.ffmpeg,
                timeout_seconds=args.timeout,
                scene_threshold=args.scene_threshold,
                minimum_shot_duration=args.minimum_shot_duration,
                language=args.language,
                include=args.include,
            )
            output = args.output or args.input.with_suffix(".semantic.json")
            rendered = document.model_dump_json(
                indent=None if args.compact else 2,
                exclude_none=True,
            )
            output.write_text(f"{rendered}\n", encoding="utf-8")
            sys.stdout.write(f"Wrote {output}\n")
            return 0
    except (SemanticVideoError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    return 2


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _unit_float(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed < 1:
        raise argparse.ArgumentTypeError("must be between zero and one")
    return parsed


def _description_provider(args: Any) -> JsonFileShotDescriber | OpenAIShotDescriber:
    provider = args.provider
    if provider == "auto":
        provider = "json" if args.descriptions is not None else "openai"
    if provider == "json":
        if args.descriptions is None:
            raise SemanticVideoError("--provider json requires --descriptions")
        return JsonFileShotDescriber(args.descriptions)
    if args.descriptions is not None:
        raise SemanticVideoError(
            "--descriptions cannot be combined with --provider openai"
        )
    return OpenAIShotDescriber(model=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
