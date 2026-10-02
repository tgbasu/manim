"""Storyboard visual builders for the 9:16 StoryReel layout.

Each builder takes a validated visual spec and returns ``(group, steps)``. The
group holds everything the beat leaves on screen; steps are ``(animations,
nominal_seconds)`` pairs, or ``(None, seconds)`` for a pause. StoryReel scales
the steps to fit the beat's narration so visuals never drift from the voice.
"""

import math

from manimlib import (
    Arrow, Axes, DashedLine, Dot, FadeIn, GrowFromEdge, LaggedStart, Line,
    Polygon, Rectangle, RoundedRectangle, ShowCreation, Text, ValueTracker, VGroup,
    VMobject, Write, DOWN, LEFT, ORIGIN, RIGHT, UP, linear, smooth,
)

from reelstudio.shared.components import concept_card
from reelstudio.shared.theme import (
    CYAN, FONT, GOLD, GROUP_COLORS, MONO, MUTED, PANEL, PINK, SERIES_COLORS,
)


# The visual area sits between the beat title and the captions.
CENTER = 1.45 * UP
WIDTH = 7.2
HEIGHT = 5.2


def wrap(words, max_chars):
    """Greedy word wrap; phones read short stacked lines faster than shrunken ones."""
    lines, current = [], ""
    for word in str(words).split():
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return "\n".join(lines + [current])


def text(words, size=30, color="#FFFFFF", max_width=WIDTH, font=FONT, max_chars=None, align="CENTER"):
    words = wrap(words, max_chars) if max_chars else str(words)
    result = Text(words, font=font, font_size=size, alignment=align).set_color(color)
    if result.get_width() > max_width:
        result.set_width(max_width)
    return result


def number(value, decimals=0):
    if decimals == 0 and abs(value - round(value)) < 1e-9:
        value = round(value)
        return f"{value:,}"
    return f"{value:,.{decimals or 1}f}"


class Plot:
    """Axes drawn on a unit square, so they sit at the chart edges for any data range.

    ManimGL places each axis at the other's zero, which pushes the chart off
    center whenever the data excludes zero; plotting in normalized coordinates
    keeps every chart aligned with the visual area.
    """

    def __init__(self, x_range, y_range, width=6.6, height=4.1):
        self.x_range, self.y_range = x_range, y_range
        self.axes = Axes(
            x_range=(0, 1, 0.25), y_range=(0, 1, 0.25), width=width, height=height,
            axis_config=dict(stroke_color=MUTED, stroke_width=2, include_tip=False),
        ).move_to(CENTER + 0.1 * DOWN)

    def point(self, x, y):
        (x0, x1), (y0, y1) = self.x_range, self.y_range
        return self.axes.c2p((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))

    def curve(self, xs, ys):
        return VMobject().set_points_smoothly([self.point(x, y) for x, y in zip(xs, ys)])


def padded_range(values, pad=0.12, include_zero=False):
    low, high = min(values), max(values)
    if include_zero:
        low, high = min(low, 0), max(high, 0)
    span = (high - low) or abs(high) or 1
    return low - span * pad, high + span * pad


def statement(scene, spec, title):
    words = text(title.upper(), 96, max_width=WIDTH, max_chars=14).move_to(CENTER)
    underline = Line(LEFT, RIGHT, stroke_color=GOLD, stroke_width=6)
    underline.set_width(min(words.get_width(), 5)).next_to(words, DOWN, buff=0.35)
    group = VGroup(words, underline)
    return group, [([Write(words)], 0.8), ([ShowCreation(underline)], 0.4)]


def stat(scene, spec, title):
    tracker = ValueTracker(0)
    decimals = spec.get("decimals", 0)
    prefix, suffix = spec.get("prefix", ""), spec.get("suffix", "")

    def render(value):
        return text(f"{prefix}{number(value, decimals)}{suffix}", 190, GOLD, max_width=WIDTH).move_to(CENTER + 0.5 * UP)

    value = render(0)
    value.add_updater(lambda m: m.become(render(tracker.get_value())))
    label = text(spec["label"], 50, max_width=6.8, max_chars=22).move_to(CENTER + 1.6 * DOWN)
    group = VGroup(value, label)

    def finish(_):
        value.clear_updaters()
        value.become(render(spec["value"]))

    count = tracker.animate.set_value(spec["value"]).set_anim_args(rate_func=smooth)
    return group, [([FadeIn(value), count], 1.6), ([FadeIn(label, shift=0.2 * UP)], 0.5)], finish


