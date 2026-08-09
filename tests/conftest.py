"""Reusable schema fixtures."""

from datetime import UTC, datetime
from typing import Any

import pytest


@pytest.fixture
def valid_document_data() -> dict[str, Any]:
    """Return a minimal valid document as mutable input data."""

    generated = datetime(2026, 8, 9, tzinfo=UTC).isoformat()
    return {
        "document_id": "document.test",
        "generated_at": generated,
        "media": {
            "id": "asset.test",
            "uri": "test.mp4",
            "duration": {"value": 10_000, "rate": 1000},
            "streams": [
                {
                    "kind": "video",
                    "id": "stream.video.0",
                    "index": 0,
                    "codec": "h264",
                    "width": 1920,
                    "height": 1080,
                }
            ],
        },
        "entities": [{"id": "person.host", "type": "person", "label": "host"}],
        "segments": [
            {
                "id": "shot.1",
                "kind": "shot",
                "time_range": {
                    "start": {"value": 0, "rate": 1000},
                    "duration": {"value": 5000, "rate": 1000},
                },
                "representative_times": [{"value": 2500, "rate": 1000}],
                "annotation_ids": ["annotation.scene.1"],
            }
        ],
        "annotations": [
            {
                "id": "annotation.scene.1",
                "kind": "scene",
                "time_range": {
                    "start": {"value": 0, "rate": 1000},
                    "duration": {"value": 5000, "rate": 1000},
                },
                "status": "human_authored",
                "provenance": [{"source": "manual", "generated_at": generated}],
                "value": {"description": "Host walks through a station"},
            }
        ],
    }
