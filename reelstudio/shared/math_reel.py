"""Reusable graph lesson template for portrait educational videos."""

import math

from manimlib import (
    Axes, Dot, FadeIn, Line, Rectangle,
    ShowCreation, Text, Transform, ValueTracker, VGroup, Write,
    DOWN, LEFT, RIGHT, UP, linear,
)


from reelstudio.shared.base import PortraitScene
from reelstudio.shared.theme import CYAN, GOLD, MUTED, PINK


class MathReel(PortraitScene):
    """Shared 9:16 layout; all text stays inside the central safe area."""

    episode = 0
    series_title = "MATH TO ML"
    episode_count = 6
    footer_text = "SAVE THIS  /  BUILD YOUR ML FOUNDATION"
    heading = ""
    hook = ""
    formula = ""
    x_range = (-3, 3, 1)
    y_range = (-1, 7, 2)
    input_steps = (0, 1, 2)
    insights = ()
    bridge = ""
    takeaway = ""

    def function(self, x):
        raise NotImplementedError

    def caption(self, words, duration=3):
        replacement = self.label(words, -3.25, size=32)
        if hasattr(self, "subtitle"):
            self.play(Transform(self.subtitle, replacement), run_time=0.4)
        else:
            self.subtitle = replacement
            self.play(FadeIn(self.subtitle), run_time=0.4)
        self.wait(duration)

    def construct(self):
        if len(self.input_steps) != len(self.insights):
            raise ValueError("Each input step must have one explanation")
        badge = self.label(f"{self.series_title}   /   {self.episode:02d} OF {self.episode_count:02d}", 6.4, 25, CYAN)
        title = self.label(self.heading, 5.45, 55)
        hook = self.label(self.hook, 4.45, 32, GOLD)
        formula = self.label(self.formula, 3.25, 45, CYAN)
        footer = self.label(self.footer_text, -6.1, 22, MUTED)
        self.play(FadeIn(badge), Write(title), run_time=1)
        self.play(FadeIn(hook), run_time=0.5)
        self.wait(2)
        self.play(Write(formula), FadeIn(footer), run_time=1)

        axes = Axes(
            x_range=self.x_range, y_range=self.y_range, width=6.5, height=4.25,
            axis_config=dict(stroke_color=MUTED, stroke_width=2),
        ).move_to(0.15 * DOWN)
        # Explicit Text labels avoid the LaTeX-backed coordinate-label helpers.
        labels = VGroup()
        for x in range(math.ceil(self.x_range[0]), math.floor(self.x_range[1]) + 1):
            if x and x % self.x_range[2] == 0:
                labels.add(Text(str(x), font="Arial", font_size=21, color=MUTED)
                           .next_to(axes.c2p(x, 0), DOWN, buff=0.12))
        for y in range(math.ceil(self.y_range[0]), math.floor(self.y_range[1]) + 1):
            if y and y % self.y_range[2] == 0:
                labels.add(Text(str(y), font="Arial", font_size=21, color=MUTED)
                           .next_to(axes.c2p(0, y), LEFT, buff=0.12))
        labels.add(Text("x", font="Arial", font_size=24, color=MUTED)
                   .next_to(axes.x_axis.get_end(), RIGHT, buff=0.1))
        labels.add(Text("y", font="Arial", font_size=24, color=MUTED)
                   .next_to(axes.y_axis.get_end(), UP, buff=0.1))
        graph = axes.get_graph(self.function, x_range=self.x_range[:2], color=CYAN)
        graph.set_stroke(width=5)
        self.play(ShowCreation(axes), FadeIn(labels), run_time=1)
        self.play(ShowCreation(graph), run_time=2)

        tracker = ValueTracker(self.input_steps[0])
        dot = Dot(axes.c2p(tracker.get_value(), self.function(tracker.get_value())), fill_color=GOLD)
        dot.add_updater(lambda m: m.move_to(axes.c2p(tracker.get_value(), self.function(tracker.get_value()))))
        # A fixed-structure line avoids changing dash families as ReLU crosses zero.
        guide = Line(axes.c2p(0, 0), axes.c2p(0, 0) + 0.001 * UP, stroke_color=GOLD)

        def update_guide(mobject):
            x = tracker.get_value()
            start = axes.c2p(x, 0)
            end = axes.c2p(x, self.function(x))
            is_zero = abs(self.function(x)) < 1e-6
            if is_zero:
                end = start + 0.001 * UP
            mobject.put_start_and_end_on(start, end)
            mobject.set_stroke(opacity=0 if is_zero else 0.7)

        guide.add_updater(update_guide)
        readout = self.label("Input -> output", -2.65)
        # Text-based readouts keep the series independent of a TeX installation.
        readout.add_updater(lambda m: m.become(self.label(
            f"x = {tracker.get_value():.2f}   ->   y = {self.function(tracker.get_value()):.2f}",
            -2.65, 29, GOLD,
        )))
        self.play(FadeIn(dot), FadeIn(guide), FadeIn(readout), run_time=0.5)
        for value, explanation in zip(self.input_steps, self.insights):
            self.play(tracker.animate.set_value(value), run_time=2, rate_func=linear)
            self.caption(explanation, duration=2.5)
        self.demo(axes)
        self.caption(self.bridge, duration=4)
        card = Rectangle(width=7.2, height=1.45, stroke_color=CYAN, stroke_width=2)
        card.set_fill("#14243C", opacity=1).move_to(4.8 * DOWN)
        conclusion = self.label(self.takeaway, -4.8, 30, GOLD, max_width=6.7)
        self.play(FadeIn(card), Write(conclusion), run_time=1)
        self.wait(4)
        dot.clear_updaters()
        guide.clear_updaters()
        readout.clear_updaters()

    def demo(self, axes):
        """Override for an extra visual connecting the graph to ML."""


