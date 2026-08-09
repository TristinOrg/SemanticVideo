# SemanticVideo

Open semantic video format and AI-native video understanding SDK.

SemanticVideo adds a reusable, machine-readable semantic layer beside existing
media files. It does not replace MP4, MOV, MKV, codecs, editors, or renderers.

```text
Raw video -> analyze once -> semantic manifest -> any AI/application
```

> [!IMPORTANT]
> SemanticVideo is an early specification and reference implementation. The
> `0.x` schema may change while real-world editing workflows are validated.

## Why

Traditional media containers store pixels, audio, subtitles, and technical
metadata. They do not provide a common representation of time-aligned scenes,
speech, subjects, events, locations, quality, evidence, or editing value.
Consequently, every AI application has to inspect the original media again.

SemanticVideo persists those observations as a sidecar manifest:

```text
GX010231.MP4
GX010231.semantic.json
```

The media remains the source of truth for pixels and audio. The manifest
describes what is known about the media, when it is true, and where that claim
came from.

## Design principles

- Every observation is explicitly time-aligned.
- Structural segments and overlapping semantic annotations are separate.
- Machine-generated claims carry confidence, evidence, and provenance.
- Time is represented exactly as integer ticks and a rate, not float seconds.
- Core schemas are provider-neutral and human-editable.
- Analysis is incremental, cacheable, and replaceable.
- Semantic understanding, edit decisions, timeline interchange, and rendering
  remain separate responsibilities.

## Current scope

Milestones 0 through 4 establish the schema foundation and the first complete
analysis-to-rough-cut path:

- Pydantic models for media, streams, exact time, segments, annotations,
  entities, evidence, and provenance
- JSON serialization and JSON Schema export
- cross-reference and temporal validation
- an example `.semantic.json` manifest
- deterministic `ffprobe` inspection for real video files
- a scriptable `semanticvideo inspect` command with JSON output
- FFmpeg scene-change detection and representative-frame extraction
- provider-neutral shot descriptions with an OpenAI adapter and reviewed JSON import
- deterministic multi-frame quality, audio-level, location, similarity, and editing
  signals that do not require an AI service
- one editing-oriented `.semantic.json` containing media, shots, descriptions,
  provenance, and analysis parameters
- validated, explainable `EditPlan` objects generated from structured editing signals
- deterministic FFmpeg trim-and-concatenate rendering with atomic output handling
- tests, linting, typing, CI, documentation, and architectural decisions

Search and OpenTimelineIO interchange remain later milestones.

## Quick start

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and FFmpeg's
`ffprobe` executable for media inspection.

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy src
uv run semanticvideo-schema --output semanticvideo.schema.json
```

Inspect a real video without invoking an AI model:

```bash
uv run semanticvideo inspect GX010231.MP4
uv run semanticvideo inspect GX010231.MP4 --output GX010231.inspect.json
```

The command reports source identity, exact duration, container, bitrate, video/audio/
subtitle streams, codecs, dimensions, frame rate, time base, rotation, color
metadata, audio layout, language, timestamps, and filesystem facts as JSON.

Generate the required editing information in one file:

```bash
uv sync --extra openai
set OPENAI_API_KEY=your_key
uv run semanticvideo analyze GX010231.MP4 --language zh-CN
```

No API key is required when Codex or another agent drives the analysis:

```bash
uv run semanticvideo prepare-agent GX010231.MP4 --output GX010231.task
# Ask the agent to complete GX010231.task/response.json.
uv run semanticvideo analyze GX010231.MP4 \
  --agent-response GX010231.task/response.json
```

The default `GX010231.semantic.json` always contains core media facts, contiguous
shot ranges, three representative times per shot, structured scene descriptions,
editing fitness, audio levels, and segment relations.
The command fails instead of silently writing an incomplete manifest if description
generation is unavailable.

Turn the analysis into a reviewable rough cut:

```bash
uv run semanticvideo plan GX010231.semantic.json \
  --target-duration 60 --maximum-clip-duration 8
uv run semanticvideo render GX010231.semantic.json --output GX010231.roughcut.mp4
```

Optional information is opt-in and remains in that same JSON:

```bash
uv run semanticvideo analyze GX010231.MP4 --include technical --include metadata
uv run semanticvideo analyze GX010231.MP4 --include checksum --include raw
```

Descriptions produced elsewhere or reviewed by a person can be imported from an
object keyed by shot ID:

```bash
uv run semanticvideo analyze GX010231.MP4 --descriptions descriptions.json
```

Load and validate a manifest:

```python
from pathlib import Path

from semanticvideo import SemanticVideoDocument

document = SemanticVideoDocument.model_validate_json(
    Path("examples/japan-trip/GX010231.semantic.json").read_text()
)
print(document.media.duration.seconds)
```

See [agent workflow](docs/agent-workflow.md),
[editing and rendering](docs/editing-and-rendering.md),
[video analysis](docs/video-analysis.md),
[media inspection](docs/media-inspection.md),
[the semantic format](docs/semantic-format.md), [architecture](docs/architecture.md),
and [roadmap](ROADMAP.md) for details.

## Project status

SemanticVideo is pre-alpha. Contributions and concrete media workflows are
welcome, but consumers should pin an exact schema version and retain their
original media.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes use Conventional Commits, for
example `feat(schema): add exact time ranges`.

## License

Licensed under the [Apache License 2.0](LICENSE).
