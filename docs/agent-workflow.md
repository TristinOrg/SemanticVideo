# Agent-native workflow

SemanticVideo does not require an API key when Codex or another capable AI agent is
driving the workflow. The CLI prepares a bounded, portable evidence bundle; the agent
fills one provider-neutral response; the analyzer validates and merges it into the
same `.semantic.json` used by every other provider.

## 1. Prepare evidence

```powershell
uv run semanticvideo prepare-agent input.mp4 `
  --language zh-CN `
  --output input.task
```

The new directory contains:

- `task.json`: source-relative shot ranges, instructions, and evidence paths
- `frames/`: multiple representative JPEGs for every shot
- `audio.mp3`: compact mono audio when the source has an audio stream
- `response.template.json`: safe starting object for an agent
- `response.schema.json`: validation contract for the completed response

The command refuses to write into a non-empty directory so it cannot silently replace
an earlier task or agent response.

## 2. Let an agent complete the response

Ask the agent to read `task.json`, inspect every referenced image, listen to audio when
supported, and write `response.json`. The response can contain:

- structured shot summaries, environment, subjects, actions, objects, visible text,
  framing, movement, editorial role, and confidence
- optional timed transcript segments and words
- optional location only when evidence supports it

The response is data, not executable code. Import validates it with strict Pydantic
models and the public JSON Schema.

## 3. Generate the complete manifest

```powershell
uv run semanticvideo analyze input.mp4 `
  --agent-response input.task/response.json `
  --language zh-CN `
  --output input.semantic.json
```

No API key is read in this path. The agent response is combined with deterministic
media, shot, frame-quality, audio-level, location-metadata, editing, and relationship
analysis. Capability state records whether transcript and location were complete,
partial, or omitted.

## Optional unattended transcription

For an unattended service, install the OpenAI extra and configure an API key:

```powershell
uv sync --extra openai
$env:OPENAI_API_KEY = "..."
uv run semanticvideo analyze input.mp4 `
  --descriptions descriptions.json `
  --transcribe-openai
```

Word and segment timestamp mode intentionally uses `whisper-1`; the official API
currently limits `timestamp_granularities` to that model. Compressed task audio also
keeps ordinary recordings below the transcription endpoint's documented 25 MB file
limit, although callers should still check unusually long inputs.
