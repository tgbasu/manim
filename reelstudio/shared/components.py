from manimlib import Rectangle, Text, VGroup

from reelstudio.shared.theme import CYAN, FONT, PANEL


def concept_card(title, color=CYAN, width=3.3, height=1.3):
    """An animated diagram node; move or animate the returned group."""
    box = Rectangle(width=width, height=height, stroke_color=color, stroke_width=3)
    box.set_fill(PANEL, opacity=1)
    label = Text(title, font=FONT, font_size=32).set_color(color)
    if label.get_width() > width - 0.3:
        label.set_width(width - 0.3)
    return VGroup(box, label)