def bars(scene, spec, title):
    labels, values = spec["labels"], spec["values"]
    highlight = spec.get("highlight")
    unit = spec.get("unit", "")
    count = len(values)
    slot = WIDTH / count
    baseline = CENTER[1] - 2.0
    peak = max(values)
    group, grow, annotate = VGroup(), [], []
    base_line = Line(LEFT * WIDTH / 2, RIGHT * WIDTH / 2, stroke_color=MUTED, stroke_width=2).shift(baseline * UP)
    group.add(base_line)
    for index, (label, value) in enumerate(zip(labels, values)):
        x = -WIDTH / 2 + slot * (index + 0.5)
        color = GOLD if index == highlight else (CYAN if highlight is None else MUTED)
        height = max(3.6 * value / peak, 0.02)
        bar = Rectangle(width=slot * 0.62, height=height, stroke_width=0)
        bar.set_fill(color, opacity=1).move_to([x, baseline + height / 2, 0])
        value_label = text(number(value, 1 if value != round(value) else 0) + unit, 38, color, slot * 0.95)
        value_label.next_to(bar, UP, buff=0.12)
        name = text(label, 34, MUTED if index != highlight else GOLD, slot * 0.95)
        name.next_to([x, baseline, 0], DOWN, buff=0.18)
        group.add(bar, value_label, name)
        grow.append(GrowFromEdge(bar, DOWN))
        annotate.append(FadeIn(value_label, shift=0.15 * UP))
    names = [m for m in group[3::3]]
    return group, [
        ([ShowCreation(base_line), *(FadeIn(n) for n in names)], 0.5),
        ([LaggedStart(*grow, lag_ratio=0.2)], 1.4),
        ([LaggedStart(*annotate, lag_ratio=0.15)], 0.6),
    ]


def line(scene, spec, title):
    series = spec["series"]
    count = len(series[0]["values"])
    all_values = [v for s in series for v in s["values"]]
    y_low, y_high = padded_range(all_values)
    plot = Plot((0, count - 1), (y_low, y_high))
    axes = plot.axes
    group, draws, legend = VGroup(axes), [], VGroup()
    for index, item in enumerate(series):
        color = SERIES_COLORS[index]
        curve = VMobject().set_points_as_corners([plot.point(i, v) for i, v in enumerate(item["values"])])
        curve.set_stroke(color, width=6)
        group.add(curve)
        draws.append(ShowCreation(curve, rate_func=linear))
        legend.add(VGroup(Line(ORIGIN, 0.45 * RIGHT, stroke_color=color, stroke_width=6),
                          text(item["name"], 34, color, 2.8)).arrange(RIGHT, buff=0.15))
    legend.arrange(RIGHT, buff=0.5).next_to(axes, UP, buff=0.25)
    if legend.get_width() > WIDTH:
        legend.set_width(WIDTH)
    labels = VGroup()
    step = 1 if count <= 6 else 2
    for i, label in enumerate(spec.get("x_labels", [])):
        if i % step == 0:
            labels.add(text(label, 28, MUTED, 1.2).next_to(plot.point(i, y_low), DOWN, buff=0.15))
    group.add(legend, labels)
    steps = [([ShowCreation(axes), FadeIn(legend), FadeIn(labels)], 0.6), (draws, 1.8)]
    if "highlight_index" in spec:
        i = spec["highlight_index"]
        marker = DashedLine(plot.point(i, y_low), plot.point(i, y_high), stroke_color=GOLD, stroke_width=3)
        dot = Dot(plot.point(i, series[0]["values"][i]), fill_color=GOLD, radius=0.12)
        group.add(marker, dot)
        steps.append(([ShowCreation(marker), FadeIn(dot, scale=2)], 0.6))
    return group, steps



def scatter(scene, spec, title):
    points = spec["points"]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x_low, x_high = padded_range(xs)
    y_low, y_high = padded_range(ys)
    plot = Plot((x_low, x_high), (y_low, y_high))
    axes = plot.axes
    groups = spec.get("groups")
    dots = VGroup(*(
        Dot(plot.point(x, y), radius=0.11, fill_color=GROUP_COLORS[groups[i]] if groups else CYAN)
        for i, (x, y) in enumerate(points)
    ))
    group = VGroup(axes, dots)
    steps = [([ShowCreation(axes)], 0.5), ([LaggedStart(*(FadeIn(d, scale=0.5) for d in dots), lag_ratio=0.04)], 1.2)]
    if spec.get("fit"):
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mean_x) ** 2 for x in xs)
        slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / sxx
        intercept = mean_y - slope * mean_x
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in points)
        r2 = 1 - ss_res / ss_tot if ss_tot else 1
        # Clip the fitted line to the plotted y range so it never leaves the axes.
        ends = []
        for x in (x_low, x_high):
            y = min(max(slope * x + intercept, y_low), y_high)
            ends.append(plot.point((y - intercept) / slope if slope else x, y))
        fit_line = Line(*ends, stroke_color=GOLD, stroke_width=6)
        score = text(f"R² = {r2:.2f}", 40, GOLD).next_to(axes, UP, buff=0.2).align_to(axes, RIGHT)
        group.add(fit_line, score)
        steps.append(([ShowCreation(fit_line), FadeIn(score)], 0.9))
    return group, steps


