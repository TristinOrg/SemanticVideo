"""Scriptable SemanticVideo command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from semanticvideo import __version__
from semanticvideo.errors import SemanticVideoError
from semanticvideo.media import inspect_media


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
    except (SemanticVideoError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    return 2


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
