# Math to ML: six introductory reels

A beginner series with one idea per video: **prediction → loss → probability → classification → neural networks**. Each standalone scene runs approximately 35–45 seconds, with a hook, animated graph, three numerical examples, an ML connection, and a takeaway card. Videos use a 9:16 frame, dark background, cyan curves, gold tracking points, and readable on-screen explanations. They are silent exports; record the scripts below as voiceovers in your video editor.

## Render

Follow [the production guide](../../../docs/reelstudio.md) for setup and audio.
From the repository root:

```powershell
python -m reelstudio --draft
python -m reelstudio
python -m reelstudio SigmoidReel
python -m reelstudio --stills
python -m reelstudio LinearReel --voiceover assets/audio/LinearReel.wav
```

Final settings are 1080 x 1920 at 30 fps. Outputs live beneath
`videos/math_to_ml/`: `silent/`, `final/`, and `covers/`; drafts add a `drafts/`
parent. Scenes live in `reelstudio/scenes/math_functions.py`, the graph template
in `reelstudio/shared/math_reel.py`, and render settings in `configs/portrait.yml`.
No LaTeX is needed. Record one audio file per scene using the scripts below.

## Editorial rhythm

Start with the hook immediately; skip a separate logo intro. Read the numerical examples as the gold point moves, then leave a brief pause for the takeaway. Add voiceover captions in the editor, checking they do not cover the graph's numeric readout. Keep music quiet beneath speech. Check the final upload preview for interface overlays and cover cropping. The source reserves margins but does not simulate Instagram's interface.

Use the scripts as talking points, then align speech with the existing visual beats. If a sentence needs longer, increase its `caption(..., duration=...)` hold or the final `wait(4)`. The animations illustrate concepts; they do not train a model.

## 01 — Linear: your model's first guess

**Cover:** “A straight line can predict?”

**Voiceover:** “How does a model make its first guess? Start with a line: two times x, plus one. When x is zero, the output is one. That starting value is the bias. Move x up by one and the output rises by two. That's the weight: a constant rate of change. Real data won't sit perfectly on the line—look at these scattered points. Linear regression learns the weight and bias that fit the trend. You just met the simplest prediction model.”

**Caption:** “Weight controls the slope. Bias shifts the starting point. Next: how do we measure a bad prediction?”

## 02 — Quadratic: mistakes have a price

**Cover:** “Double the mistake. FOUR times the cost.”

**Voiceover:** “Why do big prediction mistakes hurt more? Let e be prediction minus the real answer. Squaring an error of minus two gives four. An error of minus one gives one. And a perfect prediction gives zero. Both positive and negative mistakes get penalized. Double the error and the squared penalty becomes four times bigger. Average these values over your data and you get mean squared error. The slope here is two e: moving downhill reduces this simple loss. That's our first glimpse of gradient descent.”

**Caption:** “Squared error is symmetric and magnifies large errors. This bowl is in error space; an entire neural network's loss need not be a simple bowl.”

## 03 — Exponential: scores become contenders

**Cover:** “How scores become probabilities”

**Voiceover:** “One extra step can create a much bigger output. Exp of zero is one. Exp of one is about two point seven two. Exp of two is about seven point three nine. Equal input steps multiply the output by the same factor. In machine learning, softmax first exponentiates class scores, then divides each result by their total. Scores zero, one, and two become probabilities of roughly nine, twenty-four, and sixty-seven percent. Bigger scores receive more probability. Exponentiation alone doesn't make probabilities—normalization does.”

**Caption:** “Softmax = exp(score) divided by the sum. Implementations usually subtract the largest score first for numerical stability.”

## 04 — Logarithm: confident mistakes cost more

**Cover:** “Confident + wrong = expensive”

**Voiceover:** “Imagine the correct class gets probability zero point nine. Negative natural log gives a small loss: about zero point one one. At probability one half, the loss is about zero point six nine. Give the correct class only zero point one and the loss jumps to two point three. Natural log reverses the exponential; the minus sign turns this into a useful penalty. As true-class probability approaches zero, loss grows without bound. This is the true-class term in cross-entropy: reward probability placed on the correct answer.”

**Caption:** “The graph shows -ln(p), derived from the logarithm. For binary classification, the full loss includes whichever label is actually true.”

## 05 — Sigmoid: from score to yes-or-no

**Cover:** “Any score → a number between 0 and 1”

**Voiceover:** “Your model outputs a score. How do we turn it into a probability? Meet sigmoid. Very negative inputs land near zero. At input zero, the output is exactly one half. Very positive inputs land near one. Logistic regression computes a weighted input score plus bias, then applies this curve to model a binary outcome. A threshold turns that probability into a label. One half is common, but the right threshold depends on the cost of mistakes. And a probability-shaped output isn't automatically well calibrated.”

**Caption:** “Logistic regression = linear score + sigmoid. Decision thresholds are a choice, not a law.”

## 06 — ReLU: one bend changes everything

**Cover:** “The tiny bend behind neural networks”

**Voiceover:** “This tiny bend helps neural networks learn richer patterns. ReLU means take the larger of zero and the input. Negative two becomes zero. Zero stays zero. Positive two passes through unchanged. Why does that matter? Stack only linear layers and the result is still a linear map. Add ReLU between layers and the network can combine many bends into complex shapes. Its slope is zero on the negative side and one on the positive side; at zero, the ordinary derivative isn't defined. Simple rule, powerful building block.”

**Caption:** “Linear → ReLU → linear: a first neural-network building block. Next series: combine prediction, loss, and gradients to train a tiny model.”

## Accuracy notes

- `2x + 1` is technically affine; “linear” follows common introductory ML terminology.
- The exponential and logarithm episodes show ingredients used in softmax and cross-entropy, rather than full training algorithms.
- Numerical values are rounded for readability. The tracking point uses the actual function value.
- The ReLU graph shows the function's bend, not an animation of a network learning. Negative-side zero gradients can contribute to inactive neurons.
