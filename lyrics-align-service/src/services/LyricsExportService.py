from pathlib import Path

from src.domain.Transcription import Transcription
from src.domain.export.LyricsExportStrategy import LyricsExportStrategy, JsonExportStrategy, SRTExportStrategy


class LyricsExportService:
    """
    Selects exporters and writes their generated content to disk.
    """

    _strategies: dict[str, LyricsExportStrategy] = {
        "srt": SRTExportStrategy(),
        "json": JsonExportStrategy(),
    }

    def export(
        self,
        transcription: Transcription,
        output_path: str | Path,
        strategy: LyricsExportStrategy | None = None,
    ) -> Path:
        """
        Export a transcription and return the final output file path.

        If no strategy is supplied, infer it from output_path's extension:
        - output.srt  -> SRTExportStrategy
        - output.json -> JsonExportStrategy
        """
        path = Path(output_path)

        if strategy is None:
            strategy = self._get_strategy_from_path(path)
        else:
            path = self._ensure_extension(path, strategy.file_extension)

        path.parent.mkdir(parents=True, exist_ok=True)

        exported_content = strategy.export(transcription)
        path.write_text(exported_content, encoding="utf-8")

        return path

    def register_strategy(
        self,
        format_name: str,
        strategy: LyricsExportStrategy,
    ) -> None:
        """
        Register an additional exporter, for example 'vtt' or 'lrc'.
        """
        normalized_name = format_name.lower().lstrip(".")
        self._strategies[normalized_name] = strategy

    def _get_strategy_from_path(self, path: Path) -> LyricsExportStrategy:
        extension = path.suffix.lower().lstrip(".")

        if not extension:
            supported = ", ".join(
                f".{name}" for name in sorted(self._strategies)
            )
            raise ValueError(
                f"Cannot infer export format because '{path.name}' has no extension. "
                f"Use one of: {supported}, or provide a strategy explicitly."
            )

        try:
            return self._strategies[extension]
        except KeyError as exc:
            supported = ", ".join(
                f".{name}" for name in sorted(self._strategies)
            )
            raise ValueError(
                f"Unsupported export format '.{extension}'. "
                f"Supported formats: {supported}."
            ) from exc

    @staticmethod
    def _ensure_extension(path: Path, required_extension: str) -> Path:
        """
        Replace a missing or mismatched extension with the strategy's extension.
        """
        if path.suffix.lower() == required_extension.lower():
            return path

        return path.with_suffix(required_extension)