"""Visual description provider tests."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from semanticvideo.errors import DescriptionProviderError
from semanticvideo.providers import JsonFileShotDescriber, OpenAIShotDescriber


def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_json_provider_validates_and_resolves_shots(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "descriptions.json",
        {"shot.0001": {"description": "Traveler enters a station"}},
    )
    provider = JsonFileShotDescriber(path)

    result = provider.describe("shot.0001", (), language="en")
    assert result.description is not None
    assert result.description.startswith("Traveler")
    with pytest.raises(DescriptionProviderError, match="no entry"):
        provider.describe("shot.0002", (), language="en")


@pytest.mark.parametrize("content", ["not json", "[]"])
def test_json_provider_rejects_invalid_root(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(DescriptionProviderError):
        JsonFileShotDescriber(path)


def test_json_provider_reports_invalid_description(tmp_path: Path) -> None:
    provider = JsonFileShotDescriber(
        write_json(tmp_path / "bad.json", {"shot.0001": {}})
    )
    with pytest.raises(DescriptionProviderError, match="invalid description"):
        provider.describe("shot.0001", (), language="en")


class FakeResponses:
    def __init__(
        self, output: str | None = None, error: Exception | None = None
    ) -> None:
        self.output = output
        self.error = error
        self.arguments: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_text=self.output)


def test_openai_provider_sends_image_and_parses_structured_output(
    tmp_path: Path,
) -> None:
    responses = FakeResponses('{"description":"A train crosses a bridge"}')
    client = SimpleNamespace(responses=responses)
    provider = OpenAIShotDescriber(model="vision-test", client=client)
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")

    result = provider.describe("shot.0001", (frame,), language="zh-CN")

    assert result.description == "A train crosses a bridge"
    assert responses.arguments["model"] == "vision-test"
    content = responses.arguments["input"][0]["content"]
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert "zh-CN" in content[0]["text"]
    schema = responses.arguments["text"]["format"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert "default" not in json.dumps(schema)


def test_openai_provider_reports_missing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(DescriptionProviderError, match="OPENAI_API_KEY"):
        OpenAIShotDescriber()


def test_openai_provider_reports_bad_responses(tmp_path: Path) -> None:
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    provider = OpenAIShotDescriber(
        client=SimpleNamespace(responses=FakeResponses(None))
    )
    with pytest.raises(DescriptionProviderError, match="no structured text"):
        provider.describe("shot.0001", (frame,), language="en")
    with pytest.raises(DescriptionProviderError, match="no representative"):
        provider.describe("shot.0001", (), language="en")

    failing = OpenAIShotDescriber(
        client=SimpleNamespace(responses=FakeResponses(error=RuntimeError("offline")))
    )
    with pytest.raises(DescriptionProviderError, match="offline"):
        failing.describe("shot.0001", (frame,), language="en")
