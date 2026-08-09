# Roadmap

SemanticVideo is developed as independently reviewable milestones. Later work
must not compromise the provider-neutral schema foundation.

## Completed foundation

- **Milestone 0 — Repository foundation:** packaging, documentation, tests,
  linting, typing, CI, contribution guidance, and ADRs.
- **Milestone 1 — Core schema:** exact time, media identity, streams,
  structural segments, typed annotations, entities, evidence, provenance,
  document validation, JSON serialization, and JSON Schema export.
- **Milestone 2 — Media inspection:** safe `ffprobe` execution, pure JSON
  parsing, filesystem identity, technical stream metadata, scriptable CLI,
  fixtures, and a synthetic video integration test.

## Next milestones

1. **Vertical editing slice:** manually authored manifests to a minimal
   EditPlan and deterministic FFmpeg cut/concatenate renderer.
2. **Frame extraction and shot detection:** modular sampling and boundaries.
3. **Representative frames and signal quality:** local deterministic metrics.
4. **Timed transcription:** provider interface and one reference adapter.
5. **Structured visual semantics:** provider-neutral VLM adapter contracts.
6. **Semantic retrieval:** embeddings behind a replaceable local index.
7. **Editorial interchange:** validated EditPlan and OpenTimelineIO export.
8. **Japan trip demo:** semantic selection and a human-reviewable rough cut.

## Future exploration

OCR, face and speaker identity, GPS fusion, landmark recognition, audio events,
story segmentation, visual similarity, rights policies, content credentials,
professional editor integrations, an MCP server, and embedded container
metadata remain future ideas, not current commitments.
