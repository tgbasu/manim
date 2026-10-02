from manimlib import *


class SineWave(Scene):
    def construct(self):
        axes = Axes(
            x_range=(-TAU, TAU, PI / 2),
            y_range=(-1.5, 1.5, 0.5),
            width=12,
            height=4,
        )
        axes.shift(0.5 * DOWN)

        # Multiples of pi along x, written with Text so no LaTeX install is needed. Each sits
        # on whichever side the curve leaves clear as it crosses the axis there
        x_labels = VGroup(*(
            Text(name, font_size=28).next_to(axes.c2p(k * PI, 0), direction, buff=0.1)
            for k, name, direction in [
                (-2, "-2π", DOWN), (-1, "-π", DL), (1, "π", DL), (2, "2π", DR),
            ]
        ))
        y_labels = VGroup(*(
            Text(name, font_size=28).next_to(axes.c2p(0, y), LEFT, buff=0.15)
            for y, name in [(1, "1"), (-1, "-1")]
        ))

        title = Text("y = sin(x)", font_size=56)
        title.to_edge(UP)

        graph = axes.get_graph(np.sin, color=BLUE)
        graph.set_stroke(width=4)

        self.play(Write(title))
        self.play(ShowCreation(axes, lag_ratio=0.01), FadeIn(x_labels), FadeIn(y_labels))
        self.play(ShowCreation(graph), run_time=3)
        self.wait()

        # A point riding along the curve, with a drop line and a live readout of sin(x)
        x_tracker = ValueTracker(-TAU)
        get_x = x_tracker.get_value

        dot = Dot(fill_color=YELLOW)
        dot.add_updater(lambda d: d.move_to(axes.i2gp(get_x(), graph)))
        v_line = always_redraw(
            lambda: axes.get_v_line_to_graph(get_x(), graph, line_func=DashedLine, color=YELLOW)
        )

        readout = VGroup(
            Text("sin(x) =", font_size=36),
            DecimalNumber(0, num_decimal_places=2, include_sign=True, font_size=36),
        ).arrange(RIGHT)
        readout.set_color(YELLOW)
        readout.to_corner(UR).shift(0.9 * DOWN)
        readout[1].add_updater(lambda m: m.set_value(math.sin(get_x())))

        self.play(FadeIn(dot), FadeIn(v_line), FadeIn(readout))
        self.play(x_tracker.animate.set_value(TAU), run_time=8, rate_func=linear)
        self.wait()
