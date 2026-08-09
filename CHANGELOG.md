# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-08-09

### Added

- Repository foundation, documentation, tests, and continuous integration.
- Initial provider-neutral SemanticVideo schema and JSON Schema export.
- Example Japan trip semantic manifest.
- Deterministic `ffprobe` media inspection and `semanticvideo inspect` CLI.
- Fixture-driven parser coverage and a synthetic video integration test.
- Single-file `semanticvideo analyze` pipeline with FFmpeg shot detection,
  representative frames, structured shot content, and traceable provenance.
- Optional OpenAI vision and reviewed JSON description providers.
- Opt-in technical, embedded metadata, SHA-256, and raw FFprobe information.
- Schema 0.2 compatibility foundation for scene summaries, audio observations,
  actionable editing signals, explicit capability states, and segment relations.
- Multi-frame sampling with deterministic exposure, sharpness, visual-change,
  audio-level, embedded-location, duplicate, and same-scene analysis.
- API-key-free agent task bundles and validated multimodal response import.
- Optional OpenAI `whisper-1` word/segment timestamp transcription with speech
  annotations merged into the single semantic manifest.
- Validated `EditPlan` and `EditClip` contracts with exact source ranges and document
  reference checks.
- Automatic rough-cut planning using usability, quality, interest, recommended
  ranges, and duplicate groups.
- Safe, atomic FFmpeg H.264/AAC rendering through the `plan` and `render` CLI
  commands.
- Optional per-clip pacing caps for multi-shot target-duration rough cuts.
