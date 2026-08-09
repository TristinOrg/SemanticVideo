# 0005: Use OpenTimelineIO for editorial interchange

- Status: Accepted
- Date: 2026-08-09

## Context

Semantic source understanding is different from an edited timeline. Tracks,
gaps, transitions, nested compositions, source ranges, and editor adapters are
already modeled by OpenTimelineIO.

## Decision

A future simple EditPlan will express planner intent and export to
OpenTimelineIO. SemanticVideo will not become a competing timeline format.

## Alternatives

- Store edit timelines directly in the semantic manifest
- Invent a complete proprietary timeline interchange
- Render directly from unvalidated LLM output

## Consequences

Responsibilities stay clear and professional tooling can reuse OTIO. A small
translation layer and deterministic EditPlan validation will still be needed.

