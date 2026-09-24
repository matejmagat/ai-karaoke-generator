from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobDownloadUrls(BaseModel):
    srt: str
    instrumental: str
    vocals: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    lyrics_source: str | None = None
    download_url: str | None = None
    downloads: JobDownloadUrls | None = None
