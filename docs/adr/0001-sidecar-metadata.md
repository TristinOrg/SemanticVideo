# 0001: Use sidecar semantic metadata

- Status: Accepted
- Date: 2026-08-09

## Context

Existing media containers and codecs are widely supported and remain the
authoritative storage for pixels and audio. Requiring a new container would
make adoption, incremental analysis, and human inspection harder.

## Decision

SemanticVideo 0.x uses a JSON sidecar adjacent to or referencing the original
media. Embedding may be supported later as an interoperable transport.

## Alternatives

- A new media container or codec
- Mandatory metadata embedding in MP4 or MKV
- A database-only representation

## Consequences

Sidecars are easy to generate, diff, cache, and repair. Applications must keep
media and manifests associated and use identity metadata to detect staleness.

