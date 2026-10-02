"""The storyboard contract shared by writers, voices, the scene, and publishers.

A storyboard is plain JSON/YAML: a list of beats, each with narration and one
visual. Writers (LLMs or humans) produce it, voices fill in each beat's
duration, the StoryReel scene renders it, and publishers read its metadata.
"""

import json
from pathlib import Path
import re

import yaml


WORDS_PER_SECOND = 2.6
MIN_BEAT_SECONDS = 2.5
MAX_BEATS = 9
MIN_BEATS = 4
MAX_BEAT_WORDS = 40
MAX_TOTAL_WORDS = 190
# Silence kept at the end of each beat so transitions never cut off speech.
BEAT_TAIL = 0.35

# Field types: str, int, number, bool, strs, numbers, ints, points, matrix, series.
# Each entry: field -> (type, required, description shown to the writer).
VISUALS = {
    "statement": ({}, "No chart; the beat title fills the screen. Best for the hook and punchlines."),
    "stat": ({
        "value": ("number", True, "Number that counts up, e.g. 80"),
        "prefix": ("str", False, "Shown before the number, e.g. $"),
        "suffix": ("str", False, "Shown after the number, e.g. %"),
        "label": ("str", True, "What the number means, under 40 characters"),
        "decimals": ("int", False, "Decimal places, 0-2"),
    }, "One big number counting up."),
    "bars": ({
        "labels": ("strs", True, "2-6 short category names"),
        "values": ("numbers", True, "One nonnegative value per label"),
        "highlight": ("int", False, "Zero-based index of the bar to emphasize"),
        "unit": ("str", False, "Suffix for value labels, e.g. %"),
    }, "Animated bar chart."),
    "line": ({
        "series": ("series", True, "1-3 series: {name, values}; 3-12 values each, same length"),
        "x_labels": ("strs", False, "Optional label per point"),
        "highlight_index": ("int", False, "Point index to mark, e.g. where overfitting starts"),
    }, "Line chart, e.g. training vs validation loss."),
    "scatter": ({
        "points": ("points", True, "5-60 [x, y] pairs"),
        "groups": ("ints", False, "Cluster id (0-3) per point, for clustering stories"),
        "fit": ("bool", False, "Draw the least-squares regression line"),
    }, "Scatter plot, optionally with a fitted line or colored clusters."),
    "distribution": ({
        "mean": ("number", True, "Mean of the normal curve"),
        "std": ("number", True, "Positive standard deviation"),
        "shade_from": ("number", False, "Left edge of the shaded region"),
        "shade_to": ("number", False, "Right edge of the shaded region"),
    }, "Normal distribution with an optional shaded area (its probability is computed)."),
    "flow": ({
        "steps": ("strs", True, "2-5 short pipeline steps, under 22 characters each"),
    }, "Pipeline diagram; a data packet travels through the steps."),
    "matrix": ({
        "rows": ("strs", True, "Row labels, 2-3"),
        "cols": ("strs", True, "Column labels, 2-3"),
        "values": ("matrix", True, "Rows of numbers matching rows x cols"),
    }, "Grid such as a confusion matrix."),
    "compare": ({
        "left_title": ("str", True, "Left column heading"),
        "left": ("strs", True, "1-4 short points"),
        "right_title": ("str", True, "Right column heading"),
        "right": ("strs", True, "1-4 short points"),
    }, "Side-by-side comparison, e.g. myth vs fact."),
    "bullets": ({
        "items": ("strs", True, "2-4 short points revealed one by one"),
    }, "Checklist revealed in sync with the narration."),
    "code": ({
        "lines": ("strs", True, "1-8 lines of code, under 34 characters each"),
    }, "Monospaced code snippet, e.g. a pandas one-liner."),
}

TEXT_LIMITS = {"title": 34, "label": 40, "step": 22, "item": 34, "code": 34, "cover_title": 40}


