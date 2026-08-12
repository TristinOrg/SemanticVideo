# Reusable video understanding

SemanticVideo is a semantic cache, not a requirement that consumers trust stale
or incomplete model output. Consumers use this decision sequence:

1. Read the manifest's summaries, moments, annotations, and capability reports.
2. Check whether the required fields cover the required source range.
3. Answer or act directly when coverage is sufficient.
4. Otherwise inspect only the relevant source interval.
5. Save the new claims as a supplement and merge them back into the manifest.

This is the `analyze once, reuse often, inspect only when necessary, learn
incrementally` contract.

## Evidence

Representative timestamps are always part of structural shots. With
`--evidence-dir`, the actual JPEGs are retained as artifacts with checksums and
source time ranges. When the CLI writes a manifest, artifact paths are relative to
the manifest directory whenever possible. Moving the manifest and its evidence
directory together therefore preserves the links.

Adaptive mode treats `--frames-per-shot` as the minimum. Long shots receive more
evenly spaced samples until the requested maximum interval is met or the hard
limit of nine frames is reached. Important changes inside a shot belong in
`moments`, each with its own exact source range.

## Completeness and focused enrichment

A missing field does not mean the content is absent. A capability report states
whether analysis was complete, partial, omitted, or failed; `analyzed_fields` and
`covered_ranges` state exactly what was checked. Use `semanticvideo gaps` before
opening source pixels again.

Focused results use `SemanticSupplement`. Merge behavior is deterministic:

- new machine claims may replace machine claims with the same ID;
- human-authored and human-reviewed claims are never overwritten by supplements;
- every merge appends an `AnalysisRun`;
- document validation rejects out-of-bounds times and unknown references.

## Retrieval

`semanticvideo index` derives JSONL rows from summaries, moments, and annotations.
It contains source IDs and exact time ranges and can be rebuilt at any time. The
portable `.semantic.json` remains the source of truth. Future embedding indexes
will follow the same derived-cache rule.
