# Roadmap

SemanticVideo is developed as independently reviewable milestones. Later work must
not compromise the provider-neutral schema foundation.

## Completed through 0.3.0

- **Milestone 0 — Repository foundation:** packaging, documentation, tests,
  linting, typing, CI, contribution guidance, and ADRs.
- **Milestone 1 — Core schema:** exact time, media identity, streams, structural
  segments, typed annotations, entities, evidence, provenance, validation, JSON
  serialization, and JSON Schema export.
- **Milestone 2 — Media inspection:** safe `ffprobe` execution, technical stream
  metadata, scriptable CLI, fixtures, and synthetic integration testing.
- **Milestone 3 — Content understanding:** FFmpeg shot detection, multi-frame
  evidence, structured scene summaries, quality/audio/location/editing signals,
  relations, optional timestamped transcription, and provider-neutral adapters.
- **Milestone 4 — Agent-native editing slice:** portable evidence bundles for Codex
  or another agent, validated response import without an API key, explainable
  `EditPlan` generation, pacing controls, and atomic FFmpeg rough-cut rendering.
- **Japan trip workflow:** a real source video can now travel from analysis through a
  single semantic manifest to a human-reviewable MP4 rough cut.
- **Milestone 5 — reusable understanding:** adaptive evidence sampling, persistent
  keyframe artifacts, time-aligned moments, summary hierarchy, explicit field/range
  coverage, focused enrichment, and rebuildable semantic text retrieval.

## Next milestones

1. **Embedding retrieval:** image/text embeddings behind a replaceable local index.
2. **High-recall understanding:** OCR, audio events, orientation intervals, dynamic
   sampling triggers, and calibrated semantic completeness evaluation.
3. **Editorial interchange:** OpenTimelineIO export and import for NLE handoff.
4. **Story planning:** multi-source selection, chapters, narrative beats, music and
   transcript-aware pacing, and configurable editorial policies.
5. **Human review UI:** inspect evidence, correct semantic claims, lock clips, and
   compare generated plans before rendering.
6. **Performance:** incremental caches, parallel extraction, hardware encoding, and
   proxy workflows for long or high-resolution projects.

## Future exploration

OCR, face and speaker identity, GPS fusion, landmark recognition, richer audio-event
classification, rights policies, content credentials, professional editor
integrations, an MCP server, and embedded container metadata remain future ideas,
not current commitments.
