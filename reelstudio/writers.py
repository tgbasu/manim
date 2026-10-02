"""Storyboard writers: Claude, OpenAI-compatible open models, or a local library.

Every writer returns a storyboard that passed ``storyboard.validate``. LLM
writers get the validation errors back and repair their own output, so a
scheduled run never renders a malformed script.

Providers:
  anthropic  Claude through the official SDK with structured JSON output
  openai     any OpenAI-compatible chat server: Ollama, LM Studio, vLLM,
             llama.cpp, Groq, Together, or OpenAI itself
  library    hand-written storyboards under projects/<name>/storyboards/
"""

import json
import os
from pathlib import Path
import re
import urllib.request

from reelstudio import storyboard as boards


class WriterError(ValueError):
    pass


SYSTEM_PROMPT = """You are the head writer of a fast-growing faceless short-video channel that teaches \
data science through stories. Each video is a 35-60 second vertical reel: animated charts, \
big captions, and a voiceover.

What makes these videos work:
- The first beat is the hook. Its narration is one punchy sentence under 16 words that opens a \
curiosity gap: a surprising result, a costly mistake, or a counterintuitive claim. Its title is \
the same idea in under 6 words. Never open with "In this video" or a greeting.
- One idea per video, told as a story: a situation, the tension, the reveal, then a takeaway the \
viewer can use today. The last beat lands the lesson in one memorable line that echoes the hook, \
so the video loops cleanly.
- Every beat's visual must show exactly what its narration says. Prefer real charts over \
statements; use statement only for the hook and the final line.
- Speak like a sharp friend, not a textbook: short sentences, plain words, concrete numbers. \
Write numbers in narration the way they are spoken ("ninety-nine percent").
- On-screen text is short. Titles stay under 34 characters. Labels must fit the limits below.
- Be accurate. Use well-established facts only. When numbers are invented to illustrate an idea, \
keep them realistic, say "Numbers are illustrative." in post_caption, and leave sources empty. \
Never invent sources or attribute statistics to real people or organizations.
- post_caption is 2-3 short lines and ends with a question that invites comments. Give 4-6 \
relevant hashtags without the # symbol. The title is a YouTube title under 90 characters ending \
with #Shorts.

Storyboard rules: {min_beats}-{max_beats} beats, under {beat_words} words of narration per beat and \
under {total_words} words in total.

Visual kinds:
{visuals}
"""


def system_prompt(channel=None):
    prompt = SYSTEM_PROMPT.format(
        min_beats=boards.MIN_BEATS, max_beats=boards.MAX_BEATS, beat_words=boards.MAX_BEAT_WORDS,
        total_words=boards.MAX_TOTAL_WORDS, visuals=boards.visual_guide(),
    )
    if channel:
        details = {key: channel[key] for key in ("niche", "audience", "voice_and_style") if channel.get(key)}
        if details:
            prompt += "\nChannel:\n" + "\n".join(f"- {key}: {value}" for key, value in details.items()) + "\n"
    return prompt


IDEAS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["ideas"],
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["topic", "angle"],
        "properties": {
            "topic": {"type": "string", "description": "Concept name, under 50 characters"},
            "angle": {"type": "string", "description": "The story or hook that makes it gripping"},
        },
    }}},
}


