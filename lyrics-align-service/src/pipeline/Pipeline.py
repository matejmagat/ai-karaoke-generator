# src/Pipeline.py
import logging
from pathlib import Path

from src.adapters.DemucsAdapter import DemucsAdapter
from src.adapters.GeniusLyricsAdapter import GeniusLyricsAdapter
from src.adapters.WhisperXAdapter import WhisperXAdapter
from src.config import load_settings
from src.domain.export.LyricsExportStrategy import SRTExportStrategy
from src.domain.normalization.LyricsNormalizationStrategy import (
    RemoveBracketedAnnotationsStrategy,
)
from src.domain.PipelineResult import PipelineResult
from src.domain.SongMetadata import SongMetadata
from src.services.GeniusLyricsNormalizer import GeniusLyricsNormalizer
from src.services.LyricsCorrector import LyricsCorrector
from src.services.LyricsExportService import LyricsExportService

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        title: str,
        artist: str,
        language: str,
        source_path: str | Path,
        output_dir: str | Path,
    ):
        self.title = title.strip()
        self.artist = artist.strip()
        self.language = language
        self.source_path = Path(source_path)
        self.output_dir = Path(output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.settings = load_settings()

        self.demucs = DemucsAdapter(
            source_path=self.source_path,
            output_dir=self.output_dir,
            demucs_model="htdemucs",
        )

        self.whisper = WhisperXAdapter(
            model_name="medium",
            language=self.language,
            batch_size=128,
        )

        self.genius = GeniusLyricsAdapter(
            access_token=self.settings.genius_access_token,
            timeout_seconds=self.settings.genius_timeout_seconds,
            retries=self.settings.genius_retries,
            sleep_time_seconds=self.settings.genius_sleep_time_seconds,
        )

    def forward(self) -> PipelineResult:
        logger.info("Starting Demucs separation for %s — %s", self.artist, self.title)

        demucs_result = self.demucs.run()

        logger.info("Starting WhisperX transcription")
        whisper_result = self.whisper.transcribe(demucs_result.vocals_path)

        logger.info("Searching Genius lyrics")
        lyrics = self.genius.find_lyrics(
            SongMetadata(
                title=self.title,
                artist=self.artist,
            )
        )

        if lyrics is None:
            logger.info("No Genius lyrics found; using WhisperX transcription.")
            final = whisper_result
        else:
            normalizer = GeniusLyricsNormalizer(
                [RemoveBracketedAnnotationsStrategy()]
            )
            normalized_result = normalizer.normalize(lyrics)

            corrector = LyricsCorrector(adlib_policy="keep")
            final = corrector.correct(
                whisper_result,
                normalized_result.normalized_text,
            )

            logger.info(
                "Lyrics correction finished; corrections: %s",
                final.corrections,
            )

        logger.info("Starting WhisperX alignment")
        aligned = self.whisper.align(
            demucs_result.vocals_path,
            final.transcription,
        )

        output_path = self.output_dir / "lyrics.srt"

        export_service = LyricsExportService()
        export_service.export(
            aligned,
            str(output_path),
            SRTExportStrategy(),
        )

        logger.info("SRT exported to %s", output_path)

        return PipelineResult(
            srt_path=output_path,
            instrumental_path=Path(demucs_result.instrumental_path),
            vocals_path=Path(demucs_result.vocals_path),
        )


if __name__ == "__main__":
    title = "on tha line"
    artist = "yeat"
    language = "en"
    source_path = "../../testing/input/on tha line.mp3"
    output_dir = "../../testing/output"

    pipeline = Pipeline(title, artist, language, source_path, output_dir)
    pipeline.forward()
