"""FFmpeg post-production, independent of Manim and GPU initialization."""

from pathlib import Path
import re
import shutil
import subprocess


def find_ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as error:
        raise ValueError("Install FFmpeg or run: python -m pip install -r requirements-reels.txt") from error


def media_duration(path, ffmpeg):
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise ValueError(f"Cannot read media duration: {path}")
    hours, minutes, seconds = map(float, match.groups())
    return hours * 3600 + minutes * 60 + seconds


def mix_audio(video, output, ffmpeg, voiceover=None, music=None, offset=0, music_volume=0.12):
    """Keep narration in full; freeze the final video frame if it runs longer."""
    if not voiceover and not music:
        raise ValueError("Supply narration or music to create an audio export")
    if offset < 0 or not 0 <= music_volume <= 1:
        raise ValueError("Offset must be nonnegative and music volume between 0 and 1")
    video, output = Path(video), Path(output)
    if video.resolve() == output.resolve():
        raise ValueError("Audio output must differ from the silent source")
    duration = media_duration(video, ffmpeg)
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    filters = []
    if voiceover:
        duration = max(duration, media_duration(voiceover, ffmpeg) + offset)
        command += ["-i", str(voiceover)]
        filters.append(f"[1:a]adelay={round(offset * 1000)}:all=1,apad[voice]")
    if music:
        music_index = 2 if voiceover else 1
        command += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{music_index}:a]volume={music_volume}[music]")
    if voiceover and music:
        filters.append("[voice][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:latency=1[audio]")
    else:
        source = "voice" if voiceover else "music"
        filters.append(f"[{source}]anull[audio]")
    extension = duration - media_duration(video, ffmpeg)
    if extension > 0.01:
        command += ["-vf", f"tpad=stop_mode=clone:stop_duration={extension:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    else:
        command += ["-c:v", "copy"]
    command += ["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[audio]",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{duration:.3f}", "-movflags", "+faststart"]
    output.parent.mkdir(parents=True, exist_ok=True)
    command.append(str(output))
    subprocess.run(command, check=True)
    return output
