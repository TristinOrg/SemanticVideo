# Media inspection

Milestone 2 extracts deterministic technical metadata from a real media file.
It does not detect shots or describe the visible content.

## Requirements

Install FFmpeg and ensure `ffprobe` is on `PATH`, or pass its executable path:

```bash
semanticvideo inspect input.mp4 --ffprobe /path/to/ffprobe
```

SemanticVideo invokes ffprobe with a fixed argument list and without a shell:

```text
ffprobe -v error -print_format json -show_format -show_streams INPUT
```

The default timeout is 60 seconds and can be changed with `--timeout`.

## Usage

Pretty JSON is written to standard output:

```bash
semanticvideo inspect GX010231.MP4
```

For pipelines or files:

```bash
semanticvideo inspect GX010231.MP4 --compact
semanticvideo inspect GX010231.MP4 --output GX010231.inspect.json
```

Expected media, ffprobe, parse, and output errors use exit code 1 and a concise
diagnostic on standard error. Argument errors use argparse's exit code 2.

## Extracted information

The validated `MediaInfo` result includes:

- deterministic asset ID derived from the resolved file URI
- original input URI, file size, and filesystem modification time
- exact positive duration represented as integer ticks
- embedded creation time, container format, and bitrate when present
- video codec and bitrate, dimensions, pixel format, frame rate, time base, display
  rotation, sample aspect ratio, color metadata, and a conservative VFR hint
- audio codec and bitrate, sample rate, channel count/layout, language, and time base
- subtitle codec and language
- string-valued container tags for later evidence or identity decisions

Data and attachment streams are ignored in v0.1 because the core schema does
not yet model them.

## Duration fallback

The parser uses container duration when positive. If unavailable, it selects
the longest positive stream duration. A stream may express duration directly
in seconds or as `duration_ts * time_base`. Missing or non-positive duration is
an error because the core media schema requires a bounded timeline.

## Frame-rate limitation

`variable_frame_rate` compares ffprobe's average and nominal frame rates. A
difference is useful evidence of VFR, but equality does not prove that every
frame interval is constant. Later analysis may inspect packet timestamps when
an editing workflow requires stronger guarantees.

## Identity and hashing

The asset ID is deterministic for a resolved local URI; it is not a content
hash. M2 deliberately avoids hashing large video files. A future cache strategy
will define fast fingerprints and optional SHA-256 verification separately.
