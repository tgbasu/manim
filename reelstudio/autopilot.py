"""Idea -> script -> voice -> animation -> mix -> publish, in one command.

    python -m reelstudio.autopilot status
    python -m reelstudio.autopilot ideas --count 10
    python -m reelstudio.autopilot write "The birthday paradox"
    python -m reelstudio.autopilot make projects/data_stories/storyboards/overfitting.yml --draft
    python -m reelstudio.autopilot run --publish youtube,instagram

Settings live under ``autopilot:`` in projects/<name>/project.yml. The topic
queue is topics.yml and the publication log is published.yml in the same
directory; a topic leaves the queue once it is logged, so scheduled runs never
post the same story twice.
"""

import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from reelstudio import storyboard as boards
from reelstudio.media import find_ffmpeg, media_duration, mix_audio
from reelstudio.publishers import PublishError, make_publishers
from reelstudio.render import ROOT, load_config, load_project, render_scenes
from reelstudio.voices import make_voice, narrate
from reelstudio.writers import LibraryWriter, brainstorm, make_writer, write_storyboard


REMOTE_PLATFORMS = {"youtube", "instagram"}


class Studio:
    def __init__(self, project_name, config_path=None):
        self.name = project_name
        self.project, self.scene_file = load_project(project_name)
        self.directory = ROOT / "projects" / project_name
        self.settings = self.project.get("autopilot") or {}
        self.render_config = load_config(config_path or ROOT / "configs" / "portrait.yml")
        self.output = ROOT / "videos" / project_name

    # Queue and log -------------------------------------------------------

    def read_yaml(self, name, default):
        path = self.directory / name
        if not path.is_file():
            return default
        return yaml.safe_load(path.read_text(encoding="utf-8")) or default

    def write_yaml(self, name, data):
        (self.directory / name).write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")

    def topics(self):
        topics = self.read_yaml("topics.yml", [])
        return [item if isinstance(item, dict) else {"topic": str(item)} for item in topics]

    def log(self):
        return self.read_yaml("published.yml", [])

    def published_platforms(self, slug):
        return {entry["platform"] for entry in self.log() if entry.get("slug") == slug}

    def next_topic(self, platforms):
        for item in self.topics():
            done = self.published_platforms(boards.slugify(item["topic"]))
            if not set(platforms) <= done:
                return item
        return None

    # Stages --------------------------------------------------------------

    def storyboard_path(self, topic):
        return self.directory / "storyboards" / f"{boards.slugify(topic)}.yml"

    def write(self, topic, angle=""):
        path = self.storyboard_path(topic)
        if path.is_file():
            print(f"Using existing storyboard: {relative(path)}")
            return boards.load(path)
        writer = make_writer(self.settings.get("writer"), self.directory)
        if isinstance(writer, LibraryWriter):
            return writer.find(topic)
        storyboard = write_storyboard(writer, topic, angle, channel=self.settings.get("channel"))
        storyboard["slug"] = boards.slugify(topic)
        boards.save(storyboard, path)
        print(f"Wrote storyboard: {relative(path)}")
        return storyboard

    def make(self, storyboard, draft=False):
        """Voice, render, and mix one storyboard; returns the run directory."""
        ffmpeg = find_ffmpeg()
        run = self.output / "runs" / storyboard["slug"] / ("draft" if draft else "final")
        if run.exists():
            shutil.rmtree(run)
        run.mkdir(parents=True)
        voice = make_voice(self.settings.get("voice"))
        timed, narration = narrate(storyboard, voice, run / "audio", ffmpeg)
        length = boards.total_duration(timed)
        limit = self.settings.get("max_seconds", 75)
        if length > limit:
            raise ValueError(f"Narration runs {length:.1f}s, over the {limit}s limit; shorten the storyboard")
        timed_path = boards.save(timed, run / "storyboard.json")
        brand = self.settings.get("brand", {})
        env = {"REELSTUDIO_STORYBOARD": str(timed_path), "REELSTUDIO_BRAND": json.dumps(brand)}
        scene = self.project["scenes"][0]
        silent, = render_scenes(self.scene_file, [scene], self.render_config, run / "render",
                                draft=draft, env=env, ffmpeg=ffmpeg)
        cover, = render_scenes(self.scene_file, [scene], self.render_config, run / "cover",
                               stills=True, draft=draft, env={**env, "REELSTUDIO_COVER": "1"})
        shutil.move(cover, run / "cover.png")
        music = self.music()
        final = run / "final.mp4"
        if narration or music:
            mix_audio(silent, final, ffmpeg, voiceover=narration, music=music,
                      music_volume=self.settings.get("music_volume", 0.08))
        else:
            shutil.copy2(silent, final)
        (run / "captions.srt").write_text(boards.srt_text(timed, lead=0.15), encoding="utf-8")
        metadata = {key: timed[key] for key in ("slug", "topic", "title", "post_caption", "hashtags", "sources")}
        metadata["duration"] = round(media_duration(final, ffmpeg), 2)
        metadata["draft"] = draft
        (run / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Reel ready: {relative(final)} ({metadata['duration']}s)")
        return run

    def music(self):
        configured = self.settings.get("music")
        if not configured:
            return None
        path = (ROOT / configured).resolve()
        if not path.is_file():
            print(f"Music not found, continuing without it: {configured}", file=sys.stderr)
            return None
        return path

    def publish(self, run, platforms):
        metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
        if metadata["draft"] and REMOTE_PLATFORMS & set(platforms):
            raise PublishError("Draft renders are low resolution; render without --draft before publishing")
        done = self.published_platforms(metadata["slug"])
        pending = [name for name in platforms if name not in done]
        for name in sorted(set(platforms) & done):
            print(f"Already published to {name}: {metadata['slug']}")
        publishers = make_publishers(pending, self.settings, self.output / "outbox")
        log = self.log()
        try:
            for publisher in publishers:
                result = publisher.publish(run / "final.mp4", metadata, cover=run / "cover.png",
                                           captions=run / "captions.srt")
                if "location" in result:
                    result["location"] = relative(result["location"])
                print(f"Published to {publisher.name}: {result.get('url') or result.get('location') or result.get('id')}")
                if metadata["draft"]:
                    continue  # Drafts are previews; logging them would retire the topic.
                # Log after every success so a later failure never causes a repost.
                log.append({"slug": metadata["slug"], "topic": metadata["topic"],
                            "date": datetime.date.today().isoformat(), **result})
                self.write_yaml("published.yml", log)
        finally:
            if not metadata["draft"]:
                self.write_yaml("published.yml", log)


def relative(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def platforms_from(args, studio):
    if args.publish:
        return [name.strip() for name in args.publish.split(",") if name.strip()]
    return list(studio.settings.get("publish", ["local"]))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m reelstudio.autopilot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="data_stories", help="Directory name under projects/")
    parser.add_argument("--config", type=Path, help="Render configuration; default: configs/portrait.yml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Show the topic queue and publication log")
    ideas = commands.add_parser("ideas", help="Brainstorm topics with the configured LLM and queue them")
    ideas.add_argument("--count", type=int, default=10)
    write = commands.add_parser("write", help="Write a storyboard for review")
    write.add_argument("topic")
    write.add_argument("--angle", default="")
    make = commands.add_parser("make", help="Voice, render, and mix a storyboard")
    make.add_argument("storyboard", type=Path)
    run = commands.add_parser("run", help="Produce and publish the next queued topic")
    for command in (make, run):
        command.add_argument("--draft", action="store_true", help="Fast 360x640 preview; never published remotely")
        command.add_argument("--publish", help="Comma-separated platforms: local, youtube, instagram")
    make.add_argument("--no-publish", action="store_true", help="Only produce the video")
    run.add_argument("--topic", help="Produce this topic instead of the next queued one")
    args = parser.parse_args(argv)
    try:
        studio = Studio(args.project, args.config)
        if args.command == "status":
            log = studio.log()
            print(f"{studio.project.get('title', args.project)}: {len(log)} publications")
            for item in studio.topics():
                done = studio.published_platforms(boards.slugify(item["topic"]))
                print(f"  [{', '.join(sorted(done)) or 'queued'}] {item['topic']}")
        elif args.command == "ideas":
            writer = make_writer(studio.settings.get("writer"), studio.directory)
            topics = studio.topics()
            new = brainstorm(writer, studio.settings.get("channel"), args.count, [t["topic"] for t in topics])
            studio.write_yaml("topics.yml", topics + new)
            print("\n".join(f"Queued: {idea['topic']} - {idea['angle']}" for idea in new))
        elif args.command == "write":
            studio.write(args.topic, args.angle)
        elif args.command == "make":
            run_dir = studio.make(boards.load(args.storyboard), draft=args.draft)
            if not args.no_publish:
                studio.publish(run_dir, ["local"] if args.draft and not args.publish else platforms_from(args, studio))
        elif args.command == "run":
            platforms = ["local"] if args.draft and not args.publish else platforms_from(args, studio)
            item = {"topic": args.topic} if args.topic else studio.next_topic(platforms)
            if item is None:
                print("The topic queue is empty; run: python -m reelstudio.autopilot ideas")
                return
            storyboard = studio.write(item["topic"], item.get("angle", ""))
            studio.publish(studio.make(storyboard, draft=args.draft), platforms)
    except (ValueError, OSError, subprocess.CalledProcessError, PublishError) as error:
        parser.exit(1, f"autopilot: {error}\n")


if __name__ == "__main__":
    main()
