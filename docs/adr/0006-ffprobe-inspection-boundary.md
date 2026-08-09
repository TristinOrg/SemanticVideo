# 0006: Separate ffprobe execution from metadata parsing

- Status: Accepted
- Date: 2026-08-09

## Context

Technical inspection depends on an external executable, untrusted media paths,
and ffprobe JSON that varies by container and stream. Tests should not require
large binary fixtures or a particular local FFmpeg installation.

## Decision

Invoke ffprobe without a shell, with fixed arguments, captured diagnostics, and
a timeout. Keep its JSON-to-schema conversion in a pure parser. Combine local
filesystem facts only in the higher-level inspection function.

## Alternatives

- Parse human-readable ffprobe console output
- Couple subprocess execution and schema conversion in one function
- Use OpenCV as the authoritative technical metadata source
- Require a Python FFmpeg wrapper dependency

## Consequences

Fixture tests are fast and deterministic, command injection through filenames
is avoided, and other transports can reuse the parser. The project still
depends on an installed ffprobe executable for real inspection and must handle
version-specific fields conservatively.

