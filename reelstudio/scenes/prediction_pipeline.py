"""A simple 2D explainer that can be adapted to non-math subjects."""

from manimlib import Arrow, Dot, FadeIn, FadeOut, LaggedStart, ShowCreation, VGroup, Write, DOWN, UP

from reelstudio.shared.base import PortraitScene
from reelstudio.shared.components import concept_card
from reelstudio.shared.theme import CYAN, GOLD, MUTED, PINK


class PredictionPipeline(PortraitScene):
    def construct(self):
        title = self.label("HOW A MODEL PREDICTS", 5.7, 48)
        hook = self.label("Data in. A prediction out. What happens inside?", 4.7, 30, GOLD)
        self.play(Write(title), run_time=1)
        self.play(FadeIn(hook), run_time=0.5)
        self.wait(2)

        inputs = concept_card("INPUT: 2", GOLD).move_to(2.6 * UP)
        model = concept_card("MODEL: 2x + 1", CYAN).move_to(0.2 * UP)
        output = concept_card("PREDICTION: 5", PINK).move_to(2.2 * DOWN)
        arrows = VGroup(
            Arrow(inputs.get_bottom(), model.get_top(), buff=0.2, stroke_color=MUTED),
            Arrow(model.get_bottom(), output.get_top(), buff=0.2, stroke_color=MUTED),
        )
        self.play(FadeIn(inputs), run_time=0.8)
        self.wait(1.5)
        self.play(ShowCreation(arrows[0]), FadeIn(model), run_time=1)
        packet = Dot(inputs.get_bottom(), fill_color=GOLD)
        self.add(packet)
        self.play(packet.animate.move_to(model.get_center()), run_time=1.2)
        explanation = self.label("Multiply by 2. Then add 1.", -4, 34, CYAN)
        self.play(Write(explanation), run_time=0.8)
        self.wait(2)
        self.play(ShowCreation(arrows[1]), FadeIn(output), run_time=1)
        self.play(packet.animate.move_to(output.get_center()), run_time=1.2)
        self.play(FadeOut(packet), run_time=0.3)
        self.wait(2)
        self.play(FadeOut(explanation), run_time=0.4)
        takeaway = self.label("Training learns the model's parameters.\nInference uses them to make predictions.", -4.1, 30)
        self.play(Write(takeaway), run_time=1)
        dots = VGroup(*(Dot(point=(x * 0.35, -5.7, 0), fill_color=CYAN) for x in range(-3, 4)))
        self.play(LaggedStart(*(FadeIn(dot) for dot in dots), lag_ratio=0.15), run_time=1)
        self.wait(4)
