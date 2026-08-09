# Roadmap

SemanticVideo is developed as independently reviewable milestones. Later work
must not compromise the provider-neutral schema foundation.

## Completed foundation

- **Milestone 0 — Repository foundation:** packaging, documentation, tests,
  linting, typing, CI, contribution guidance, and ADRs.
- **Milestone 1 — Core schema:** exact time, media identity, streams,
  structural segments, typed annotations, entities, evidence, provenance,
  document validation, JSON serialization, and JSON Schema export.

## Next milestones

1. **Media inspection:** parse deterministic `ffprobe` output.
2. **Vertical editing slice:** manually authored manifests to a minimal
   EditPlan and deterministic FFmpeg cut/concatenate renderer.
3. **Frame extraction and shot detection:** modular sampling and boundaries.
4. **Representative frames and signal quality:** local deterministic metrics.
5. **Timed transcription:** provider interface and one reference adapter.
6. **Structured visual semantics:** provider-neutral VLM adapter contracts.
7. **Semantic retrieval:** embeddings behind a replaceable local index.
8. **Editorial interchange:** validated EditPlan and OpenTimelineIO export.
9. **Japan trip demo:** semantic selection and a human-reviewable rough cut.

## Future exploration

OCR, face and speaker identity, GPS fusion, landmark recognition, audio events,
story segmentation, visual similarity, rights policies, content credentials,
professional editor integrations, an MCP server, and embedded container
metadata remain future ideas, not current commitments.

