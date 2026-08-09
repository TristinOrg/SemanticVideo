# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
