"""JSON Schema exporter tests."""

import json
from pathlib import Path

from semanticvideo.schema.export import main


def test_export_to_file(tmp_path: Path) -> None:
    output = tmp_path / "semanticvideo.schema.json"

    assert main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["title"] == (
        "SemanticVideoDocument"
    )


def test_export_to_stdout(capsys: object) -> None:
    assert main([]) == 0
    # pytest's fixture is intentionally duck-typed to keep runtime dependencies small.
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert json.loads(captured.out)["title"] == "SemanticVideoDocument"
