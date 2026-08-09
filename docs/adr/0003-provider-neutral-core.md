# 0003: Keep core schemas provider-neutral

- Status: Accepted
- Date: 2026-08-09

## Context

Video understanding can use deterministic tools, local models, hosted models,
manual input, or imported metadata. Binding persisted data to one vendor would
make it less reusable and harder to reproduce.

## Decision

Core values use application-level types. Provider and model identifiers appear
only in provenance. Analyzer implementations will live behind explicit adapter
interfaces in later milestones.

## Alternatives

- Model-specific response objects as the stored schema
- A single supported hosted provider
- Unstructured prose descriptions only

## Consequences

Providers must translate and validate their output. Consumers receive a stable
contract and retain enough provenance to compare or replace generators.

