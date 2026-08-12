"""Provider-neutral derived text index for semantic manifests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import Field

from semanticvideo.schema import SemanticVideoDocument, TimeRange
from semanticvideo.schema._base import SemanticModel

_TERMS = re.compile(r"[\w\u3400-\u9fff]+", re.UNICODE)


class SearchRecord(SemanticModel):
    """One disposable index row linked to the authoritative manifest."""

    document_id: str
    media_uri: str
    source_id: str
    kind: str
    text: str = Field(min_length=1)
    time_range: TimeRange | None = None
    terms: tuple[str, ...] = ()


class SearchHit(SemanticModel):
    record: SearchRecord
    score: float = Field(ge=0, le=1)


def index_document(document: SemanticVideoDocument) -> tuple[SearchRecord, ...]:
    """Derive searchable rows without changing the portable source manifest."""

    rows: list[SearchRecord] = []
    for summary in document.summaries:
        rows.append(
            _record(
                document,
                summary.id,
                f"summary:{summary.level}",
                summary.text,
                summary.time_range,
            )
        )
    for moment in document.moments:
        text = " ".join(
            (
                moment.summary,
                *moment.subjects,
                *moment.actions,
                *moment.objects,
                *moment.visible_text,
            )
        )
        rows.append(_record(document, moment.id, "moment", text, moment.time_range))
    for annotation in document.annotations:
        value = annotation.value.model_dump(exclude_none=True)
        text = " ".join(_strings(value))
        if text:
            rows.append(
                _record(
                    document,
                    annotation.id,
                    f"annotation:{annotation.kind}",
                    text,
                    annotation.time_range,
                )
            )
    return tuple(rows)


def write_index(documents: Iterable[SemanticVideoDocument], output: Path) -> int:
    """Write a deterministic JSONL index that can always be rebuilt."""

    records = sorted(
        (record for document in documents for record in index_document(document)),
        key=lambda item: (item.document_id, item.source_id),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{record.model_dump_json(exclude_none=True)}\n" for record in records),
        encoding="utf-8",
    )
    return len(records)


def load_index(path: Path) -> tuple[SearchRecord, ...]:
    return tuple(
        SearchRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def search(
    records: Iterable[SearchRecord], query: str, *, limit: int = 20
) -> tuple[SearchHit, ...]:
    """Rank exact normalized term overlap with a small phrase-match boost."""

    if limit <= 0:
        raise ValueError("search limit must be greater than zero")
    query_terms = set(_terms(query))
    if not query_terms:
        return ()
    normalized_query = " ".join(_terms(query))
    hits: list[SearchHit] = []
    for record in records:
        overlap = query_terms & set(record.terms)
        if not overlap:
            continue
        score = len(overlap) / len(query_terms)
        if normalized_query and normalized_query in " ".join(record.terms):
            score = min(1.0, score + 0.15)
        hits.append(SearchHit(record=record, score=score))
    return tuple(
        sorted(hits, key=lambda item: (-item.score, item.record.source_id))[:limit]
    )


def read_documents(paths: Iterable[Path]) -> tuple[SemanticVideoDocument, ...]:
    return tuple(
        SemanticVideoDocument.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )


def _record(
    document: SemanticVideoDocument,
    source_id: str,
    kind: str,
    text: str,
    time_range: TimeRange,
) -> SearchRecord:
    cleaned = " ".join(text.split())
    return SearchRecord(
        document_id=document.document_id,
        media_uri=document.media.uri,
        source_id=source_id,
        kind=kind,
        text=cleaned,
        time_range=time_range,
        terms=_terms(cleaned),
    )


def _terms(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.casefold() for match in _TERMS.findall(value)))


def _strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)