def parse_json(text):
    """Parse model output, tolerating a Markdown code fence around the JSON."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end < start:
        raise WriterError("Model response contained no JSON object")
    try:
        return json.loads(candidate[start:end + 1])
    except json.JSONDecodeError as error:
        raise WriterError(f"Model returned invalid JSON: {error}") from error


class AnthropicWriter:
    """Claude via the official SDK, constrained to the storyboard JSON schema."""

    def __init__(self, model="claude-opus-5-5", effort="medium", max_tokens=16000, client=None):
        self.model, self.effort, self.max_tokens = model, effort, max_tokens
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as error:
                raise WriterError("Install the Claude writer: python -m pip install -r requirements-ai.txt") from error
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system, messages, schema):
        # "default" fallbacks re-run a declined request on a suitable model server-side.
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=messages,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            raise WriterError("Claude declined this topic; choose another")
        if response.stop_reason == "max_tokens":
            raise WriterError("Claude ran out of output tokens; raise max_tokens")
        text = next((block.text for block in response.content if block.type == "text"), "")
        return text, response.content


class OpenAICompatibleWriter:
    """Open-source or hosted models behind an OpenAI-compatible chat endpoint."""

    def __init__(self, model="qwen3:14b", base_url=None, api_key_env="OPENAI_API_KEY",
                 temperature=0.7, timeout=600, transport=None):
        self.model, self.temperature, self.timeout = model, temperature, timeout
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or "http://localhost:11434/v1").rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        self.transport = transport or self._post

    def _post(self, url, payload, headers):
        request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())

    def complete(self, system, messages, schema):
        # Open models follow a schema best when it is in the prompt as well as the request.
        system = f"{system}\nRespond with one JSON object matching this JSON Schema:\n{json.dumps(schema)}"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        result = self.transport(f"{self.base_url}/chat/completions", payload, headers)
        try:
            text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise WriterError(f"Unexpected chat completion response: {str(result)[:200]}") from error
        return text, text


class LibraryWriter:
    """Serves hand-written storyboards; lets the pipeline run with no model at all."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def storyboards(self):
        return sorted(self.directory.glob("*.yml")) + sorted(self.directory.glob("*.json"))

    def find(self, topic):
        slug = boards.slugify(topic)
        for path in self.storyboards():
            storyboard = boards.load(path)
            if slug in (path.stem, storyboard["slug"]) or boards.slugify(storyboard["topic"]) == slug:
                return storyboard
        raise WriterError(f"No storyboard for {topic!r} in {self.directory}; add one or use an LLM writer")


def make_writer(settings, project_dir):
    settings = dict(settings or {"provider": "library"})
    provider = settings.pop("provider", "library")
    if provider == "anthropic":
        return AnthropicWriter(**settings)
    if provider == "openai":
        return OpenAICompatibleWriter(**settings)
    if provider == "library":
        return LibraryWriter(Path(project_dir) / settings.get("directory", "storyboards"))
    raise WriterError(f"Unknown writer provider {provider!r}; choose anthropic, openai, or library")


def write_storyboard(writer, topic, angle="", channel=None, attempts=3):
    """Write and validate a storyboard, feeding validation errors back for repair."""
    if isinstance(writer, LibraryWriter):
        return writer.find(topic)
    request = f"Write a storyboard about: {topic}"
    if angle:
        request += f"\nStory angle: {angle}"
    messages = [{"role": "user", "content": request}]
    schema = boards.json_schema()
    system = system_prompt(channel)
    problems = []
    for _ in range(attempts):
        text, content = writer.complete(system, messages, schema)
        try:
            storyboard = parse_json(text)
            storyboard.setdefault("topic", topic)
            return boards.validate(storyboard)
        except (WriterError, boards.StoryboardError) as error:
            problems = getattr(error, "problems", [str(error)])
        messages += [
            {"role": "assistant", "content": content},
            {"role": "user", "content": "That storyboard failed validation:\n- " + "\n- ".join(problems)
                                        + "\nReturn the complete corrected storyboard."},
        ]
    raise WriterError(f"No valid storyboard after {attempts} attempts:\n- " + "\n- ".join(problems))


def brainstorm(writer, channel, count=10, exclude=()):
    """Propose new topics for the channel, skipping ones already covered."""
    if isinstance(writer, LibraryWriter):
        raise WriterError("The library writer cannot brainstorm; configure an LLM writer")
    request = (f"Propose {count} new video ideas for this channel. Mix fundamentals, common mistakes, "
               "famous stories from data history, and practical tools. Each needs a gripping story angle.")
    if exclude:
        request += "\nAlready covered, do not repeat: " + "; ".join(exclude)
    text, _ = writer.complete(system_prompt(channel), [{"role": "user", "content": request}], IDEAS_SCHEMA)
    ideas = parse_json(text).get("ideas")
    if not isinstance(ideas, list):
        raise WriterError("Brainstorm response had no ideas list")
    covered = {boards.slugify(topic) for topic in exclude}
    return [idea for idea in ideas if isinstance(idea, dict) and isinstance(idea.get("topic"), str)
            and boards.slugify(idea["topic"]) not in covered][:count]
