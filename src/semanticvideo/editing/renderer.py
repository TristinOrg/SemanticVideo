"""Render validated edit plans through one safe FFmpeg invocation."""

from __future__ import annotations

import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path

from semanticvideo.errors import RenderError
from semanticvideo.schema import AudioStream, EditPlan, SemanticVideoDocument


def render_edit_plan(
    document: SemanticVideoDocument,
    plan: EditPlan,
    output: Path,
    *,
    executable: str = "ffmpeg",
    timeout_seconds: float = 3600,
    overwrite: bool = False,
) -> Path:
    """Re-encode and concatenate plan clips into a widely compatible MP4."""

    source = Path(document.media.uri)
    if not source.is_file():
        raise RenderError(f"source media does not exist: {source}")
    if output.exists() and not overwrite:
        raise RenderError(f"render output already exists: {output}")
    if source.resolve() == output.resolve():
        raise RenderError("render output cannot overwrite source media")
    output.parent.mkdir(parents=True, exist_ok=True)
    has_audio = any(
        isinstance(stream, AudioStream) for stream in document.media.streams
    )
    filter_complex = _filter_complex(plan, has_audio=has_audio)

    with tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}.",
        suffix=output.suffix or ".mp4",
        dir=output.parent,
        delete=False,
    ) as temporary_handle:
        temporary = Path(temporary_handle.name)
    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
    ]
    if has_audio:
        command.extend(("-map", "[outa]"))
    command.extend(
        (
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
        )
    )
    if has_audio:
        command.extend(("-c:a", "aac", "-b:a", "160k"))
    command.extend(("-movflags", "+faststart", str(temporary)))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        _remove_partial(temporary)
        raise RenderError(f"ffmpeg executable was not found: {executable!r}") from error
    except subprocess.TimeoutExpired as error:
        _remove_partial(temporary)
        raise RenderError(
            f"render timed out after {timeout_seconds:g} seconds"
        ) from error
    if completed.returncode != 0:
        _remove_partial(temporary)
        detail = completed.stderr.strip() or "ffmpeg returned no diagnostic output"
        raise RenderError(
            f"ffmpeg render failed with exit code {completed.returncode}: {detail}"
        )
    if not temporary.is_file() or temporary.stat().st_size == 0:
        _remove_partial(temporary)
        raise RenderError("ffmpeg completed without producing a video")
    temporary.replace(output)
    return output


def find_edit_plan(document: SemanticVideoDocument, plan_id: str | None) -> EditPlan:
    """Resolve an explicit plan or the latest plan in a manifest."""

    if not document.edit_plans:
        raise RenderError("manifest contains no edit plan")
    if plan_id is None:
        return document.edit_plans[-1]
    for plan in document.edit_plans:
        if plan.id == plan_id:
            return plan
    raise RenderError(f"manifest has no edit plan {plan_id!r}")


def _filter_complex(plan: EditPlan, *, has_audio: bool) -> str:
    filters: list[str] = []
    inputs: list[str] = []
    for index, clip in enumerate(plan.clips):
        start = float(clip.source_range.start_fraction)
        end = float(clip.source_range.end_fraction)
        filters.append(
            f"[0:v:0]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{index}]"
        )
        inputs.append(f"[v{index}]")
        if has_audio:
            filters.append(
                f"[0:a:0]atrim=start={start:.6f}:end={end:.6f},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            inputs.append(f"[a{index}]")
    filters.append(
        f"{''.join(inputs)}concat=n={len(plan.clips)}:v=1:"
        f"a={1 if has_audio else 0}[outv]" + ("[outa]" if has_audio else "")
    )
    return ";".join(filters)


def _remove_partial(path: Path) -> None:
    with suppress(OSError):
        path.unlink(missing_ok=True)
