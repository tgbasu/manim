# Repository Guidelines

## Project Structure & Module Organization

This repository combines ManimGL (`manimgl`, imported as `manimlib`) with a reusable reel-production workspace. Python 3.10+ is required. `manimlib/` contains the engine, including the wgpu renderer and WGSL shaders. Add video-specific code to `reelstudio/scenes/`, shared layouts and components to `reelstudio/shared/`, and production utilities to `reelstudio/render.py` or `media.py`.

`projects/<name>/project.yml` lists each series' scene file and classes; `scripts/` holds narration. Storyboard projects such as `data_stories` add an `autopilot:` section, `storyboards/`, `topics.yml`, and the committed `published.yml` log. The autopilot pipeline lives in `reelstudio/storyboard.py` (contract), `writers.py`, `voices.py`, `publishers.py`, and `autopilot.py`; `reelstudio/scenes/story_reel.py` renders any storyboard and `reelstudio/shared/visuals.py` holds its visual builders. `configs/` contains render presets. `assets/` holds images and local audio. Generated videos belong in ignored `videos/`. `tests/` contains engine and production checks; `docs/reelstudio.md` explains the workflow. Root reel scripts remain compatibility entry points.

## Build, Test, and Development Commands

Run from the repository root in an activated environment:

- `python -m pip install -e .`: install the editable engine.
- `python -m pip install -r requirements.txt -r requirements-reels.txt`: install runtime dependencies and bundled FFmpeg support.
- `python -m reelstudio --list`: list the default math series.
- `python -m reelstudio --project getting_started --draft`: render the 2D starter.
- `python -m reelstudio LinearReel --voiceover assets/audio/LinearReel.wav`: render and mix narration.
- `python -m reelstudio --stills`: export math-series covers.
- `python -m pip install -r requirements-ai.txt`: optional Claude writer and Edge voice.
- `python -m reelstudio.autopilot run --draft`: produce the next queued data story offline.
- `python -m reelstudio.autopilot make projects/data_stories/storyboards/overfitting.yml`: voice, render, and mix one storyboard.
- `python -m unittest tests.test_reelstudio tests.test_autopilot`: run production and autopilot checks.
- `python -m pytest tests/`: run the full unit suite after installing pytest.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and modules, `PascalCase` scenes, and uppercase constants. Follow surrounding type annotation conventions. No formatter or linter is configured. Prefer reusable portrait components over duplicated layouts. Use explicit UTF-8 for text files. Keep Python GPU record layouts consistent with WGSL when changing engine code.

## Testing Guidelines

Name tests `test_*.py` and test functions or methods `test_*`. No coverage threshold is configured. Verify changed scenes with covers and drafts; test audio duration and stream behavior for production changes. Renderer changes additionally require before/after comparisons using `tests/render_compare.py`.

## Commit & Pull Request Guidelines

Use concise imperative subjects; history also uses `docs:` prefixes. Follow `.github/PULL_REQUEST_TEMPLATE.md`, explain motivation, link relevant issues, report validation, and include visual comparisons for appearance changes.

## Configuration & Assets

Keep personal overrides in ignored `custom_config.yml`. API keys and platform tokens belong in environment variables or CI secrets, never in project files; new visual kinds go in `VISUALS` and `BUILDERS` so prompts and schemas stay generated. Commit narration scripts; keep recordings, music, videos, caches, and environments out of Git. Record asset sources where needed. The manual render CLI mixes supplied recordings; the autopilot generates narration through the providers in `reelstudio/voices.py`.
