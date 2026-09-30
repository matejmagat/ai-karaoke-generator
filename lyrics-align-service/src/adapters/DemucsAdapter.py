import subprocess
import sys
from pathlib import Path
from src.domain.SourceSeparationResult import SourceSeparationResult


class DemucsAdapter:
    def __init__(self, source_path,
                 output_dir,
                 demucs_model,
                 ):
        self.source_path = Path(source_path)
        self.output_root = Path(output_dir) / "separated"
        self.demucs_model = demucs_model

        self.command = [
            sys.executable, "-m", "demucs",
            "-n", demucs_model,
            "--two-stems", "vocals",
            "-o", str(self.output_root),
            str(self.source_path),
        ]

    def run(self) -> SourceSeparationResult:
        print("Running:", " ".join(self.command))
        subprocess.run(self.command, check=True)
        source_path = str(self.source_path)
        vocals_path = str(self._get_stem_path("vocals"))
        instrumental_path = str(self._get_stem_path("no_vocals"))
        result = SourceSeparationResult(
            source_path,
            vocals_path,
            instrumental_path
        )
        return result


    def _get_stem_path(self, stem:str):
        output_stem = self.output_root / self.demucs_model / self.source_path.stem / f"{stem}.wav"
        if not output_stem.is_file():
            candidates = list(self.output_root.rglob(f"{stem}.wav"))
            if len(candidates) != 1:
                raise FileNotFoundError(f"Could not uniquely locate the Demucs {stem} stem.")
            output_stem = candidates[0]

        return output_stem
