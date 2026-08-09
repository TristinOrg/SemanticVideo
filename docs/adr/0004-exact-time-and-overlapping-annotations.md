# 0004: Use exact time and overlapping annotations

- Status: Accepted
- Date: 2026-08-09

## Context

Shots, speech, actions, locations, audio events, and narrative structures have
different boundaries. Floating-point seconds also lose the exact relationship
to media timestamps, audio samples, and fractional frame rates.

## Decision

Represent time as integer ticks plus a positive rate. Separate structural
segments from independently ranged, typed annotations.

## Alternatives

- One universal segment containing every semantic field
- Floating-point start and end seconds
- Frame numbers as the only time coordinate

## Consequences

The JSON is slightly more verbose and consumers must convert rates carefully.
In exchange, annotations can overlap naturally and time survives editorial and
FFmpeg conversions without avoidable rounding.

