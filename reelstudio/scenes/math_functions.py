import math

from manimlib import DashedLine, Dot, FadeIn, FadeOut, Line, ShowCreation, Text, VGroup, DOWN
from reelstudio.shared.math_reel import MathReel
from reelstudio.shared.theme import MUTED, PINK


class LinearReel(MathReel):
    episode = 1
    heading = "LINEAR FUNCTION"
    hook = "How does a model make its first guess?"
    formula = "f(x) = 2x + 1"
    x_range = (-2, 3, 1)
    y_range = (-4, 8, 2)
    input_steps = (0, 1, 2)
    insights = ("At x = 0, the output starts at 1.", "Add 1 to x. The output rises by 2.", "Same input step. Same output step.")
    bridge = "ML: learn the slope and intercept from data."
    takeaway = "LINEAR REGRESSION\nPrediction = weight x input + bias"

    def function(self, x):
        return 2 * x + 1

    def demo(self, axes):
        points = VGroup(*(Dot(axes.c2p(x, self.function(x) + error), fill_color=PINK)
                          for x, error in [(-1, 0.5), (0, -0.6), (1, 0.8), (2, -0.5)]))
        self.play(FadeIn(points), run_time=0.6)
        self.caption("Real data is noisy. A line models the trend.")


class QuadraticReel(MathReel):
    episode = 2
    heading = "QUADRATIC FUNCTION"
    hook = "Why do big prediction mistakes hurt more?"
    formula = "L(e) = e^2"
    x_range = (-2.5, 2.5, 1)
    y_range = (-0.5, 7, 2)
    input_steps = (-2, -1, 0)
    insights = ("Error -2 gives loss 4.", "Error -1 gives loss 1.", "Zero error. Zero squared loss.")
    bridge = "ML: average squared errors to get MSE."
    takeaway = "SQUARED ERROR\nDouble the error -> 4x the penalty"

    def function(self, x):
        return x * x

    def demo(self, axes):
        tangent = Line(axes.c2p(-1.7, 2.4), axes.c2p(-0.5, 0), color=PINK)
        self.play(ShowCreation(tangent), run_time=0.6)
        self.caption("Slope = 2e. Follow downhill toward zero.")
        self.play(FadeOut(tangent), run_time=0.4)


class ExponentialReel(MathReel):
    episode = 3
    heading = "EXPONENTIAL FUNCTION"
    hook = "One extra step. A much bigger output."
    formula = "f(x) = exp(x)"
    x_range = (-2, 2, 1)
    y_range = (-0.5, 8, 2)
    input_steps = (0, 1, 2)
    insights = ("exp(0) = 1. This is the baseline.", "exp(1) is about 2.72.", "exp(2) is about 7.39. Growth accelerates.")
    bridge = "ML: softmax normalizes exponentiated scores."
    takeaway = "SOFTMAX\nexp(score) / sum of exp(scores)"

    def function(self, x):
        return math.exp(x)

    def demo(self, axes):
        self.caption("Scores [0, 1, 2] -> probabilities [9%, 24%, 67%].", 4)


class LogarithmReel(MathReel):
    episode = 4
    heading = "LOGARITHMIC FUNCTION"
    hook = "Confident and wrong? That gets expensive."
    formula = "L(p) = -ln(p),  0 < p <= 1"
    x_range = (0.05, 1, 0.25)
    y_range = (-0.3, 3.2, 1)
    input_steps = (0.9, 0.5, 0.1)
    insights = ("True-class probability 0.9: loss about 0.11.", "At 0.5: loss rises to about 0.69.", "At 0.1: loss jumps to about 2.30.")
    bridge = "ML: cross-entropy penalizes unlikely true labels."
    takeaway = "NEGATIVE LOG LIKELIHOOD\nMore probability on truth -> less loss"

    def function(self, x):
        return -math.log(x)

    def demo(self, axes):
        markers = VGroup(*(Text(str(x), font="Arial", font_size=22, color=MUTED)
                           .next_to(axes.c2p(x, 0), DOWN, buff=0.13)
                           for x in (0.1, 0.5, 0.9)))
        self.play(FadeIn(markers), run_time=0.5)
        self.caption("ln reverses exp. Negative ln turns it into a loss.")


class SigmoidReel(MathReel):
    episode = 5
    heading = "SIGMOID FUNCTION"
    hook = "Turn any score into a number from 0 to 1."
    formula = "s(x) = 1 / (1 + exp(-x))"
    x_range = (-6, 6, 2)
    y_range = (-0.1, 1.1, 1)
    input_steps = (-4, 0, 4)
    insights = ("A negative score maps close to 0.", "Score 0 maps exactly to 0.5.", "A positive score maps close to 1.")
    bridge = "ML: logistic regression maps a score to probability."
    takeaway = "BINARY CLASSIFICATION\nA threshold turns probability into a label"

    def function(self, x):
        return 1 / (1 + math.exp(-x))

    def demo(self, axes):
        threshold = DashedLine(axes.c2p(-6, 0.5), axes.c2p(6, 0.5), color=PINK)
        self.play(ShowCreation(threshold), run_time=0.6)
        self.caption("0.5 is a common threshold, not a universal rule.")


class ReLUReel(MathReel):
    episode = 6
    heading = "ReLU FUNCTION"
    hook = "The simple bend that powers neural nets."
    formula = "ReLU(x) = max(0, x)"
    x_range = (-3, 3, 1)
    y_range = (-0.5, 3.5, 1)
    input_steps = (-2, 0, 2)
    insights = ("Negative input? The output is zero.", "At zero, the function changes direction.", "Positive input? Pass it straight through.")
    bridge = "ML: nonlinear activations enable richer patterns."
    takeaway = "NEURAL NETWORKS\nLinear layer -> ReLU -> linear layer"

    def function(self, x):
        return max(0, x)

    def demo(self, axes):
        self.caption("Stacking only linear layers still gives a linear map.")
        self.caption("ReLU adds a bend. Networks can build complex shapes.")

