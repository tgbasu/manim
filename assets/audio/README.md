# Audio assets

Record narration as WAV or MP3, named after the scene class (`LinearReel.wav`,
`PredictionPipeline.mp3`). Pass `--audio-dir assets/audio` to include recordings.
Each selected scene must have a matching file. Silent exports are the default.

Use `--voiceover path/to/recording.wav` for one selected scene and
`--music path/to/music.mp3` for a quiet looping music track. Audio files are
ignored by Git. Commit scripts under `projects/<name>/scripts/`.