def distribution(scene, spec, title):
    mean, std = spec["mean"], spec["std"]

    def pdf(x):
        return math.exp(-0.5 * ((x - mean) / std) ** 2) / (std * math.sqrt(2 * math.pi))

    peak = pdf(mean)
    plot = Plot((mean - 4 * std, mean + 4 * std), (0, peak * 1.25))
    axes = plot.axes
    xs = [mean + std * (i / 25 - 4) for i in range(201)]
    curve = plot.curve(xs, [pdf(x) for x in xs]).set_stroke(CYAN, width=6)
    ticks = VGroup(*(
        text(number(mean + k * std, 1 if std != round(std) else 0), 28, MUTED, 1.2)
        .next_to(plot.point(mean + k * std, 0), DOWN, buff=0.15)
        for k in (-2, -1, 0, 1, 2)
    ))
    group = VGroup(axes, curve, ticks)
    steps = [([ShowCreation(axes), FadeIn(ticks)], 0.5), ([ShowCreation(curve)], 1.2)]
    if "shade_from" in spec:
        low = max(spec["shade_from"], mean - 4 * std)
        high = min(spec["shade_to"], mean + 4 * std)
        samples = [low + (high - low) * i / 60 for i in range(61)]
        area = Polygon(plot.point(low, 0), *(plot.point(x, pdf(x)) for x in samples), plot.point(high, 0))
        area.set_stroke(width=0).set_fill(GOLD, opacity=0.45)
        cdf = lambda x: 0.5 * (1 + math.erf((x - mean) / (std * math.sqrt(2))))
        share = cdf(spec["shade_to"]) - cdf(spec["shade_from"])
        label = text(f"{share * 100:.1f}% of the data", 46, GOLD).next_to(axes, UP, buff=0.15)
        group.add(area, label)
        steps.append(([FadeIn(area), Write(label)], 0.9))
    return group, steps


def flow(scene, spec, title):
    steps_text = spec["steps"]
    count = len(steps_text)
    gap = HEIGHT / count
    cards = VGroup(*(
        concept_card(step, color=(CYAN, GOLD, PINK)[i % 3], width=6.4, height=min(1.05, gap * 0.62), size=42)
        .move_to(CENTER + (HEIGHT / 2 - gap * (i + 0.5)) * UP)
        for i, step in enumerate(steps_text)
    ))
    arrows = VGroup(*(
        Arrow(a.get_bottom(), b.get_top(), buff=0.08, stroke_color=MUTED, stroke_width=4)
        for a, b in zip(cards, cards[1:])
    ))
    packet = Dot(cards[0].get_left() + 0.35 * RIGHT, fill_color=GOLD, radius=0.13)
    group = VGroup(cards, arrows, packet)
    steps = [([FadeIn(cards[0], shift=0.2 * DOWN), FadeIn(packet)], 0.5)]
    for i in range(1, count):
        steps.append(([ShowCreation(arrows[i - 1]), FadeIn(cards[i], shift=0.2 * DOWN),
                       packet.animate.move_to(cards[i].get_left() + 0.35 * RIGHT)], 0.7))
    return group, steps


