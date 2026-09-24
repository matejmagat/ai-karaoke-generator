# AI Karaoke Generator

AI Karaoke Generator turns a regular song into an interactive karaoke experience. The app separates the original recording into instrumental and vocal stems, transcribes and aligns the lyrics, and exports timestamped lyrics in SRT format.

The processing pipeline combines **Demucs** for source separation, **WhisperX** for transcription and word-level alignment, and **Genius** lyrics when available to improve transcription accuracy. A **Django** backend manages songs, generated files, user libraries, and playlists, while the **React** frontend provides synchronized playback, timed lyrics, cue navigation, and independent volume controls for the instrumental and guide vocals.

The goal is to let users generate, organize, and perform karaoke tracks from their own audio through one application.
