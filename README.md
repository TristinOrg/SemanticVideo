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

Milestones 0 and 1 establish the repository and the schema foundation:

- Pydantic models for media, streams, exact time, segments, annotations,
  entities, evidence, and provenance
- JSON serialization and JSON Schema export
- cross-reference and temporal validation
- an example `.semantic.json` manifest
- tests, linting, typing, CI, documentation, and architectural decisions

Media analysis, AI providers, search, EditPlan, OpenTimelineIO, and FFmpeg
rendering are intentionally scheduled for later milestones.

## Quick start

Requirements: Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy src
uv run semanticvideo-schema --output semanticvideo.schema.json
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

See [the semantic format](docs/semantic-format.md),
[architecture](docs/architecture.md), and [roadmap](ROADMAP.md) for details.

## Project status

SemanticVideo is pre-alpha. Contributions and concrete media workflows are
welcome, but consumers should pin an exact schema version and retain their
original media.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes use Conventional Commits, for
example `feat(schema): add exact time ranges`.

## License

Licensed under the [Apache License 2.0](LICENSE).

