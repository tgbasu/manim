from manimlib import Scene, Text, UP, WHITE

from reelstudio.shared.theme import FONT


class PortraitScene(Scene):
    """A 9:16 canvas with width-limited text for mobile explainers."""

    def setup(self):
        super().setup()
        self.camera.frame.set_width(9, stretch=True)
        self.camera.frame.set_height(16, stretch=True)

    def label(self, words, y, size=36, color=WHITE, max_width=7.1):
        result = Text(words, font=FONT, font_size=size).set_color(color)
        if result.get_width() > max_width:
            result.set_width(max_width)
        return result.move_to(y * UP)
