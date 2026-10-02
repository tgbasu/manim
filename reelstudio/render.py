"""Render project scenes, then optionally mix voiceover and music."""

import argparse
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml

from reelstudio.media import find_ffmpeg, mix_audio


ROOT = Path(__file__).resolve().parents[1]


def load_project(name):
    manifest = ROOT / "projects" / name / "project.yml"
    if not manifest.is_file():
        raise ValueError(f"Unknown project {name!r}; expected {manifest}")
    project = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(project, dict) or not isinstance(project.get("scenes"), list) or not project["scenes"]:
        raise ValueError(f"Project must define a nonempty scenes list: {manifest}")
    if any(not isinstance(scene, str) or not scene.isidentifier() for scene in project["scenes"]):
        raise ValueError("Scene names must be valid Python class names")
    scene_file = ROOT / project.get("scene_file", "")
    if not scene_file.is_file():
        raise ValueError(f"Scene file does not exist: {scene_file}")
    return project, scene_file


def narration_files(scenes, voiceover=None, audio_dir=None):
    if voiceover:
        if len(scenes) != 1:
            raise ValueError("--voiceover requires exactly one selected scene; use --audio-dir for a series")
        file = Path(voiceover).resolve()
        if not file.is_file():
            raise ValueError(f"Narration does not exist: {file}")
        return {scenes[0]: file}
    recordings = {}
    if audio_dir:
        directory = Path(audio_dir).resolve()
        for scene in scenes:
            candidates = [directory / f"{scene}{suffix}" for suffix in (".wav", ".mp3", ".m4a")]
            found = [file for file in candidates if file.is_file()]
            if len(found) != 1:
                raise ValueError(f"Expected one WAV, MP3, or M4A recording for {scene} in {directory}; found {len(found)}")
            recordings[scene] = found[0]
    return recordings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenes", nargs="*", help="Scene class names; default: all scenes in the project")
    parser.add_argument("--project", default="math_to_ml", help="Directory name under projects/")
    parser.add_argument("--list", action="store_true", help="List project scenes without rendering")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "portrait.yml")
    parser.add_argument("--output", type=Path, help="Output base directory; default: videos/<project>")
    parser.add_argument("--draft", action="store_true", help="360x640 at 15 fps")
    parser.add_argument("--stills", action="store_true", help="Save final-frame PNG covers")
    audio = parser.add_mutually_exclusive_group()
    audio.add_argument("--voiceover", type=Path, help="Narration for one selected scene")
    audio.add_argument("--audio-dir", type=Path, help="Directory containing <SceneName>.wav/mp3/m4a")
    parser.add_argument("--voiceover-offset", type=float, default=0, help="Delay narration by this many seconds")
    parser.add_argument("--music", type=Path, help="Music file to loop under the video")
    parser.add_argument("--music-volume", type=float, default=0.12, help="Music multiplier, between 0 and 1")
    args = parser.parse_args(argv)
    try:
        project, scene_file = load_project(args.project)
        selected = args.scenes or project["scenes"]
        if any(scene not in project["scenes"] for scene in selected):
            raise ValueError("Choose scenes from: " + ", ".join(project["scenes"]))
        if args.list:
            print(project.get("title", args.project))
            print("\n".join(project["scenes"]))
            return
        if args.stills and (args.voiceover or args.audio_dir or args.music):
            raise ValueError("Audio options cannot be combined with --stills")
        if not math.isfinite(args.voiceover_offset) or args.voiceover_offset < 0:
            raise ValueError("--voiceover-offset must be a finite nonnegative number")
        if not math.isfinite(args.music_volume) or not 0 <= args.music_volume <= 1:
            raise ValueError("--music-volume must be between 0 and 1")
        recordings = narration_files(selected, args.voiceover, args.audio_dir)
        music = args.music.resolve() if args.music else None
        if music and not music.is_file():
            raise ValueError(f"Music does not exist: {music}")
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("Render configuration must be a YAML mapping")
        output = args.output.resolve() if args.output else ROOT / "videos" / args.project
        if args.draft:
            output = output / "drafts"
            config.setdefault("camera", {}).update(resolution="(360, 640)", fps=15)
        destination = output / ("covers" if args.stills else "silent")
        directory_config = config.setdefault("directories", {})
        cache = ROOT / ".cache" / "reelstudio"
        cache.mkdir(parents=True, exist_ok=True)
        directory_config["cache"] = str(cache)
        directory_config["mirror_module_path"] = False
        directory_config.setdefault("subdirs", {})["output"] = str(destination)
        ffmpeg = find_ffmpeg() if not args.stills else None
        if ffmpeg:
            config.setdefault("file_writer", {})["ffmpeg_bin"] = ffmpeg
        # Each render owns its config, so concurrent jobs cannot overwrite settings.
        with tempfile.TemporaryDirectory(prefix="render-", dir=cache) as work:
            runtime_config = Path(work) / "config.yml"
            runtime_config.write_text(yaml.safe_dump(config), encoding="utf-8")
            command = [sys.executable, "-m", "manimlib", str(scene_file.relative_to(ROOT)),
                       *selected, "--config_file", str(runtime_config), "-w", "-q"]
            if args.stills:
                command.append("-s")
            subprocess.run(command, cwd=ROOT, check=True)
        for scene in selected:
            rendered = destination / f"{scene}{'.png' if args.stills else '.mp4'}"
            if not rendered.is_file():
                raise ValueError(f"Renderer did not create expected output: {rendered}")
            print(f"Rendered: {rendered}")
            if scene in recordings or music:
                final = mix_audio(rendered, output / "final" / f"{scene}.mp4", ffmpeg,
                                  voiceover=recordings.get(scene), music=music,
                                  offset=args.voiceover_offset, music_volume=args.music_volume)
                print(f"With audio: {final}")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"reelstudio: {error}\n")


if __name__ == "__main__":
    main()
