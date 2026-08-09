# Editing and rendering

SemanticVideo keeps observations and edit decisions in the same validated manifest,
while leaving source pixels in the original media. An `EditPlan` is an ordered list
of source ranges; it is reviewable JSON and can be rendered deterministically.

## Create a rough-cut plan

```powershell
uv run semanticvideo plan input.semantic.json `
  --target-duration 60 `
  --maximum-clip-duration 8
```

The planner uses structured `editorial` annotations rather than parsing scene prose.
It removes shots marked unusable, applies recommended in/out ranges, keeps the
highest-scoring member of each duplicate group, ranks by interest and quality, and
then restores source order. The optional target duration trims only the final
selected clip needed to meet the limit.
`--maximum-clip-duration` caps long source ranges so a short target can include more
than one shot and produce a better-paced assembly.

By default the command atomically updates the input manifest. Use `--output` to keep
the analyzed manifest unchanged, or `--ranked-order` to keep score order instead of
source chronology.

Every generated clip records its source segment, exact source range, timeline order,
and selection reason. The document validator rejects unknown segments and ranges
outside their source shot.

## Render the latest plan

```powershell
uv run semanticvideo render input.semantic.json `
  --output input.roughcut.mp4
```

Use `--plan-id` to select an older plan and `--overwrite` to replace an existing
render. The renderer:

- invokes FFmpeg directly without a shell
- trims video and audio against the same exact ranges
- resets clip timestamps and concatenates in plan order
- produces H.264/AAC MP4 with a broadly compatible pixel format
- renders to a temporary sibling file and only replaces the destination on success
- refuses to overwrite the source media

Rendering deliberately re-encodes at cut boundaries. Stream-copy and transition
strategies can be added later without changing the stored `EditPlan` contract.

## Complete keyless workflow

```powershell
uv run semanticvideo prepare-agent input.mp4 --output input.task
# Let Codex or another agent complete input.task/response.json.
uv run semanticvideo analyze input.mp4 `
  --agent-response input.task/response.json `
  --output input.semantic.json
uv run semanticvideo plan input.semantic.json --target-duration 60
uv run semanticvideo render input.semantic.json --output input.roughcut.mp4
```

None of these commands requires an API key when an already-running agent supplies
the response file. The standalone OpenAI adapters remain optional for unattended API
workflows.