class StoryboardError(ValueError):
    """Raised with every problem found, so a writer can repair all of them at once."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("Invalid storyboard:\n- " + "\n- ".join(self.problems))


def word_count(text):
    return len(re.findall(r"[\w'%$.-]+", text))


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:60] or "reel"


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _check_type(kind, value):
    if kind == "str":
        return isinstance(value, str) and value.strip() != ""
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return _is_number(value)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "strs":
        return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)
    if kind == "numbers":
        return isinstance(value, list) and bool(value) and all(_is_number(v) for v in value)
    if kind == "ints":
        return isinstance(value, list) and bool(value) and all(_check_type("int", v) for v in value)
    if kind == "points":
        return isinstance(value, list) and bool(value) and all(
            isinstance(p, list) and len(p) == 2 and all(_is_number(v) for v in p) for p in value)
    if kind == "matrix":
        return isinstance(value, list) and bool(value) and all(_check_type("numbers", row) for row in value)
    if kind == "series":
        return isinstance(value, list) and bool(value) and all(
            isinstance(s, dict) and set(s) <= {"name", "values"} and _check_type("str", s.get("name"))
            and _check_type("numbers", s.get("values")) for s in value)
    raise AssertionError(kind)


def _check_visual(visual, where):
    problems = []
    if not isinstance(visual, dict) or visual.get("kind") not in VISUALS:
        return [f"{where}.kind must be one of: {', '.join(VISUALS)}"]
    kind = visual["kind"]
    fields = VISUALS[kind][0]
    for name in visual:
        if name != "kind" and name not in fields:
            problems.append(f"{where}: unknown field {name!r} for kind {kind!r}")
    for name, (field_type, required, _) in fields.items():
        value = visual.get(name)
        if value is None:
            if required:
                problems.append(f"{where}.{name} is required for kind {kind!r}")
        elif not _check_type(field_type, value):
            problems.append(f"{where}.{name} must be of type {field_type}")
    if problems:
        return problems

    def limit(items, low, high, label):
        if not low <= len(items) <= high:
            problems.append(f"{where}.{label} needs {low}-{high} entries, got {len(items)}")

    def short(items, maximum, label):
        for item in items:
            if len(item) > maximum:
                problems.append(f"{where}.{label} entry {item!r} exceeds {maximum} characters")

    if kind == "stat":
        short([visual["label"]], TEXT_LIMITS["label"], "label")
        if not 0 <= visual.get("decimals", 0) <= 2:
            problems.append(f"{where}.decimals must be 0-2")
    elif kind == "bars":
        limit(visual["labels"], 2, 6, "labels")
        short(visual["labels"], 14, "labels")
        if len(visual["values"]) != len(visual["labels"]):
            problems.append(f"{where}.values must have one value per label")
        if any(v < 0 for v in visual["values"]) or max(visual["values"]) <= 0:
            problems.append(f"{where}.values must be nonnegative with a positive maximum")
        if "highlight" in visual and not 0 <= visual["highlight"] < len(visual["labels"]):
            problems.append(f"{where}.highlight is out of range")
    elif kind == "line":
        limit(visual["series"], 1, 3, "series")
        lengths = {len(s["values"]) for s in visual["series"]}
        if len(lengths) != 1 or not 3 <= lengths.pop() <= 12:
            problems.append(f"{where}.series values must share one length of 3-12")
        else:
            count = len(visual["series"][0]["values"])
            if "x_labels" in visual and len(visual["x_labels"]) != count:
                problems.append(f"{where}.x_labels must have one label per value")
            if "highlight_index" in visual and not 0 <= visual["highlight_index"] < count:
                problems.append(f"{where}.highlight_index is out of range")
    elif kind == "scatter":
        limit(visual["points"], 5, 60, "points")
        if "groups" in visual:
            if len(visual["groups"]) != len(visual["points"]):
                problems.append(f"{where}.groups needs one id per point")
            if any(not 0 <= g <= 3 for g in visual["groups"]):
                problems.append(f"{where}.groups ids must be 0-3")
        xs = {p[0] for p in visual["points"]}
        ys = {p[1] for p in visual["points"]}
        if len(xs) < 2 or len(ys) < 2:
            problems.append(f"{where}.points must vary in both x and y")
    elif kind == "distribution":
        if visual["std"] <= 0:
            problems.append(f"{where}.std must be positive")
        if ("shade_from" in visual) != ("shade_to" in visual):
            problems.append(f"{where}: give both shade_from and shade_to, or neither")
        elif "shade_from" in visual and visual["shade_from"] >= visual["shade_to"]:
            problems.append(f"{where}.shade_from must be below shade_to")
    elif kind == "flow":
        limit(visual["steps"], 2, 5, "steps")
        short(visual["steps"], TEXT_LIMITS["step"], "steps")
    elif kind == "matrix":
        limit(visual["rows"], 2, 3, "rows")
        limit(visual["cols"], 2, 3, "cols")
        if len(visual["values"]) != len(visual["rows"]) or any(
                len(row) != len(visual["cols"]) for row in visual["values"]):
            problems.append(f"{where}.values must be a {len(visual['rows'])}x{len(visual['cols'])} grid")
    elif kind == "compare":
        for side in ("left", "right"):
            limit(visual[side], 1, 4, side)
            short(visual[side], 26, side)
            short([visual[f"{side}_title"]], 16, f"{side}_title")
    elif kind == "bullets":
        limit(visual["items"], 2, 4, "items")
        short(visual["items"], TEXT_LIMITS["item"], "items")
    elif kind == "code":
        limit(visual["lines"], 1, 8, "lines")
        short(visual["lines"], TEXT_LIMITS["code"], "lines")
    return problems


def validate(storyboard):
    """Return a normalized copy of the storyboard or raise StoryboardError."""
    problems = []
    if not isinstance(storyboard, dict):
        raise StoryboardError(["Storyboard must be a mapping"])
    allowed = {"topic", "title", "cover_title", "beats", "post_caption", "hashtags", "sources", "slug"}
    for key in storyboard:
        if key not in allowed:
            problems.append(f"Unknown top-level field {key!r}")
    for key in ("topic", "title", "cover_title", "post_caption"):
        if not _check_type("str", storyboard.get(key)):
            problems.append(f"{key} must be a nonempty string")
    if _check_type("str", storyboard.get("cover_title")) and len(storyboard["cover_title"]) > TEXT_LIMITS["cover_title"]:
        problems.append(f"cover_title exceeds {TEXT_LIMITS['cover_title']} characters")
    hashtags = storyboard.get("hashtags", [])
    if not isinstance(hashtags, list) or not all(isinstance(t, str) and re.fullmatch(r"#?\w+", t) for t in hashtags):
        problems.append("hashtags must be a list of single words")
    if not isinstance(storyboard.get("sources", []), list):
        problems.append("sources must be a list of strings")
    beats = storyboard.get("beats")
    if not isinstance(beats, list) or not MIN_BEATS <= len(beats) <= MAX_BEATS:
        problems.append(f"beats must be a list of {MIN_BEATS}-{MAX_BEATS} beats")
        beats = beats if isinstance(beats, list) else []
    total_words = 0
    for index, beat in enumerate(beats):
        where = f"beats[{index}]"
        if not isinstance(beat, dict):
            problems.append(f"{where} must be a mapping")
            continue
        for key in beat:
            if key not in {"title", "narration", "visual", "duration"}:
                problems.append(f"{where}: unknown field {key!r}")
        if not _check_type("str", beat.get("title")):
            problems.append(f"{where}.title must be a nonempty string")
        elif len(beat["title"]) > TEXT_LIMITS["title"]:
            problems.append(f"{where}.title exceeds {TEXT_LIMITS['title']} characters")
        if not _check_type("str", beat.get("narration")):
            problems.append(f"{where}.narration must be a nonempty string")
        else:
            words = word_count(beat["narration"])
            total_words += words
            if words > MAX_BEAT_WORDS:
                problems.append(f"{where}.narration has {words} words; keep it under {MAX_BEAT_WORDS}")
        if "duration" in beat and not (_is_number(beat["duration"]) and beat["duration"] > 0):
            problems.append(f"{where}.duration must be a positive number")
        problems += _check_visual(beat.get("visual"), f"{where}.visual")
    if total_words > MAX_TOTAL_WORDS:
        problems.append(f"Narration totals {total_words} words; keep it under {MAX_TOTAL_WORDS} (about 70 seconds)")
    if problems:
        raise StoryboardError(problems)
    result = json.loads(json.dumps(storyboard))
    result["hashtags"] = ["#" + tag.lstrip("#") for tag in hashtags]
    result.setdefault("sources", [])
    result.setdefault("slug", slugify(result["topic"]))
    return result


def estimate_duration(narration):
    return max(MIN_BEAT_SECONDS, word_count(narration) / WORDS_PER_SECOND + 0.6)


def with_estimated_durations(storyboard):
    """Fill missing beat durations from word counts, for silent drafts."""
    result = json.loads(json.dumps(storyboard))
    for beat in result["beats"]:
        beat.setdefault("duration", round(estimate_duration(beat["narration"]), 3))
    return result


def total_duration(storyboard):
    return sum(beat["duration"] for beat in storyboard["beats"])


def caption_chunks(text, duration, max_words=4):
    """Split narration into short on-screen phrases timed by character count."""
    words = text.split()
    chunks, current = [], []
    for word in words:
        current.append(word)
        if len(current) >= max_words or word[-1] in ".,;:!?":
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    weights = [len(chunk) + 4 for chunk in chunks]
    total, start, timed = sum(weights), 0.0, []
    for chunk, weight in zip(chunks, weights):
        end = start + duration * weight / total
        timed.append((start, end, chunk))
        start = end
    return timed


def srt_text(storyboard, lead=0.0):
    """SubRip captions for platforms that accept caption uploads."""
    def stamp(seconds):
        millis = round(seconds * 1000)
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    entries, offset = [], 0.0
    for beat in storyboard["beats"]:
        speech = max(0.1, beat["duration"] - lead - BEAT_TAIL)
        for start, end, chunk in caption_chunks(beat["narration"], speech):
            entries.append(f"{len(entries) + 1}\n{stamp(offset + lead + start)} --> {stamp(offset + lead + end)}\n{chunk}\n")
        offset += beat["duration"]
    return "\n".join(entries)



def load(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    return validate(data)


def save(storyboard, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(storyboard, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return path


_JSON_TYPES = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "number": {"type": "number"},
    "bool": {"type": "boolean"},
    "strs": {"type": "array", "items": {"type": "string"}},
    "numbers": {"type": "array", "items": {"type": "number"}},
    "ints": {"type": "array", "items": {"type": "integer"}},
    "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
    "matrix": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
    "series": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["name", "values"],
        "properties": {"name": {"type": "string"}, "values": {"type": "array", "items": {"type": "number"}}},
    }},
}


def json_schema():
    """JSON Schema for structured LLM output; semantic limits are checked by validate()."""
    visuals = []
    for kind, (fields, description) in VISUALS.items():
        properties = {"kind": {"type": "string", "enum": [kind]}}
        for name, (field_type, _, field_description) in fields.items():
            properties[name] = dict(_JSON_TYPES[field_type], description=field_description)
        visuals.append({
            "type": "object", "description": description, "additionalProperties": False,
            "properties": properties,
            "required": ["kind"] + [name for name, spec in fields.items() if spec[1]],
        })
    beat = {
        "type": "object", "additionalProperties": False, "required": ["title", "narration", "visual"],
        "properties": {
            "title": {"type": "string", "description": f"On-screen headline, under {TEXT_LIMITS['title']} characters"},
            "narration": {"type": "string", "description": f"Spoken words for this beat, under {MAX_BEAT_WORDS} words"},
            "visual": {"anyOf": visuals},
        },
    }
    return {
        "type": "object", "additionalProperties": False,
        "required": ["topic", "title", "cover_title", "beats", "post_caption", "hashtags", "sources"],
        "properties": {
            "topic": {"type": "string"},
            "title": {"type": "string", "description": "Video title for YouTube, under 90 characters"},
            "cover_title": {"type": "string", "description": "2-6 word thumbnail text"},
            "beats": {"type": "array", "items": beat, "description": f"{MIN_BEATS}-{MAX_BEATS} beats; the first is the hook"},
            "post_caption": {"type": "string", "description": "Social post caption with a question to drive comments"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "string"},
                        "description": "Where real statistics come from; empty when numbers are illustrative"},
        },
    }


def visual_guide():
    """Human-readable visual catalog for prompts and docs."""
    lines = []
    for kind, (fields, description) in VISUALS.items():
        parts = [f"{name}{'' if spec[1] else '?'}: {spec[2]}" for name, spec in fields.items()]
        lines.append(f"- {kind}: {description}" + (f" Fields: {'; '.join(parts)}." if parts else ""))
    return "\n".join(lines)
