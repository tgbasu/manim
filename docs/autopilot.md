# Reel autopilot

`python -m reelstudio.autopilot` turns a topic into a published, narrated,
captioned 9:16 data-science reel with no manual editing:

```text
topic queue ─► writer ─► storyboard ─► voice ─► StoryReel render ─► mix ─► publish
(topics.yml)   Claude /   (YAML,       per-beat   (Manim, timed to    FFmpeg  local / YouTube /
               open LLM / reviewable)  TTS,       the measured        +music  Instagram,
               library                 measured   speech)                     logged once
```

The **storyboard** is the contract between stages. It is plain YAML, so you
can read, edit, or hand-write one, and every stage can be swapped without
touching the others.

## Quick start (offline, no accounts)

The bundled `data_stories` project runs with nothing but the engine installed:
it uses hand-written storyboards, estimated timing, silent audio, and a local
outbox.

```powershell
python -m reelstudio.autopilot status
python -m reelstudio.autopilot run --draft          # 360x640 preview of the next topic
python -m reelstudio.autopilot make projects/data_stories/storyboards/overfitting.yml
```

Each run writes to `videos/data_stories/runs/<slug>/final/` (or `draft/`):

| File | Purpose |
| --- | --- |
| `final.mp4` | Upload-ready 1080x1920 reel with voice and music |
| `cover.png` | Thumbnail with the storyboard's `cover_title` |
| `captions.srt` | Captions for platforms that accept caption files |
| `storyboard.json` | The storyboard with measured beat durations |
| `metadata.json` | Title, post caption, hashtags, sources, duration |

The local publisher copies the reel, cover, captions, and a ready-to-paste
`post.txt` to `videos/<project>/outbox/<slug>/`.

## Plug in AI and open-source models

Install the optional providers once:

```powershell
python -m pip install -r requirements-ai.txt
```

Then choose providers under `autopilot:` in `projects/data_stories/project.yml`.

### Writers (script and storyboard)

| `writer.provider` | What it uses | Setup |
| --- | --- | --- |
| `library` | Storyboards in `projects/<name>/storyboards/` | None; default |
| `anthropic` | Claude via the official SDK, constrained to the storyboard JSON schema | `ANTHROPIC_API_KEY` |
| `openai` | Any OpenAI-compatible chat server: Ollama, LM Studio, vLLM, llama.cpp, Groq, OpenAI | `base_url` or `LLM_BASE_URL`, plus `OPENAI_API_KEY` for hosted APIs |

```yaml
writer:
  provider: anthropic
  model: claude-opus-5-5
  effort: medium            # low | medium | high | xhigh | max

writer:                     # fully open source, local
  provider: openai
  base_url: http://localhost:11434/v1
  model: qwen3:14b
```

Claude requests opt into server-side refusal fallbacks (`fallbacks: "default"`),
so a declined request is retried on a suitable model automatically. Every
writer's output passes `reelstudio/storyboard.py` validation. On failure, the
exact errors go back to the model for repair, up to three attempts, so a bad
script never reaches the renderer. The writer prompt asks for a hook in the
first beat, one idea told as a story, a looping last line, and honest numbers:
invented figures are labeled "illustrative" and sources are never fabricated.

```powershell
python -m reelstudio.autopilot ideas --count 15     # brainstorm and queue topics
python -m reelstudio.autopilot write "Simpson's paradox" --angle "A drug that wins in every group but loses overall"
```

`write` saves `projects/<name>/storyboards/<slug>.yml` for review. `run` reuses
a saved storyboard when one exists, so you can edit any script before it goes out.

### Voices (narration)

| `voice.provider` | What it uses | Example settings |
| --- | --- | --- |
| `silent` | No audio; timing estimated from word counts | default |
| `edge` | Free Microsoft Edge neural voices (`edge-tts`; needs network) | `voice: en-US-AndrewMultilingualNeural`, `rate: "+5%"` |
| `piper` | Local open-source Piper TTS | `model: voices/en_US-ryan-medium.onnx` |
| `openai` | OpenAI speech, or local open-source servers with the same API (Kokoro-FastAPI, openedai-speech) | `base_url: http://localhost:8880/v1`, `voice: af_heart`, `model: kokoro` |

Each beat is synthesized separately and measured. The beat's duration becomes
`0.15 s lead + speech + 0.35 s tail`, the scene renders to exactly those
durations, and the clips are placed on one loudness-normalized track at the
same offsets. Voice, captions, and visuals start together on every beat
without manual alignment.

### Publishers

