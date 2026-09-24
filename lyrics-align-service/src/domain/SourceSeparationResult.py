from dataclasses import dataclass

@dataclass
class SourceSeparationResult:
    source_path: str
    vocals_path: str
    instrumental_path: str