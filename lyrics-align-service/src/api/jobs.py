from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


from src.api.schemas import JobStatus

@dataclass
class Job:
    job_id: str
    status: JobStatus
    work_dir: Path
    created_at: datetime
    completed_at: datetime | None = None
    output_path: Path | None = None
    error: str | None = None


class JobStore:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self) -> Job:
        job_id = str(uuid4())
        work_dir = self.root_dir / job_id
        work_dir.mkdir(parents=True, exist_ok=False)

        job = Job(
            job_id=job_id,
            status=JobStatus.queued,
            work_dir=work_dir,
            created_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self._jobs[job_id] = job

        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_processing(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id].status = JobStatus.processing

    def set_completed(self, job_id: str, output_path: Path) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.completed
            job.output_path = output_path
            job.completed_at = datetime.now(timezone.utc)

    def set_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.failed
            job.error = error
            job.completed_at = datetime.now(timezone.utc)