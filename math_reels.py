# Compatibility entry point; new scenes live in reelstudio/scenes/.
from reelstudio.scenes.math_functions import (
    LinearReel as _LinearReel,
    QuadraticReel as _QuadraticReel,
    ExponentialReel as _ExponentialReel,
    LogarithmReel as _LogarithmReel,
    SigmoidReel as _SigmoidReel,
    ReLUReel as _ReLUReel,
)


# ManimGL discovers classes defined in the entry module, not imported classes.
class LinearReel(_LinearReel):
    pass


class QuadraticReel(_QuadraticReel):
    pass


class ExponentialReel(_ExponentialReel):
    pass


class LogarithmReel(_LogarithmReel):
    pass


class SigmoidReel(_SigmoidReel):
    pass


class ReLUReel(_ReLUReel):
    pass
