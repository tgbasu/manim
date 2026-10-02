"""Autopilot contracts: storyboards, writers, voices, publishers, and the queue.

Network services are replaced by fakes that record requests; audio checks use
real FFmpeg. Nothing here initializes the GPU renderer.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from reelstudio import storyboard as boards
from reelstudio.media import find_ffmpeg, media_duration
from reelstudio.publishers import InstagramPublisher, LocalPublisher, PublishError, YouTubePublisher
from reelstudio.render import ROOT
from reelstudio.voices import VOICE_LEAD, SilentVoice, Voice, narrate
from reelstudio.writers import (
    AnthropicWriter, LibraryWriter, OpenAICompatibleWriter, WriterError, brainstorm, parse_json,
    write_storyboard,
)


LIBRARY = ROOT / "projects" / "data_stories" / "storyboards"


def sample():
    return boards.load(LIBRARY / "accuracy_paradox.yml")


class StoryboardTests(unittest.TestCase):
    def test_bundled_storyboards_are_valid_and_reel_length(self):
        paths = sorted(LIBRARY.glob("*.yml"))
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            storyboard = boards.with_estimated_durations(boards.load(path))
            self.assertLess(boards.total_duration(storyboard), 75, path.name)
            self.assertTrue(all(tag.startswith("#") for tag in storyboard["hashtags"]))

    def test_every_problem_is_reported_at_once(self):
        broken = sample()
        broken["beats"][1]["visual"]["values"] = [1]
        broken["beats"][2]["visual"]["kind"] = "pie"
        broken["beats"][3]["narration"] = "word " * 60
        with self.assertRaises(boards.StoryboardError) as caught:
            boards.validate(broken)
        joined = "\n".join(caught.exception.problems)
        self.assertIn("beats[1].visual.values must have one value per label", joined)
        self.assertIn("beats[2].visual.kind must be one of", joined)
        self.assertIn("beats[3].narration has 60 words", joined)

    def test_unknown_visual_fields_are_rejected(self):
        broken = sample()
        broken["beats"][1]["visual"]["colour"] = "red"
        with self.assertRaisesRegex(boards.StoryboardError, "unknown field 'colour'"):
            boards.validate(broken)

    def test_json_schema_covers_every_visual_and_is_closed(self):
        schema = boards.json_schema()
        variants = schema["properties"]["beats"]["items"]["properties"]["visual"]["anyOf"]
        self.assertEqual([v["properties"]["kind"]["enum"][0] for v in variants], list(boards.VISUALS))

        def closed(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                    self.assertTrue(set(node["required"]) <= set(node["properties"]))
                for value in node.values():
                    closed(value)
            elif isinstance(node, list):
                for value in node:
                    closed(value)

        closed(schema)

    def test_caption_chunks_tile_the_speech_window(self):
        chunks = boards.caption_chunks("Real data is noisy. A line models the trend, mostly.", 4.0)
        self.assertEqual(chunks[0][0], 0)
        self.assertAlmostEqual(chunks[-1][1], 4.0)
        for (_, end, _), (start, _, _) in zip(chunks, chunks[1:]):
            self.assertAlmostEqual(end, start)
        self.assertTrue(all(len(words.split()) <= 4 for _, _, words in chunks))

    def test_srt_offsets_follow_beat_durations(self):
        storyboard = boards.with_estimated_durations(sample())
        srt = boards.srt_text(storyboard, lead=VOICE_LEAD)
        second_beat = storyboard["beats"][0]["duration"] + VOICE_LEAD
        stamp = f"00:00:{int(second_beat):02d},{round(second_beat % 1 * 1000):03d}"
        self.assertIn(f"{stamp} --> ", srt)
        self.assertTrue(srt.startswith("1\n00:00:00,150 --> "))

    def test_round_trip_through_json_and_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".json", ".yml"):
                path = boards.save(sample(), Path(directory) / f"board{suffix}")
                self.assertEqual(boards.load(path), sample())


class FakeAnthropic:
    """Records create() calls and replays canned responses."""

    def __init__(self, *responses):
        self.calls, self.responses = [], list(responses)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs, default=str)))
        stop_reason, text = self.responses.pop(0)
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class WriterTests(unittest.TestCase):
    def test_claude_request_uses_schema_effort_and_fallbacks(self):
        client = FakeAnthropic(("end_turn", json.dumps(sample())))
        result = write_storyboard(AnthropicWriter(client=client), "The accuracy paradox")
        self.assertEqual(result["title"], sample()["title"])
        call = client.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(call["output_config"]["effort"], "medium")
        self.assertEqual(call["output_config"]["format"]["schema"], boards.json_schema())
        self.assertIn("Visual kinds:", call["system"])

    def test_validation_errors_are_fed_back_for_repair(self):
        broken = sample()
        broken["beats"][1]["visual"]["highlight"] = 9
        client = FakeAnthropic(("end_turn", json.dumps(broken)), ("end_turn", json.dumps(sample())))
        write_storyboard(AnthropicWriter(client=client), "The accuracy paradox")
        repair = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in repair], ["user", "assistant", "user"])
        self.assertIn("beats[1].visual.highlight is out of range", repair[2]["content"])

    def test_writer_gives_up_after_the_attempt_limit(self):
        client = FakeAnthropic(*[("end_turn", "{}")] * 2)
        with self.assertRaisesRegex(WriterError, "after 2 attempts"):
            write_storyboard(AnthropicWriter(client=client), "x", attempts=2)

    def test_refusal_is_an_actionable_error(self):
        client = FakeAnthropic(("refusal", ""))
        with self.assertRaisesRegex(WriterError, "declined"):
            write_storyboard(AnthropicWriter(client=client), "x")

    def test_open_model_endpoint_and_fenced_output(self):
        requests = []

        def transport(url, payload, headers):
            requests.append((url, payload, headers))
            return {"choices": [{"message": {"content": "```json\n" + json.dumps(sample()) + "\n```"}}]}

        with mock.patch.dict(os.environ, {"LLM_BASE_URL": "", "OPENAI_API_KEY": ""}):
            writer = OpenAICompatibleWriter(model="llama3.1", transport=transport)
        write_storyboard(writer, "The accuracy paradox")
        url, payload, headers = requests[0]
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertIn("JSON Schema", payload["messages"][0]["content"])
        self.assertNotIn("Authorization", headers)

    def test_parse_json_rejects_prose(self):
        with self.assertRaises(WriterError):
            parse_json("Sorry, I cannot help with that.")

    def test_library_matches_topic_or_file_name(self):
        library = LibraryWriter(LIBRARY)
        self.assertEqual(library.find("The accuracy paradox")["slug"], "the_accuracy_paradox")
        self.assertEqual(library.find("Overfitting")["topic"], "Overfitting")
        with self.assertRaisesRegex(WriterError, "No storyboard"):
            library.find("Quantum gravity")

    def test_brainstorm_skips_covered_topics(self):
        ideas = {"ideas": [{"topic": "Overfitting", "angle": "a"}, {"topic": "Bootstrapping", "angle": "b"}]}
        client = FakeAnthropic(("end_turn", json.dumps(ideas)))
        result = brainstorm(AnthropicWriter(client=client), {"niche": "stats"}, 5, ["overfitting"])
        self.assertEqual(result, [{"topic": "Bootstrapping", "angle": "b"}])
        self.assertIn("niche: stats", client.calls[0]["system"])


class ToneVoice(Voice):
    """A deterministic stand-in for TTS: one tone of 0.1 s per word."""

    extension = ".wav"

    def __init__(self, ffmpeg):
        self.ffmpeg = ffmpeg

    def synthesize(self, text, destination):
        seconds = 0.1 * len(text.split())
        subprocess.run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", f"sine=frequency=330:duration={seconds}", str(destination)], check=True)
        return destination


class VoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = find_ffmpeg()
        except ValueError as error:
            raise unittest.SkipTest(str(error))

    def test_beat_durations_come_from_measured_speech(self):
        storyboard = sample()
        with tempfile.TemporaryDirectory() as directory:
            timed, track = narrate(storyboard, ToneVoice(self.ffmpeg), directory, self.ffmpeg)
            for beat in timed["beats"]:
                speech = 0.1 * len(beat["narration"].split())
                expected = max(boards.MIN_BEAT_SECONDS, VOICE_LEAD + speech + boards.BEAT_TAIL)
                self.assertAlmostEqual(beat["duration"], expected, delta=0.05)
            self.assertAlmostEqual(media_duration(track, self.ffmpeg), boards.total_duration(timed), delta=0.1)

    def test_silent_voice_estimates_timing_without_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            timed, track = narrate(sample(), SilentVoice(), directory, self.ffmpeg)
        self.assertIsNone(track)
        self.assertTrue(all(beat["duration"] >= boards.MIN_BEAT_SECONDS for beat in timed["beats"]))


METADATA = {"slug": "the_accuracy_paradox", "topic": "The accuracy paradox", "title": "99% accurate",
            "post_caption": "Caption?", "hashtags": ["#datascience"], "sources": []}


class RecordingTransport:
    def __init__(self, *responses):
        self.calls, self.responses = [], list(responses)

    def __call__(self, method, url, headers=None, data=None, timeout=300):
        body = data.read() if hasattr(data, "read") else data
        self.calls.append(SimpleNamespace(method=method, url=url, headers=headers or {}, body=body))
        status, response_headers, response = self.responses.pop(0)
        return status, response_headers, json.dumps(response).encode()


class PublisherTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.video = self.root / "final.mp4"
        self.video.write_bytes(b"video-bytes")

    def test_local_outbox_contains_post_materials(self):
        result = LocalPublisher(self.root / "outbox").publish(self.video, METADATA)
        folder = Path(result["location"])
        self.assertEqual((folder / "video.mp4").read_bytes(), b"video-bytes")
        self.assertIn("#datascience", (folder / "post.txt").read_text(encoding="utf-8"))

    def test_youtube_resumable_upload(self):
        transport = RecordingTransport(
            (200, {}, {"access_token": "token"}),
            (200, {"Location": "https://upload.example/session"}, {}),
            (200, {}, {"id": "abc123"}),
        )
        env = {"YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "secret", "YOUTUBE_REFRESH_TOKEN": "refresh"}
        with mock.patch.dict(os.environ, env):
            result = YouTubePublisher(transport=transport).publish(self.video, METADATA)
        token, start, upload = transport.calls
        self.assertIn(b"grant_type=refresh_token", token.body)
        resource = json.loads(start.body)
        self.assertEqual(resource["snippet"]["title"], "99% accurate #Shorts")
        self.assertEqual(resource["status"]["privacyStatus"], "private")
        self.assertEqual(start.headers["X-Upload-Content-Length"], str(len(b"video-bytes")))
        self.assertEqual((upload.method, upload.url, upload.body), ("PUT", "https://upload.example/session", b"video-bytes"))
        self.assertEqual(result["url"], "https://youtube.com/shorts/abc123")

    def test_youtube_requires_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PublishError, "YOUTUBE_CLIENT_ID"):
                YouTubePublisher(transport=RecordingTransport()).publish(self.video, METADATA)

    def test_instagram_waits_for_processing_then_publishes(self):
        transport = RecordingTransport(
            (200, {}, {"id": "container"}),
            (200, {}, {"success": True}),
            (200, {}, {"status_code": "IN_PROGRESS"}),
            (200, {}, {"status_code": "FINISHED"}),
            (200, {}, {"id": "media42"}),
        )
        sleeps = []
        env = {"INSTAGRAM_USER_ID": "17841", "INSTAGRAM_ACCESS_TOKEN": "token"}
        with mock.patch.dict(os.environ, env):
            result = InstagramPublisher(transport=transport, sleep=sleeps.append).publish(self.video, METADATA)
        create, upload, _, _, publish = transport.calls
        self.assertIn(b"media_type=REELS", create.body)
        self.assertIn(b"upload_type=resumable", create.body)
        self.assertEqual(upload.url, "https://rupload.facebook.com/ig-api-upload/v23.0/container")
        self.assertEqual(upload.headers["file_size"], str(len(b"video-bytes")))
        self.assertIn(b"creation_id=container", publish.body)
        self.assertEqual((result["id"], sleeps), ("media42", [10]))

    def test_instagram_processing_error_is_raised(self):
        transport = RecordingTransport((200, {}, {"id": "c"}), (200, {}, {}),
                                       (200, {}, {"status_code": "ERROR", "status": "bad codec"}))
        env = {"INSTAGRAM_USER_ID": "1", "INSTAGRAM_ACCESS_TOKEN": "t"}
        with mock.patch.dict(os.environ, env), self.assertRaisesRegex(PublishError, "bad codec"):
            InstagramPublisher(transport=transport, sleep=lambda _: None).publish(self.video, METADATA)


class QueueTests(unittest.TestCase):
    def setUp(self):
        from reelstudio.autopilot import Studio
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.studio = Studio("data_stories")
        self.studio.directory = Path(workspace.name)
        self.studio.output = Path(workspace.name) / "videos"
        self.studio.write_yaml("topics.yml", [{"topic": "Overfitting"}, "The accuracy paradox"])

    def make_run(self, draft):
        run = self.studio.output / "run"
        run.mkdir(parents=True, exist_ok=True)
        (run / "final.mp4").write_bytes(b"v")
        (run / "metadata.json").write_text(json.dumps({**METADATA, "draft": draft}), encoding="utf-8")
        return run

    def test_next_topic_skips_fully_published_topics(self):
        self.studio.write_yaml("published.yml", [{"slug": "overfitting", "platform": "local"}])
        self.assertEqual(self.studio.next_topic(["local"])["topic"], "The accuracy paradox")
        self.assertEqual(self.studio.next_topic(["local", "youtube"])["topic"], "Overfitting")

    def test_drafts_are_never_published_remotely_or_logged(self):
        run = self.make_run(draft=True)
        with self.assertRaisesRegex(PublishError, "Draft"):
            self.studio.publish(run, ["youtube"])
        self.studio.publish(run, ["local"])
        self.assertEqual(self.studio.log(), [])

    def test_publication_is_logged_once_per_platform(self):
        run = self.make_run(draft=False)
        self.studio.publish(run, ["local"])
        self.studio.publish(run, ["local"])
        log = self.studio.log()
        self.assertEqual([(e["slug"], e["platform"]) for e in log], [("the_accuracy_paradox", "local")])


if __name__ == "__main__":
    unittest.main()
