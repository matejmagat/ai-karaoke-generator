import asyncio
import logging
import shutil
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from src.api.jobs import Job, JobStore
from src.api.schemas import (
    JobCreatedResponse,
    JobDownloadUrls,
    JobStatus,
    JobStatusResponse,
)
from src.pipeline.Pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RUNTIME_DIR = Path("runtime")
JOBS_DIR = RUNTIME_DIR / "jobs"
pipeline_semaphore = asyncio.Semaphore(1)
job_store = JobStore(JOBS_DIR)
app = FastAPI(title="Lyrics Alignment API", version="0.2.0")
ArtifactName = Literal["srt", "instrumental", "vocals"]


def allowed_extension(filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    allowed = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
    if extension not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio extension. Allowed: {', '.join(sorted(allowed))}",
        )
    return extension


async def save_upload(upload: UploadFile, destination: Path) -> None:
    chunk_size = 1024 * 1024
    with destination.open("wb") as output_file:
        while chunk := await upload.read(chunk_size):
            output_file.write(chunk)
    await upload.close()


def execute_pipeline(
    job_id: str,
    title: str,
    artist: str,
    language: str,
    input_path: Path,
    output_dir: Path,
) -> None:
    job_store.set_processing(job_id)
    pipeline = None
    try:
        pipeline = Pipeline(
            title=title,
            artist=artist,
            language=language,
            source_path=input_path,
            output_dir=output_dir,
        )
        result = pipeline.forward()
        job_store.set_completed(
            job_id,
            srt_path=result.srt_path,
            instrumental_path=result.instrumental_path,
            vocals_path=result.vocals_path,
        )
    except Exception:
        logger.exception("Pipeline failed for job %s", job_id)
        job_store.set_failed(
            job_id,
            "Processing failed. Check server logs for details.",
        )
    finally:
        if pipeline is not None:
            pipeline.close()


def get_completed_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The job has not completed yet.",
        )
    return job


def build_artifact_response(job_id: str, artifact: ArtifactName) -> FileResponse:
    job = get_completed_job(job_id)
    artifacts = {
        "srt": (job.srt_path, "application/x-subrip", f"{job_id}.srt"),
        "instrumental": (
            job.instrumental_path,
            "audio/wav",
            f"{job_id}-instrumental.wav",
        ),
        "vocals": (job.vocals_path, "audio/wav", f"{job_id}-vocals.wav"),
    }
    artifact_path, media_type, filename = artifacts[artifact]
    if artifact_path is None or not artifact_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{artifact.capitalize()} file is no longer available.",
        )
    return FileResponse(
        path=artifact_path,
        media_type=media_type,
        filename=filename,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/jobs",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_job(
    title: str = Form(..., min_length=1, max_length=250),
    artist: str = Form(..., min_length=1, max_length=250),
    language: str = Form(..., min_length=2, max_length=10),
    audio: UploadFile = File(...),
) -> JobCreatedResponse:
    extension = allowed_extension(audio.filename)
    job = job_store.create()
    input_path = job.work_dir / f"input{extension}"
    output_dir = job.work_dir / "output"
    try:
        await save_upload(audio, input_path)
    except Exception:
        shutil.rmtree(job.work_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not save uploaded audio.",
        )

    async def run_job() -> None:
        async with pipeline_semaphore:
            await asyncio.to_thread(
                execute_pipeline,
                job.job_id,
                title,
                artist,
                language,
                input_path,
                output_dir,
            )

    asyncio.create_task(run_job())
    return JobCreatedResponse(job_id=job.job_id, status=JobStatus.queued)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    download_url = None
    downloads = None
    if job.status == JobStatus.completed:
        download_url = f"/jobs/{job.job_id}/download"
        downloads = JobDownloadUrls(
            srt=f"/jobs/{job.job_id}/download/srt",
            instrumental=f"/jobs/{job.job_id}/download/instrumental",
            vocals=f"/jobs/{job.job_id}/download/vocals",
        )
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
        download_url=download_url,
        downloads=downloads,
    )


@app.get(
    "/jobs/{job_id}/download",
    response_class=FileResponse,
    responses={200: {"content": {"application/x-subrip": {}}}},
)
def download_srt(job_id: str) -> FileResponse:
    return build_artifact_response(job_id, "srt")


@app.get(
    "/jobs/{job_id}/download/{artifact}",
    response_class=FileResponse,
    responses={
        200: {
            "content": {
                "application/x-subrip": {},
                "audio/wav": {},
            }
        }
    },
)
def download_artifact(job_id: str, artifact: ArtifactName) -> FileResponse:
    return build_artifact_response(job_id, artifact)
