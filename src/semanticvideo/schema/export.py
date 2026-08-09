"""Command-line JSON Schema export."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from semanticvideo.schema.document import SemanticVideoDocument


def build_parser() -> argparse.ArgumentParser:
    """Build the schema exporter argument parser."""

    parser = argparse.ArgumentParser(
        description="Export the SemanticVideo JSON Schema."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file. Omit to write to stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Export the current document schema as stable, formatted JSON."""

    args = build_parser().parse_args(argv)
    rendered = json.dumps(
        SemanticVideoDocument.model_json_schema(),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    if args.output is None:
        sys.stdout.write(f"{rendered}\n")
    else:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
