# Architecture

SemanticVideo is a semantic sidecar format and reference SDK. The source media
continues to own pixels and audio; the manifest owns reusable claims about that
media.

## Responsibility boundaries

```text
Media file
    |
    v
Replaceable analyzers ---> SemanticVideo manifest
                                  |
                                  v
                           Search / AI planner
                                  |
                                  v
                              EditPlan
                              /      \
                             v        v
                           OTIO     FFmpeg
```

- **SemanticVideo** records source facts, structural intervals, observations,
  uncertainty, evidence, and provenance.
- **EditPlan** records a planner's concrete editing intent.
- **OpenTimelineIO** exchanges editorial timelines with other applications.
- **FFmpeg** inspects and renders media deterministically.

None of these representations substitutes for the others.

## Core document

`SemanticVideoDocument` is the aggregate consistency boundary for one source
asset. It contains:

- `media`: source identity, exact duration, and stream-level metadata
- `entities`: identities referenced across intervals and potentially assets
- `segments`: structural ranges such as shots, scenes, sequences, and chapters
- `annotations`: overlapping time-aligned claims with typed values
- `artifacts`: references to large derived files kept outside the manifest
- `analysis_runs`: resumable analyzer execution records
- `extensions`: explicitly namespaced experimental document data

## Segments are not annotations

A shot boundary, spoken phrase, visual action, and location rarely have the
same temporal extent. SemanticVideo therefore avoids a single universal
segment that contains every possible description.

Segments express media structure. Annotations express independently timed
claims. A segment may reference related annotations without owning or copying
their values.

## Trust model

Semantic values are claims, not absolute truth. Machine-generated annotations
must identify their provenance. Confidence indicates uncertainty but never
replaces evidence or traceability. Multiple conflicting annotations may exist
over the same target range; applications decide how to resolve them.

The v0.1 manifest is not tamper-evident. Compatibility with C2PA is a future
integration concern rather than a custom signature system in the core schema.

## Extensibility

Core annotation types use discriminated unions and strict validation. New
experimental observations can use `CustomAnnotation` with a reverse-domain
namespace. Large vectors, thumbnails, waveforms, and model feature arrays use
artifact references instead of bloating human-readable JSON.

Breaking core changes require a schema version change, fixtures, migration
notes, and an ADR. Provider-specific fields do not belong in core models.

