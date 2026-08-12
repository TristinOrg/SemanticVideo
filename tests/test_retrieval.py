"""Derived semantic retrieval tests."""

from datetime import UTC, datetime
from pathlib import Path

from semanticvideo.retrieval import index_document, load_index, search, write_index
from semanticvideo.schema import (
    MediaInfo,
    RationalTime,
    SemanticMoment,
    SemanticVideoDocument,
    TimeRange,
    VideoStream,
)


def document() -> SemanticVideoDocument:
    time_range = TimeRange(
        start=RationalTime(value=0, rate=1), duration=RationalTime(value=5, rate=1)
    )
    return SemanticVideoDocument(
        document_id="document.tokyo",
        generated_at=datetime.now(UTC),
        media=MediaInfo(
            id="asset.tokyo",
            uri="tokyo.mp4",
            duration=RationalTime(value=5, rate=1),
            streams=(
                VideoStream(
                    id="stream.video.0",
                    index=0,
                    codec="h264",
                    width=1920,
                    height=1080,
                ),
            ),
        ),
        moments=(
            SemanticMoment(
                id="moment.1",
                time_range=time_range,
                summary="Tokyo Tower observation deck",
                objects=("Conan display",),
            ),
        ),
    )


def test_index_search_and_jsonl_roundtrip(tmp_path: Path) -> None:
    records = index_document(document())
    hits = search(records, "Conan")
    assert hits[0].record.source_id == "moment.1"
    assert search(records, "aquarium") == ()
    output = tmp_path / "semantic.index.jsonl"
    assert write_index((document(),), output) == 1
    assert load_index(output) == records


def test_search_validates_limit() -> None:
    try:
        search(index_document(document()), "Tokyo", limit=0)
    except ValueError as error:
        assert "greater than zero" in str(error)
    else:
        raise AssertionError("expected invalid limit")
