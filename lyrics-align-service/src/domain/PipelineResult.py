from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineResult:
    srt_path: Path
    instrumental_path: Path
    vocals_path: Path
