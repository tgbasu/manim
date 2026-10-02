"""Production contracts and real audio/video integration without GPU imports."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from reelstudio.media import find_ffmpeg, media_duration, mix_audio
from reelstudio.render import load_project, narration_files


class ProjectTests(unittest.TestCase):
    def test_bundled_projects_resolve_to_existing_scene_files(self):
        for name in ("math_to_ml", "getting_started"):
            project, scene_file = load_project(name)
            self.assertTrue(scene_file.is_file())
            self.assertTrue(project["scenes"])

    def test_unknown_project_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown project"):
            load_project("missing_project")

    def test_series_requires_a_separate_recording_per_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            recording = Path(directory) / "LinearReel.wav"
            recording.touch()
            self.assertEqual(narration_files(["LinearReel"], audio_dir=directory), {"LinearReel": recording.resolve()})
            with self.assertRaisesRegex(ValueError, "QuadraticReel"):
                narration_files(["LinearReel", "QuadraticReel"], audio_dir=directory)
            (Path(directory) / "LinearReel.mp3").touch()
            with self.assertRaisesRegex(ValueError, "found 2"):
                narration_files(["LinearReel"], audio_dir=directory)

    def test_single_voiceover_is_not_repeated_across_a_series(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            narration_files(["LinearReel", "QuadraticReel"], voiceover="recording.wav")


class AudioIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = find_ffmpeg()
        except ValueError as error:
            raise unittest.SkipTest(str(error))

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.video = self.root / "silent.mp4"
        self.voice = self.root / "voice.wav"
        self.music = self.root / "music.wav"
        self.generate("color=c=blue:s=90x160:r=10:d=1", self.video, "-c:v", "libx264")
        self.generate("sine=frequency=440:duration=1.6", self.voice)
        self.generate("sine=frequency=220:duration=0.3", self.music)

    def generate(self, source, destination, *options):
        subprocess.run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", source, *options, str(destination)], check=True)

    def test_long_narration_extends_video_and_includes_audio(self):
        output = self.root / "final.mp4"
        original = self.video.read_bytes()
        mix_audio(self.video, output, self.ffmpeg, voiceover=self.voice,
                  music=self.music, offset=0.2)
        self.assertAlmostEqual(media_duration(output, self.ffmpeg), 1.8, delta=0.15)
        self.assertEqual(self.video.read_bytes(), original)
        result = subprocess.run([self.ffmpeg, "-hide_banner", "-i", str(output)], capture_output=True, text=True)
        self.assertIn("Audio: aac", result.stderr)
        self.assertIn("Video: h264", result.stderr)
        self.assertIn("90x160", result.stderr)
        # Decode the whole output, catching broken streams beyond their metadata.
        subprocess.run([self.ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)

    def test_short_narration_does_not_shorten_video(self):
        output = self.root / "short_voice.mp4"
        mix_audio(self.video, output, self.ffmpeg, voiceover=self.music)
        self.assertAlmostEqual(media_duration(output, self.ffmpeg), 1, delta=0.1)

    def test_music_only_loops_to_video_duration(self):
        output = self.root / "music_only.mp4"
        mix_audio(self.video, output, self.ffmpeg, music=self.music)
        self.assertAlmostEqual(media_duration(output, self.ffmpeg), 1, delta=0.1)


if __name__ == "__main__":
    unittest.main()
