# Reel production guide

This workspace combines the local ManimGL engine with a small production layer
for short educational videos. It supports 2D diagrams, function animations,
portrait exports, recorded voiceover, and optional background music.

## Repository layout

```text
manimlib/                   ManimGL engine
reelstudio/
  scenes/                   Episode-specific animations
  shared/                   Portrait layout, theme, and diagram components
  render.py                 Project-based render CLI
  media.py                  FFmpeg narration/music mixing
configs/portrait.yml        Default 1080x1920, 30 fps settings
projects/<project>/
  project.yml               Scene entry file and scene class names
  scripts/                  Voiceover scripts and editorial notes
assets/audio/               Local recordings and music (ignored)
assets/images/              Reusable image assets
videos/<project>/           Generated media (ignored)
tests/                      Engine and production-tool tests
```

## Setup and first render

Use Python 3.10+ and a GPU supported by this checkout's wgpu renderer.
From the repository root, activate your environment and run:

```powershell
python -m pip install -e .
python -m pip install -r requirements.txt -r requirements-reels.txt
python -m reelstudio --list
python -m reelstudio --project getting_started --draft
python -m reelstudio LinearReel --draft
python -m reelstudio LinearReel
python -m reelstudio --stills
```

Silent MP4s go into `videos/<project>/silent/`, audio mixes into `final/`, and
PNG covers into `covers/`. Drafts use the same folders beneath `drafts/` and
render at 360x640, 15 fps. Drafts are for review; default settings produce final
1080x1920 videos. Rendering without audio is supported.

## Include voiceover and music

Record a project script using your microphone or an external voice tool,
then provide its WAV, MP3, or M4A file:

```powershell
python -m reelstudio LinearReel --voiceover assets/audio/LinearReel.wav
python -m reelstudio --project getting_started --voiceover assets/audio/PredictionPipeline.wav
python -m reelstudio LinearReel --voiceover assets/audio/LinearReel.wav --voiceover-offset 1.5
python -m reelstudio LinearReel --voiceover assets/audio/LinearReel.wav --music assets/audio/music.mp3 --music-volume 0.10
python -m reelstudio --audio-dir assets/audio
```

`--voiceover` applies to exactly one selected scene. `--audio-dir` requires one
matching `<SceneName>.wav`, `.mp3`, or `.m4a` per selected scene; missing or ambiguous
recordings fail before rendering. Background music loops and is mixed at the
requested volume multiplier. Narration starts at zero unless delayed.

Mixing preserves the silent source. Short narration leaves the remainder silent;
long narration extends the video by freezing its final frame. This prevents
truncation but does **not** synchronize speech to individual animation beats.
Adjust `play(run_time=...)` and `wait(...)` to align speech with visuals. Automatic
speech generation, word-level captions, and timeline editing are not included.

## Create another video project

1. Add a scene module in `reelstudio/scenes/`. Subclass `PortraitScene` from
   `reelstudio.shared.base`; use `concept_card` for 2D flow diagrams. Inspect
   `prediction_pipeline.py` as a complete example. Math lessons can subclass
   `MathReel` and supply a function, three input steps, and explanations.
2. Create `projects/my_series/project.yml`:

   ```yaml
   title: My series
   scene_file: reelstudio/scenes/my_series.py
   scenes:
     - MyFirstScene
   ```

3. Put narration in `projects/my_series/scripts/`, recordings in `assets/audio/`,
   and image assets in `assets/images/`.
4. Run `python -m reelstudio --project my_series --draft`, review the output,
   then render without `--draft` and include audio when ready.

Use `--config path/to/config.yml` to override settings and `--output path` to
change the output base. The shared layout is portrait; landscape scenes need
their own frame layout as well as a matching resolution preset.

## Compatibility and verification

`math_reels.py` exposes compatibility subclasses for the six scenes, and `render_math_reels.py`
forwards to the new CLI. Existing invocations still work; the render helper's
output now follows `videos/math_to_ml/`. Old exports in `videos/math_reels/`
remain available. `reels_config.yml` remains a direct-Manim configuration.

Run `python -m unittest discover -s tests -p test_reelstudio.py` for production
tests, including real FFmpeg checks when FFmpeg is available. Use
`python -m reelstudio --stills` to check layouts and a draft render to check motion.
