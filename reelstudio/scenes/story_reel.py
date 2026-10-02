"""Render any storyboard as a captioned 9:16 data story.

The renderer passes the storyboard path in REELSTUDIO_STORYBOARD. Beat
durations come from measured narration, so each beat's visuals, captions, and
voice start together. REELSTUDIO_COVER=1 renders a thumbnail layout instead.
"""

import json
import os

from manimlib import FadeIn, FadeOut, Rectangle, RoundedRectangle, VGroup, Write, DOWN, LEFT, UP

from reelstudio import storyboard as boards
from reelstudio.shared.base import PortraitScene
from reelstudio.shared.theme import CYAN, GOLD, MUTED, PANEL
from reelstudio.shared.visuals import build, text


# Narration starts this long after each beat begins; voices.py uses the same value.
VOICE_LEAD = 0.15
TRANSITION = 0.3
TITLE_TIME = 0.4
OUTRO_SECONDS = 1.6
CAPTION_Y = -2.45


def load_environment():
    path = os.environ.get("REELSTUDIO_STORYBOARD")
    if not path:
        raise ValueError("Set REELSTUDIO_STORYBOARD or render through: python -m reelstudio.autopilot make <storyboard>")
    storyboard = boards.with_estimated_durations(boards.load(path))
    brand = json.loads(os.environ.get("REELSTUDIO_BRAND", "{}"))
    return storyboard, brand


def scale_steps(steps, budget):
    nominal = sum(seconds for _, seconds in steps) or 1
    factor = min(1.0, budget / nominal)
    return [(animations, seconds * factor) for animations, seconds in steps]


class StoryReel(PortraitScene):
    def construct(self):
        storyboard, brand = load_environment()
        if os.environ.get("REELSTUDIO_COVER") == "1":
            self.cover(storyboard, brand)
            return
        total = boards.total_duration(storyboard) + OUTRO_SECONDS
        self.add_chrome(brand.get("series", "DATA STORIES"), total)
        self.add_captions()
        offset = 0.0
        for index, beat in enumerate(storyboard["beats"]):
            self.play_beat(beat, offset, is_last=index == len(storyboard["beats"]) - 1)
            offset += beat["duration"]
        self.outro(brand)

    def add_chrome(self, series, total):
        track = Rectangle(width=8.4, height=0.09, stroke_width=0).set_fill(MUTED, opacity=0.25).move_to(7.55 * UP)
        bar = Rectangle(width=8.4, height=0.09, stroke_width=0).set_fill(GOLD, opacity=1).move_to(track)
        left = track.get_left()
        # Rebuilding the bar from the clock keeps it exact through every play and wait.
        bar.add_updater(lambda m: m.set_width(max(8.4 * min(self.time / total, 1), 0.001), stretch=True)
                        .move_to(left, aligned_edge=LEFT))
        badge = self.label(series.upper(), 6.85, 32, CYAN)
        self.add(track, bar, badge)

    def add_captions(self):
        self.caption_schedule = []
        self.caption_text = None
        panel = RoundedRectangle(width=8.0, height=1.35, corner_radius=0.25, stroke_width=0)
        panel.set_fill(PANEL, opacity=0.0).move_to(CAPTION_Y * UP)
        holder = VGroup(panel)

        def update(group):
            now = self.time
            active = next((words for start, end, words in self.caption_schedule if start <= now < end), None)
            if active == self.caption_text:
                return
            self.caption_text = active
            if active is None:
                group.set_submobjects([panel])
                panel.set_fill(opacity=0)
                return
            # Captions are the retention engine on muted autoplay: big, bold, centered.
            words = text(active, 60, "#FFFFFF", max_width=7.4).move_to(CAPTION_Y * UP)
            panel.set_fill(opacity=0.85)
            panel.set_width(words.get_width() + 0.6, stretch=True).move_to(words)
            group.set_submobjects([panel, words])

        holder.add_updater(update)
        self.add(holder)

    def play_beat(self, beat, offset, is_last):
        duration = beat["duration"]
        speech = max(0.1, duration - VOICE_LEAD - boards.BEAT_TAIL)
        self.caption_schedule = [
            (offset + VOICE_LEAD + start, offset + VOICE_LEAD + end, words)
            for start, end, words in boards.caption_chunks(beat["narration"], speech)
        ]
        kind = beat["visual"]["kind"]
        on_screen = VGroup()
        intro = []
        if kind != "statement":
            title = text(beat["title"].upper(), 62, max_width=8.0, max_chars=20).move_to(5.6 * UP)
            on_screen.add(title)
            intro.append(FadeIn(title, shift=0.2 * DOWN))
        group, steps, finish = build(self, beat["visual"], beat["title"])
        on_screen.add(group)
        reserved = TITLE_TIME + (0 if is_last else TRANSITION)
        budget = max(0.3, duration - reserved - 0.2)
        if intro:
            self.play(*intro, run_time=TITLE_TIME)
        for animations, seconds in scale_steps(steps, budget):
            if seconds <= 0.02:
                continue
            if animations is None:
                self.wait(seconds)
            else:
                self.play(*animations, run_time=seconds)
        if finish:
            finish(group)
        end = offset + duration - (0 if is_last else TRANSITION)
        if end - self.time > 0.01:
            self.wait(end - self.time)
        if not is_last:
            self.play(FadeOut(on_screen), run_time=TRANSITION)
        else:
            self.final_group = on_screen

    def outro(self, brand):
        self.caption_schedule = []
        cta = brand.get("cta", "Follow for a new data story every day")
        handle = brand.get("handle", "")
        card = RoundedRectangle(width=7.6, height=2.4 if handle else 1.8, corner_radius=0.25,
                                stroke_color=GOLD, stroke_width=3).set_fill(PANEL, opacity=0.95)
        words = VGroup(text(cta, 44, GOLD, 6.8, max_chars=26))
        if handle:
            words.add(text(handle, 40, "#FFFFFF", 6.8))
        words.arrange(DOWN, buff=0.25)
        card.move_to(4.2 * DOWN)
        words.move_to(card)
        self.play(FadeIn(card, shift=0.3 * UP), Write(words), run_time=0.6)
        self.wait(OUTRO_SECONDS - 0.6)

    def cover(self, storyboard, brand):
        badge = self.label(brand.get("series", "DATA STORIES").upper(), 5.6, 34, CYAN)
        words = storyboard["cover_title"].upper().split()
        # Two balanced lines read better in a grid thumbnail than one long one.
        middle = (len(words) + 1) // 2
        lines = [" ".join(words[:middle]), " ".join(words[middle:])] if len(words) > 2 else [" ".join(words)]
        title = VGroup(*(text(line, 96, "#FFFFFF" if i == 0 else GOLD, 8.0) for i, line in enumerate(lines)))
        title.arrange(DOWN, buff=0.35).move_to(1.6 * UP)
        group, _, finish = build(self, storyboard["beats"][1]["visual"], storyboard["beats"][1]["title"])
        if finish:
            finish(group)
        group.scale(0.62).next_to(title, DOWN, buff=0.6)
        # fade() keeps unfilled curves unfilled, unlike set_opacity.
        group.fade(0.45)
        self.add(badge, group, title)
