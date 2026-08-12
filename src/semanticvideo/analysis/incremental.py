"""Incrementally enrich a manifest without re-analyzing the complete source."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from semanticvideo.schema import (
    AnalysisRun,
    Annotation,
    AnnotationStatus,
    CapabilityReport,
    CapabilityStatus,
    SemanticMoment,
    SemanticSummary,
    SemanticVideoDocument,
    TimeRange,
)
from semanticvideo.schema._base import SemanticModel


class SemanticSupplement(SemanticModel):
    """Validated additions produced by a focused follow-up inspection."""

    supplement_version: str = Field(default="0.1.0", pattern=r"^\d+\.\d+\.\d+$")
    capabilities: tuple[CapabilityReport, ...]
    annotations: tuple[Annotation, ...] = ()
    moments: tuple[SemanticMoment, ...] = ()
    summaries: tuple[SemanticSummary, ...] = ()
    analyzer: str = "semanticvideo-supplement"
    analyzer_version: str = "1"


def capability_gaps(
    document: SemanticVideoDocument,
    required_fields: tuple[str, ...],
    *,
    time_range: TimeRange | None = None,
) -> tuple[str, ...]:
    """Return fields whose declared capability coverage is insufficient."""

    gaps: list[str] = []
    for field in required_fields:
        reports = [
            report
            for report in document.capabilities
            if field == report.name or field in report.analyzed_fields
        ]
        if not reports or all(
            report.status in {CapabilityStatus.OMITTED, CapabilityStatus.FAILED}
            for report in reports
        ):
            gaps.append(field)
            continue
        if time_range is not None and not any(
            _covers(report, time_range) for report in reports
        ):
            gaps.append(field)
    return tuple(gaps)


def apply_supplement(
    document: SemanticVideoDocument,
    supplement: SemanticSupplement,
) -> SemanticVideoDocument:
    """Merge focused results while never overwriting human-confirmed claims."""

    annotations = {item.id: item for item in document.annotations}
    for incoming in supplement.annotations:
        existing = annotations.get(incoming.id)
        if existing is not None and existing.status in {
            AnnotationStatus.HUMAN_AUTHORED,
            AnnotationStatus.HUMAN_REVIEWED,
        }:
            continue
        annotations[incoming.id] = incoming

    moments = {item.id: item for item in document.moments}
    moments.update((item.id, item) for item in supplement.moments)
    summaries = {item.id: item for item in document.summaries}
    summaries.update((item.id, item) for item in supplement.summaries)
    capabilities = {item.name: item for item in document.capabilities}
    capabilities.update((item.name, item) for item in supplement.capabilities)

    now = datetime.now(UTC)
    added_annotation_ids = tuple(item.id for item in supplement.annotations if annotations.get(item.id) == item)
    run = AnalysisRun(
        id=f"run.supplement.{now.strftime('%Y%m%dT%H%M%S%fZ')}",
        analyzer=supplement.analyzer,
        analyzer_version=supplement.analyzer_version,
        started_at=now,
        completed_at=now,
        capabilities=tuple(item.name for item in supplement.capabilities),
        annotation_ids=added_annotation_ids,
    )
    return SemanticVideoDocument.model_validate(
        document.model_dump()
        | {
            "generated_at": now,
            "annotations": tuple(annotations.values()),
            "moments": tuple(moments.values()),
            "summaries": tuple(summaries.values()),
            "capabilities": tuple(capabilities.values()),
            "analysis_runs": (*document.analysis_runs, run),
        }
    )


def _covers(report: CapabilityReport, requested: TimeRange) -> bool:
    if report.status is CapabilityStatus.COMPLETE and not report.covered_ranges:
        return True
    return any(
        covered.start_fraction <= requested.start_fraction
        and requested.end_fraction <= covered.end_fraction
        for covered in report.covered_ranges
    )
