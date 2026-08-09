"""Aggregate document integrity and serialization tests."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from semanticvideo import SemanticVideoDocument

EXAMPLE = (
    Path(__file__).parents[1] / "examples" / "japan-trip" / "GX010231.semantic.json"
)
CANONICAL_SCHEMA = Path(__file__).parents[1] / "semanticvideo.schema.json"


def test_valid_document_roundtrip(valid_document_data: dict[str, Any]) -> None:
    document = SemanticVideoDocument.model_validate(valid_document_data)
    restored = SemanticVideoDocument.model_validate_json(document.model_dump_json())

    assert restored == document
    assert restored.media.duration.seconds == 10


def test_japan_trip_example_is_valid() -> None:
    document = SemanticVideoDocument.model_validate_json(
        EXAMPLE.read_text(encoding="utf-8")
    )

    assert document.document_id == "document.GX010231"
    assert len(document.annotations) == 4


def test_json_schema_contains_discriminated_annotations() -> None:
    schema = SemanticVideoDocument.model_json_schema()
    rendered = json.dumps(schema)

    assert schema["title"] == "SemanticVideoDocument"
    assert "SceneAnnotation" in rendered
    assert "CustomAnnotation" in rendered
    assert "discriminator" in rendered


def test_committed_json_schema_is_current() -> None:
    assert json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8")) == (
        SemanticVideoDocument.model_json_schema()
    )


def test_duplicate_ids_are_rejected(valid_document_data: dict[str, Any]) -> None:
    duplicate = copy.deepcopy(valid_document_data["annotations"][0])
    valid_document_data["annotations"].append(duplicate)

    with pytest.raises(ValidationError, match="annotation IDs must be unique"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_out_of_bounds_segment_is_rejected(
    valid_document_data: dict[str, Any],
) -> None:
    valid_document_data["segments"][0]["time_range"]["duration"]["value"] = 11_000

    with pytest.raises(ValidationError, match="exceeds media duration"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_out_of_bounds_annotation_is_rejected(
    valid_document_data: dict[str, Any],
) -> None:
    valid_document_data["annotations"][0]["time_range"]["start"]["value"] = 9000
    valid_document_data["annotations"][0]["time_range"]["duration"]["value"] = 2000

    with pytest.raises(ValidationError, match="exceeds media duration"):
        SemanticVideoDocument.model_validate(valid_document_data)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["segments"][0].update(parent_id="missing"),
            "segment parent",
        ),
        (
            lambda data: data["segments"][0].update(parent_id="shot.1"),
            "own parent",
        ),
        (
            lambda data: data["segments"][0].update(annotation_ids=["missing"]),
            "segment annotation",
        ),
        (
            lambda data: data["annotations"][0].update(stream_id="missing"),
            "annotation stream",
        ),
    ],
)
def test_unknown_references_are_rejected(
    valid_document_data: dict[str, Any], mutation: Any, message: str
) -> None:
    mutation(valid_document_data)

    with pytest.raises(ValidationError, match=message):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_machine_annotation_requires_provenance(
    valid_document_data: dict[str, Any],
) -> None:
    annotation = valid_document_data["annotations"][0]
    annotation["status"] = "machine_generated"
    annotation["provenance"] = []

    with pytest.raises(ValidationError, match="requires provenance"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_unknown_entity_reference_is_rejected(
    valid_document_data: dict[str, Any],
) -> None:
    annotation = valid_document_data["annotations"][0]
    annotation["kind"] = "subject"
    annotation["value"] = {
        "type": "person",
        "label": "guest",
        "entity_id": "person.missing",
    }

    with pytest.raises(ValidationError, match="annotation entity"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_unknown_event_participant_is_rejected(
    valid_document_data: dict[str, Any],
) -> None:
    annotation = valid_document_data["annotations"][0]
    annotation["kind"] = "event"
    annotation["value"] = {
        "type": "walking",
        "description": "A guest walks",
        "participant_entity_ids": ["person.missing"],
    }

    with pytest.raises(ValidationError, match="event participant"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_speech_word_must_be_inside_utterance(
    valid_document_data: dict[str, Any],
) -> None:
    annotation = valid_document_data["annotations"][0]
    annotation["kind"] = "speech"
    annotation["value"] = {
        "text": "hello",
        "language": "en",
        "speaker_entity_id": "person.host",
        "words": [
            {
                "text": "hello",
                "time_range": {
                    "start": {"value": 6000, "rate": 1000},
                    "duration": {"value": 500, "rate": 1000},
                },
            }
        ],
    }

    with pytest.raises(ValidationError, match="word range"):
        SemanticVideoDocument.model_validate(valid_document_data)


def test_unknown_artifact_and_analysis_references_are_rejected(
    valid_document_data: dict[str, Any],
) -> None:
    valid_document_data["annotations"][0]["evidence"] = [
        {"type": "frame", "artifact_id": "artifact.missing"}
    ]
    with pytest.raises(ValidationError, match="evidence artifact"):
        SemanticVideoDocument.model_validate(valid_document_data)

    valid_document_data["annotations"][0]["evidence"] = []
    valid_document_data["analysis_runs"] = [
        {
            "id": "run.1",
            "analyzer": "test",
            "analyzer_version": "1",
            "started_at": "2026-08-09T00:00:00Z",
            "annotation_ids": ["annotation.missing"],
        }
    ]
    with pytest.raises(ValidationError, match="analysis annotation"):
        SemanticVideoDocument.model_validate(valid_document_data)
