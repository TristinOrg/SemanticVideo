"""Scriptable SemanticVideo command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from semanticvideo import RationalTime, SemanticVideoDocument, TimeRange, __version__
from semanticvideo.analysis import analyze_video
from semanticvideo.analysis.agent_task import prepare_agent_task
from semanticvideo.analysis.incremental import (
    SemanticSupplement,
    apply_supplement,
    capability_gaps,
)
from semanticvideo.analysis.pipeline import INCLUDE_CHOICES
from semanticvideo.editing import (
    add_edit_plan,
    create_edit_plan,
    find_edit_plan,
    render_edit_plan,
)
from semanticvideo.errors import SemanticVideoError
from semanticvideo.media import inspect_media
from semanticvideo.providers import (
    AgentResponseProvider,
    JsonFileShotDescriber,
    OpenAIShotDescriber,
    OpenAITranscriber,
)
from semanticvideo.retrieval import load_index, read_documents, search, write_index


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
        choices=("auto", "openai", "json", "agent"),
        default="auto",
        help="Description provider (default: auto).",
    )
    analyze_parser.add_argument(
        "--descriptions",
        type=Path,
        help="Reviewed JSON descriptions keyed by shot ID; selects the JSON provider.",
    )
    analyze_parser.add_argument(
        "--agent-response",
        type=Path,
        help="Validated response.json produced from a prepare-agent task bundle.",
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
        "--transcribe-openai",
        action="store_true",
        help="Add word-timestamp transcription with whisper-1 (requires API key).",
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
        "--frames-per-shot",
        type=_frame_count,
        default=3,
        metavar="COUNT",
        help="Representative frames sampled inside each shot, 1-9 (default: 3).",
    )
    analyze_parser.add_argument(
        "--adaptive-frames",
        action="store_true",
        help="Increase representative frames for long shots (bounded to 9).",
    )
    analyze_parser.add_argument(
        "--maximum-frame-interval",
        type=_positive_float,
        default=8.0,
        metavar="SECONDS",
        help="Maximum desired interval in adaptive mode (default: 8).",
    )
    analyze_parser.add_argument(
        "--evidence-dir",
        type=Path,
        help="Persist representative JPEG evidence in this directory.",
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

    prepare_parser = commands.add_parser(
        "prepare-agent",
        help="Extract a portable task bundle for Codex or another AI agent.",
    )
    prepare_parser.add_argument("input", type=Path, help="Input video file.")
    prepare_parser.add_argument(
        "-o", "--output", type=Path, help="Task directory (default: INPUT.task)."
    )
    prepare_parser.add_argument("--language", default="en")
    prepare_parser.add_argument(
        "--scene-threshold", type=_unit_float, default=0.3, metavar="NUMBER"
    )
    prepare_parser.add_argument(
        "--minimum-shot-duration",
        type=_positive_float,
        default=0.5,
        metavar="SECONDS",
    )
    prepare_parser.add_argument(
        "--frames-per-shot", type=_frame_count, default=3, metavar="COUNT"
    )
    prepare_parser.add_argument("--adaptive-frames", action="store_true")
    prepare_parser.add_argument(
        "--maximum-frame-interval", type=_positive_float, default=8.0
    )
    prepare_parser.add_argument("--ffmpeg", default="ffmpeg")
    prepare_parser.add_argument("--ffprobe", default="ffprobe")
    prepare_parser.add_argument("--timeout", type=_positive_float, default=300.0)

    plan_parser = commands.add_parser(
        "plan",
        help="Create an explainable rough-cut plan from editing signals.",
    )
    plan_parser.add_argument("manifest", type=Path, help="SemanticVideo JSON file.")
    plan_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output manifest (default: update MANIFEST atomically).",
    )
    plan_parser.add_argument(
        "--target-duration",
        type=_positive_float,
        metavar="SECONDS",
        help="Maximum rough-cut duration.",
    )
    plan_parser.add_argument(
        "--minimum-clip-duration",
        type=_positive_float,
        default=0.5,
        metavar="SECONDS",
    )
    plan_parser.add_argument(
        "--maximum-clip-duration",
        type=_positive_float,
        metavar="SECONDS",
        help="Cap each selected source range to improve pacing.",
    )
    plan_parser.add_argument(
        "--ranked-order",
        action="store_true",
        help="Keep interest ranking instead of restoring source order.",
    )
    plan_parser.add_argument("--name", default="Automatic rough cut")

    render_parser = commands.add_parser(
        "render", help="Render an edit plan to MP4 with FFmpeg."
    )
    render_parser.add_argument("manifest", type=Path, help="SemanticVideo JSON file.")
    render_parser.add_argument("-o", "--output", type=Path, required=True)
    render_parser.add_argument("--plan-id", help="Plan ID (default: latest).")
    render_parser.add_argument("--ffmpeg", default="ffmpeg")
    render_parser.add_argument(
        "--timeout", type=_positive_float, default=3600.0, metavar="SECONDS"
    )
    render_parser.add_argument("--overwrite", action="store_true")

    gaps_parser = commands.add_parser(
        "gaps", help="Report semantic fields that require focused inspection."
    )
    gaps_parser.add_argument("manifest", type=Path)
    gaps_parser.add_argument("--field", action="append", required=True)
    gaps_parser.add_argument("--start", type=_non_negative_float)
    gaps_parser.add_argument("--duration", type=_positive_float)

    enrich_parser = commands.add_parser(
        "enrich", help="Merge a validated focused-analysis supplement."
    )
    enrich_parser.add_argument("manifest", type=Path)
    enrich_parser.add_argument("supplement", type=Path)
    enrich_parser.add_argument("-o", "--output", type=Path)

    index_parser = commands.add_parser(
        "index", help="Build a disposable JSONL search index from manifests."
    )
    index_parser.add_argument("manifest", nargs="+", type=Path)
    index_parser.add_argument("-o", "--output", required=True, type=Path)

    search_parser = commands.add_parser(
        "search", help="Search a derived SemanticVideo JSONL index."
    )
    search_parser.add_argument("index", type=Path)
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=_positive_int, default=20)
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
            output = args.output or args.input.with_suffix(".semantic.json")
            describer = _description_provider(args)
            agent_response = (
                describer if isinstance(describer, AgentResponseProvider) else None
            )
            transcriber = OpenAITranscriber() if args.transcribe_openai else None
            document = analyze_video(
                args.input,
                describer=describer,
                ffprobe_executable=args.ffprobe,
                ffmpeg_executable=args.ffmpeg,
                timeout_seconds=args.timeout,
                scene_threshold=args.scene_threshold,
                minimum_shot_duration=args.minimum_shot_duration,
                frames_per_shot=args.frames_per_shot,
                language=args.language,
                include=args.include,
                transcriber=transcriber,
                transcript=(
                    agent_response.transcript if agent_response is not None else None
                ),
                imported_location=(
                    agent_response.location if agent_response is not None else None
                ),
                adaptive_frames=args.adaptive_frames,
                maximum_frame_interval_seconds=args.maximum_frame_interval,
                evidence_directory=args.evidence_dir,
            )
            rendered = document.model_dump_json(
                indent=None if args.compact else 2,
                exclude_none=True,
            )
            output.write_text(f"{rendered}\n", encoding="utf-8")
            sys.stdout.write(f"Wrote {output}\n")
            return 0
        if args.command == "prepare-agent":
            output = args.output or args.input.with_suffix(".task")
            bundle = prepare_agent_task(
                args.input,
                output,
                language=args.language,
                ffprobe_executable=args.ffprobe,
                ffmpeg_executable=args.ffmpeg,
                timeout_seconds=args.timeout,
                scene_threshold=args.scene_threshold,
                minimum_shot_duration=args.minimum_shot_duration,
                frames_per_shot=args.frames_per_shot,
                adaptive_frames=args.adaptive_frames,
                maximum_frame_interval_seconds=args.maximum_frame_interval,
            )
            sys.stdout.write(
                f"Wrote agent task with {len(bundle.shots)} shots to {output}\n"
            )
            return 0
        if args.command == "plan":
            document = _read_document(args.manifest)
            plan = create_edit_plan(
                document,
                target_duration_seconds=args.target_duration,
                minimum_clip_seconds=args.minimum_clip_duration,
                maximum_clip_seconds=args.maximum_clip_duration,
                preserve_source_order=not args.ranked_order,
                name=args.name,
            )
            updated = add_edit_plan(document, plan)
            output = args.output or args.manifest
            _write_document_atomic(updated, output)
            sys.stdout.write(
                f"Wrote {plan.id} with {len(plan.clips)} clips "
                f"({plan.duration_seconds:.3f}s) to {output}\n"
            )
            return 0
        if args.command == "render":
            document = _read_document(args.manifest)
            plan = find_edit_plan(document, args.plan_id)
            rendered_output = render_edit_plan(
                document,
                plan,
                args.output,
                executable=args.ffmpeg,
                timeout_seconds=args.timeout,
                overwrite=args.overwrite,
            )
            sys.stdout.write(f"Rendered {plan.id} to {rendered_output}\n")
            return 0
        if args.command == "gaps":
            document = _read_document(args.manifest)
            requested_range = _optional_range(args.start, args.duration)
            gaps = capability_gaps(
                document, tuple(args.field), time_range=requested_range
            )
            sys.stdout.write(f"{json.dumps({'gaps': gaps}, ensure_ascii=False)}\n")
            return 1 if gaps else 0
        if args.command == "enrich":
            document = _read_document(args.manifest)
            supplement = SemanticSupplement.model_validate_json(
                args.supplement.read_text(encoding="utf-8")
            )
            updated = apply_supplement(document, supplement)
            output = args.output or args.manifest
            _write_document_atomic(updated, output)
            sys.stdout.write(f"Enriched {output}\n")
            return 0
        if args.command == "index":
            count = write_index(read_documents(args.manifest), args.output)
            sys.stdout.write(f"Indexed {count} semantic records to {args.output}\n")
            return 0
        if args.command == "search":
            hits = search(load_index(args.index), args.query, limit=args.limit)
            sys.stdout.write(
                json.dumps(
                    [item.model_dump(mode="json", exclude_none=True) for item in hits],
                    ensure_ascii=False,
                )
                + "\n"
            )
            return 0
    except (SemanticVideoError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    return 2


def _read_document(path: Path) -> SemanticVideoDocument:
    return SemanticVideoDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _write_document_atomic(document: SemanticVideoDocument, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = document.model_dump_json(indent=2, exclude_none=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(f"{rendered}\n")
    try:
        temporary.replace(output)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _optional_range(start: float | None, duration: float | None) -> TimeRange | None:
    if start is None and duration is None:
        return None
    if start is None or duration is None:
        raise SemanticVideoError("--start and --duration must be supplied together")
    return TimeRange(
        start=RationalTime(value=round(start * 1_000_000), rate=1_000_000),
        duration=RationalTime(value=round(duration * 1_000_000), rate=1_000_000),
    )


def _unit_float(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed < 1:
        raise argparse.ArgumentTypeError("must be between zero and one")
    return parsed


def _frame_count(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 9:
        raise argparse.ArgumentTypeError("must be between 1 and 9")
    return parsed


def _description_provider(
    args: Any,
) -> JsonFileShotDescriber | OpenAIShotDescriber | AgentResponseProvider:
    provider = args.provider
    if provider == "auto":
        if args.agent_response is not None:
            provider = "agent"
        else:
            provider = "json" if args.descriptions is not None else "openai"
    if provider == "agent":
        if args.agent_response is None:
            raise SemanticVideoError("--provider agent requires --agent-response")
        if args.descriptions is not None:
            raise SemanticVideoError(
                "--agent-response cannot be combined with --descriptions"
            )
        return AgentResponseProvider(args.agent_response)
    if args.agent_response is not None:
        raise SemanticVideoError(
            "--agent-response cannot be combined with a non-agent provider"
        )
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