| Platform | Credentials (environment variables) | Notes |
| --- | --- | --- |
| `local` | none | Outbox folder with `post.txt` |
| `youtube` | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | YouTube Data API v3 resumable upload; vertical videos under 3 minutes become Shorts. `youtube.privacy` defaults to `private`; set `public` once you trust the pipeline |
| `instagram` | `INSTAGRAM_USER_ID`, `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API resumable Reels upload, processing poll, then publish. Requires a Business or Creator account |

```powershell
python -m reelstudio.autopilot run --publish local,youtube,instagram
```

To get a YouTube refresh token, create an OAuth client (Desktop app) in Google
Cloud with the YouTube Data API v3 enabled, authorize the
`https://www.googleapis.com/auth/youtube.upload` scope once, and store the
refresh token. Unverified Google Cloud projects can only upload private
videos until the project passes Google's audit. For Instagram, use a long-lived
token with `instagram_business_basic` and `instagram_business_content_publish`
(Instagram Login) or `instagram_content_publish` (Facebook Login). Set
`instagram.graph_host: https://graph.instagram.com` for Instagram Login tokens.
Both platforms enforce daily posting limits.

The YouTube and Instagram publishers are tested against recorded request
flows, not live accounts. Run your first upload with `privacy: private` and
check the result before enabling scheduled public posts.

Publications are logged in `projects/<name>/published.yml` after each
successful upload. A topic leaves the queue once it is logged for every target
platform, and a rerun skips platforms that already have it, so a failure
halfway never causes a double post. Draft renders are never logged or
published remotely.

## Run on a schedule

### GitHub Actions (no computer required)

`.github/workflows/reel-autopilot.yml` installs the engine on a stock Ubuntu
runner, renders with a software Vulkan driver (lavapipe), publishes, uploads
the reel as a workflow artifact, and commits `published.yml` and any new
storyboards back so the next run continues the queue.

1. Add the secrets you need under **Settings → Secrets and variables → Actions**:
   `ANTHROPIC_API_KEY`, `YOUTUBE_*`, `INSTAGRAM_*`.
2. Switch `writer.provider` to `anthropic` (or `openai` with `LLM_BASE_URL`)
   so the queue is not limited to the bundled storyboards.
3. Trigger it manually from the **Actions** tab to check one run.
4. Set the repository variables `AUTOPILOT_ENABLED=true` and, for example,
   `AUTOPILOT_PUBLISH=youtube,instagram` to post daily at 14:23 UTC. Edit the
   `cron` line to change the time.

Rendering needs no GPU: during testing, a 43-second 1080p reel with narration
took about a minute end to end on 4 CPU cores with lavapipe.

### Local cron or Task Scheduler

```bash
# crontab -e: every day at 18:05
5 18 * * * cd /path/to/manim && .venv/bin/python -m reelstudio.autopilot run >> videos/autopilot.log 2>&1
```

Commit `published.yml` occasionally so the log survives a fresh clone.

## Storyboard format

```yaml
topic: The accuracy paradox
title: My model was 99% accurate. It caught zero fraud. #Shorts
cover_title: 99% accurate. Totally useless.
beats:
  - title: 99% accurate. Totally useless.     # on-screen headline
    narration: My fraud model scored ninety-nine percent accuracy...
    visual: {kind: statement}
  - title: The data
    narration: Out of ten thousand transactions, only one hundred were fraud.
    visual: {kind: bars, labels: [Legit, Fraud], values: [9900, 100], highlight: 1}
post_caption: |-
  99% accuracy sounds amazing until...
  Have you ever been fooled by a metric?
hashtags: [datascience, machinelearning]
sources: []
```

Visual kinds: `statement`, `stat` (counting number), `bars`, `line`
(multi-series with a marked point), `scatter` (optional regression line with R²,
or colored clusters), `distribution` (normal curve with a computed shaded
probability), `flow` (pipeline with a moving data packet), `matrix` (confusion
matrix), `compare` (two columns), `bullets`, and `code`. Field definitions and
limits live in `VISUALS` in `reelstudio/storyboard.py`; builders are in
`reelstudio/shared/visuals.py`. To add a visual, add its spec to `VISUALS` and
a builder to `BUILDERS`; writers learn about it automatically because the
prompt and JSON schema are generated from `VISUALS`.

Preview one storyboard through the regular renderer without voice:

```powershell
python -m reelstudio --project data_stories --storyboard projects/data_stories/storyboards/overfitting.yml --draft
```

## Start another channel

Copy `projects/data_stories/` to `projects/<new_channel>/`, edit
`autopilot.brand`, `autopilot.channel`, and `topics.yml`, then pass
`--project <new_channel>`. The same StoryReel scene renders any subject the
visual kinds can express.

## Tests

`python -m unittest tests.test_autopilot` checks storyboard validation, the
writer repair loop, measured voice timing with real FFmpeg audio, the YouTube
and Instagram request flows, and the publication log, all without network
access or a GPU.
