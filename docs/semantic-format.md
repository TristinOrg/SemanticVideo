# SemanticVideo format 0.1

This document describes the normative intent of the initial JSON sidecar. The
generated JSON Schema is the machine-readable validation contract.

## File naming

The recommended sidecar name replaces the media extension:

```text
GX010231.MP4
GX010231.semantic.json
```

Paths may be relative to the manifest. Consumers must not assume that a URI is
local or that the manifest and media have the same base name.

## Exact time

Time uses non-negative integer ticks:

```json
{
  "value": 41200,
  "rate": 1000
}
```

This represents exactly `41200 / 1000` seconds. `TimeRange` is half-open and
stores `start` plus positive `duration`:

```text
[start, start + duration)
```

Applications may display float seconds, but serialized float seconds are not
authoritative. Integer ticks avoid accumulated rounding errors and work with
media PTS, audio samples, millisecond annotations, and non-integer frame rates.

## Media and streams

`media` identifies one source asset. A content checksum is optional because
hashing large media can be expensive, but reliable workflows should populate
one or use a documented cache fingerprint strategy.

Streams are a discriminated union of `video`, `audio`, and `subtitle` records.
Annotations may target the entire asset or one stream by ID. Stream indexes and
IDs are unique within the asset.

## Structural segments

Segments model shots, scenes, sequences, chapters, or custom structural
intervals. Their ranges must fit within media duration. Representative times
must fall inside the segment. A segment can reference a parent and related
annotations.

Segments may overlap or nest. This version deliberately does not require shots
to form a gapless partition because detectors can be incomplete and media can
contain multiple video streams.

## Typed annotations

All annotations have:

- a stable ID and discriminating `kind`
- a positive source-media time range
- optional stream and normalized spatial targets
- a typed `value`
- review status and optional confidence
- provenance and evidence
- free tags for retrieval

Core kinds in v0.1 are `scene`, `quality`, `event`, `subject`, `speech`, and
`location`. A `custom` kind provides namespaced experimentation without adding
unvalidated fields to core objects.

Schema 0.2 adds `audio` observations and `editorial` signals. Scene prose moves
to the optional `summary` field; the older `description` field remains readable
for compatibility, but planners should consume structured subjects, actions,
objects, environment, shot type, and editorial annotations instead of parsing prose.

Editorial annotations may record quality and interest scores, usability, a
recommended source range, duplicate group, continuity notes, reasons, and warnings.
Recommended ranges must remain inside the annotation range.

## Capability state and segment relations

The root `capabilities` collection says whether each analyzer completed, produced
partial data, was intentionally omitted, or failed. This prevents missing data from
being mistaken for a negative observation.

The root `relations` collection connects segments as same-scene, continuation,
duplicate, alternative, contrast, or supporting material. Both referenced segment
IDs must resolve and a relation cannot point from a segment to itself.

An annotation expresses one claim. If two models disagree about a location,
store two annotations with independent confidence and provenance rather than
merging away the disagreement.

## Provenance and evidence

Machine-generated annotations require provenance. Automated provenance records
identify the generator name and version, plus optional provider and model.
Evidence may embed a small JSON value, reference another annotation, or point
to a declared artifact.

Human-authored annotations should also include manual provenance so later
consumers can distinguish corrections from machine output.

## Entities

Entities provide stable identities for people, speakers, places, objects, and
other subjects referenced by annotations. Entity references must resolve within
the document in v0.1. Cross-document entity catalogs are a future extension.

## Artifact references

Thumbnails, embeddings, waveforms, proxies, and other large derivatives should
remain outside the manifest and be referenced through `artifacts`. Referenced
artifact IDs are validated.

## Integrity rules

A valid document must satisfy at least these rules:

- IDs are unique within each object collection.
- media contains a video stream and has positive duration.
- all ranges are positive and end within media duration.
- stream, entity, segment, annotation, and artifact references resolve.
- representative timestamps fall inside their segment.
- word ranges fall inside their speech utterance.
- automated claims identify their generating implementation.

See [`examples/japan-trip/GX010231.semantic.json`](../examples/japan-trip/GX010231.semantic.json)
for a complete example.
