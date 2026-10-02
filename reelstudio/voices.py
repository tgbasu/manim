"""Text-to-speech providers and per-beat narration timing.

Every beat is synthesized separately and measured, then the beat's duration is
set from the real audio. The scene renders to those durations and the beat
clips are placed on one track at the same offsets, so speech, captions, and
visuals stay in sync without manual editing.

Providers:
  silent  no audio; durations estimated from word counts (drafts, CI)
  edge    Microsoft Edge neural voices via the free ``edge-tts`` package
  piper   local open-source Piper TTS (``piper`` executable and a voice model)
  openai  any OpenAI-compatible /v1/audio/speech server: OpenAI, or local
          open-source servers such as Kokoro-FastAPI or openedai-speech
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

from reelstudio import storyboard as boards
from reelstudio.media import media_duration


# Must match reelstudio/scenes/story_reel.py.
VOICE_LEAD = 0.15


class Voice:
    extension = ".mp3"

    def synthesize(self, text, destination):
        raise NotImplementedError


class SilentVoice(Voice):
    """Produces no audio; narrate() falls back to estimated durations."""

    def synthesize(self, text, destination):
        return None


class EdgeVoice(Voice):
    def __init__(self, voice="en-US-AndrewMultilingualNeural", rate="+5%", pitch="+0Hz"):
        self.voice, self.rate, self.pitch = voice, rate, pitch

    def synthesize(self, text, destination):
        try:
            import edge_tts
        except ImportError as error:
            raise ValueError("Install the edge voice: python -m pip install -r requirements-ai.txt") from error
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
        asyncio.run(communicate.save(str(destination)))
        return destination


class PiperVoice(Voice):
    extension = ".wav"

    def __init__(self, model, executable="piper", length_scale=None):
        self.model, self.executable, self.length_scale = model, executable, length_scale

    def synthesize(self, text, destination):
        executable = shutil.which(self.executable)
        if not executable:
            raise ValueError("Piper is not installed; see https://github.com/rhasspy/piper")
        command = [executable, "--model", str(self.model), "--output_file", str(destination)]
        if self.length_scale:
            command += ["--length_scale", str(self.length_scale)]
        subprocess.run(command, input=text, text=True, check=True, capture_output=True)
        return destination


class OpenAISpeechVoice(Voice):
    def __init__(self, voice="alloy", model="tts-1", base_url=None, api_key_env="OPENAI_API_KEY", speed=1.0):
        self.voice, self.model, self.speed = voice, model, speed
        self.base_url = (base_url or os.environ.get("TTS_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")

    def synthesize(self, text, destination):
        body = json.dumps({"model": self.model, "voice": self.voice, "input": text,
                           "speed": self.speed, "response_format": "mp3"}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}/audio/speech", data=body, headers=headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            Path(destination).write_bytes(response.read())
        return destination


PROVIDERS = {"silent": SilentVoice, "edge": EdgeVoice, "piper": PiperVoice, "openai": OpenAISpeechVoice}


def make_voice(settings):
    settings = dict(settings or {"provider": "silent"})
    provider = settings.pop("provider", "silent")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown voice provider {provider!r}; choose from {', '.join(PROVIDERS)}")
    return PROVIDERS[provider](**settings)


def narrate(storyboard, voice, workdir, ffmpeg):
    """Synthesize each beat, set beat durations, and return (storyboard, track or None)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    timed = json.loads(json.dumps(storyboard))
    clips = []
    for index, beat in enumerate(timed["beats"]):
        clip = voice.synthesize(beat["narration"], workdir / f"beat_{index:02d}{voice.extension}")
        if clip is None:
            beat["duration"] = round(boards.estimate_duration(beat["narration"]), 3)
            continue
        speech = media_duration(clip, ffmpeg)
        beat["duration"] = round(max(boards.MIN_BEAT_SECONDS, VOICE_LEAD + speech + boards.BEAT_TAIL), 3)
        clips.append((clip, sum(b["duration"] for b in timed["beats"][:index]) + VOICE_LEAD))
    if not clips:
        return timed, None
    track = workdir / "narration.wav"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    filters = []
    for index, (clip, start) in enumerate(clips):
        command += ["-i", str(clip)]
        filters.append(f"[{index}:a]aresample=48000,adelay={round(start * 1000)}:all=1[a{index}]")
    mix_inputs = "".join(f"[a{index}]" for index in range(len(clips)))
    filters.append(f"{mix_inputs}amix=inputs={len(clips)}:duration=longest:normalize=0,"
                   f"loudnorm=I=-16:TP=-1.5:LRA=11,apad[voice]")
    command += ["-filter_complex", ";".join(filters), "-map", "[voice]", "-ar", "48000",
                "-t", f"{boards.total_duration(timed):.3f}", str(track)]
    subprocess.run(command, check=True)
    return timed, track
