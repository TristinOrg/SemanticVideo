# 0002: Use strict JSON as the first serialization

- Status: Accepted
- Date: 2026-08-09

## Context

The format must be readable by humans, LLMs, scripts, and services while its
data model is still being validated through real media workflows.

## Decision

Use UTF-8 JSON validated by a generated JSON Schema. Pydantic models form the
reference implementation, not the only permitted implementation.

## Alternatives

- Protobuf or another binary serialization
- XML as used by established media metadata standards
- JSON-LD as a mandatory core representation

## Consequences

JSON is accessible and portable but verbose. Large binary values and vectors
must use artifact references. A JSON-LD mapping can be added without changing
the initial operational representation.