def matrix(scene, spec, title):
    rows, cols, values = spec["rows"], spec["cols"], spec["values"]
    size = min(1.9, 5.4 / max(len(rows), len(cols)))
    peak = max(abs(v) for row in values for v in row) or 1
    origin = CENTER + 0.6 * RIGHT + 0.3 * DOWN
    cells = VGroup()
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            center = origin + ((c - (len(cols) - 1) / 2) * size) * RIGHT + (((len(rows) - 1) / 2 - r) * size) * UP
            box = Rectangle(width=size * 0.94, height=size * 0.94, stroke_color=CYAN, stroke_width=2)
            box.set_fill(GOLD if r == c else PINK, opacity=0.15 + 0.6 * abs(value) / peak).move_to(center)
            cells.add(VGroup(box, text(number(value, 0 if value == round(value) else 2), 52, max_width=size * 0.8).move_to(center)))
    col_labels = VGroup(*(
        text(name, 30, MUTED, size * 0.95, max_chars=10).next_to(cells[c][0], UP, buff=0.15) for c, name in enumerate(cols)
    ))
    row_labels = VGroup(*(
        text(name, 30, MUTED, 1.9, max_chars=8).next_to(cells[r * len(cols)][0], LEFT, buff=0.15) for r, name in enumerate(rows)
    ))
    group = VGroup(cells, col_labels, row_labels)
    return group, [([FadeIn(col_labels), FadeIn(row_labels)], 0.4),
                   ([LaggedStart(*(FadeIn(cell, scale=0.8) for cell in cells), lag_ratio=0.12)], 1.4)]


def compare(scene, spec, title):
    columns = VGroup()
    reveals = []
    for side, color, x in (("left", PINK, -1.85), ("right", CYAN, 1.85)):
        panel = RoundedRectangle(width=3.45, height=HEIGHT, corner_radius=0.2, stroke_color=color, stroke_width=3)
        panel.set_fill(PANEL, opacity=1).move_to(CENTER + x * RIGHT)
        heading = text(spec[f"{side}_title"].upper(), 42, color, 3.1).move_to(panel.get_top() + 0.55 * DOWN)
        items = VGroup(*(text(item, 36, max_width=3.1, max_chars=12) for item in spec[side]))
        items.arrange(DOWN, buff=0.5).next_to(heading, DOWN, buff=0.55)
        columns.add(VGroup(panel, heading, items))
        reveals.append((panel, heading, items))
    steps = [([FadeIn(VGroup(p, h)) for p, h, _ in reveals], 0.6)]
    for left_item, right_item in zip(reveals[0][2], reveals[1][2]):
        steps.append(([FadeIn(left_item, shift=0.15 * RIGHT), FadeIn(right_item, shift=0.15 * LEFT)], 0.5))
    longer = max(reveals, key=lambda r: len(r[2]))[2]
    for item in longer[min(len(reveals[0][2]), len(reveals[1][2])):]:
        steps.append(([FadeIn(item)], 0.5))
    return columns, steps


def bullets(scene, spec, title):
    rows = VGroup()
    for item in spec["items"]:
        mark = Dot(radius=0.11, fill_color=GOLD)
        rows.add(VGroup(mark, text(item, 46, max_width=6.3, max_chars=20, align="LEFT")).arrange(RIGHT, buff=0.3))
    rows.arrange(DOWN, buff=0.6, aligned_edge=LEFT).move_to(CENTER)
    steps = []
    for row in rows:
        steps += [([FadeIn(row, shift=0.25 * RIGHT)], 0.5), (None, 1.2)]
    return rows, steps[:-1]


def code(scene, spec, title):
    lines = VGroup(*(text(line or " ", 34, "#E6EDF3", 6.6, font=MONO, align="LEFT") for line in spec["lines"]))
    lines.arrange(DOWN, buff=0.28, aligned_edge=LEFT)
    panel = RoundedRectangle(width=WIDTH, height=lines.get_height() + 1.3, corner_radius=0.2,
                             stroke_color=MUTED, stroke_width=2).set_fill("#0D1117", opacity=1)
    panel.move_to(CENTER)
    lights = VGroup(*(Dot(radius=0.08, fill_color=c) for c in (PINK, GOLD, "#06D6A0"))).arrange(RIGHT, buff=0.15)
    lights.move_to(panel.get_corner(UP + LEFT) + 0.45 * RIGHT + 0.3 * DOWN)
    lines.next_to(lights, DOWN, buff=0.35).align_to(lights, LEFT)
    group = VGroup(panel, lights, lines)
    return group, [([FadeIn(panel), FadeIn(lights)], 0.4),
                   ([LaggedStart(*(Write(line) for line in lines), lag_ratio=0.5)], 0.6 * len(lines))]


BUILDERS = {
    "statement": statement, "stat": stat, "bars": bars, "line": line, "scatter": scatter,
    "distribution": distribution, "flow": flow, "matrix": matrix, "compare": compare,
    "bullets": bullets, "code": code,
}


def build(scene, spec, title):
    """Return (group, steps, finish) for a visual spec; finish may be None."""
    result = BUILDERS[spec["kind"]](scene, spec, title)
    return result if len(result) == 3 else (*result, None)
