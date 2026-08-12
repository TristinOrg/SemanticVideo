# Video analysis

`semanticvideo analyze` is the end-to-end reusable-understanding path. It
uses FFprobe for source facts, FFmpeg for shot boundaries and representative JPEGs,
and a replaceable visual-description provider. The final deliverable is one
`.semantic.json`. Frames are temporary by default; `--evidence-dir` retains them
as reusable, checksummed artifacts linked from the manifest.

## Required output

The command treats the following as required rather than optional:

- source URI, exact duration, file size, container, codecs, dimensions, frame rate,
  audio sample rate, and channel count
- contiguous shot ranges covering the complete source duration
- three evenly spaced representative timestamps inside every shot by default
- one structured scene annotation for every shot
- provenance, evidence timestamp, provider/model identity, and analysis parameters

If any representative frame or description cannot be produced, the command exits
with an error and does not pretend that the analysis is complete.

Scene annotations include a concise description plus optional environment, subjects,
actions, objects, visible text, location hint, shot type, camera movement, editorial
role, and confidence. Unknown values remain empty instead of being guessed.

## Deterministic editing signals

The default pipeline does not require a model for basic editing fitness. It measures
representative-frame exposure, edge-based sharpness, visual change, average-hash
similarity, and per-shot mean/peak audio level. These measurements produce quality,
interest, usability, conservative trim handles, duplicate groups, and same-scene or
duplicate relations. Reasons retain the component values so heuristics remain
reviewable rather than looking like model facts.

`--frames-per-shot` accepts 1 through 9. Three frames balance temporal evidence and
cost; visual model providers receive all sampled images in one shot request.

Embedded location tags are parsed separately from visual `location_hint` guesses.
ISO-6709 coordinates become a typed geographic point with metadata-key evidence. If
no location exists, the capability is explicitly marked `omitted`.

## OpenAI provider

Install the optional dependency and configure the API key in the environment:

```powershell
uv sync --extra openai
$env:OPENAI_API_KEY = "..."
uv run semanticvideo analyze input.mp4 --language zh-CN
```

The adapter submits representative images through the Responses API and requests a
strict JSON Schema result. The core pipeline only depends on the `ShotDescriber`
contract, so local or other hosted models can be added without changing the format.

The default model is `gpt-5.6`; use `--model` to choose another compatible model.
The key is read from `OPENAI_API_KEY` and is never stored in the output manifest.

## Reviewed JSON provider

For offline runs, human review, or another vision system, provide a JSON object whose
keys match generated shot IDs:

```json
{
  "shot.0001": {
    "description": "A traveler walks through a railway station.",
    "environment": ["indoor station"],
    "subjects": ["traveler"],
    "actions": ["walking"],
    "objects": ["luggage"],
    "shot_type": "wide shot"
  }
}
```

Run it with:

```powershell
uv run semanticvideo analyze input.mp4 --descriptions descriptions.json
```

## Optional information

Core editing facts are always present. Repeat `--include` to add information:

| Value | Additional content |
| --- | --- |
| `technical` | bitrate, pixel format, time bases, aspect ratio, color and VFR hints |
| `metadata` | embedded tags and filesystem/embedded timestamps |
| `checksum` | SHA-256 of the complete source file |
| `raw` | namespaced raw FFprobe response under `extensions` |

For example:

```powershell
uv run semanticvideo analyze input.mp4 `
  --include technical `
  --include metadata `
  --output input.semantic.json
```

## Shot controls

`--scene-threshold` is FFmpeg's scene-change threshold and must be between zero and
one. Lower values detect more cuts. `--minimum-shot-duration` removes very short
detections and defaults to 0.5 seconds. Both values are persisted in `analysis_runs`
so the result can be reproduced and compared.
