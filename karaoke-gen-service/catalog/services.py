import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from tempfile import SpooledTemporaryFile
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.files import File
from django.db import close_old_connections, transaction
from django.db.models import Max

from library.models import Library, LibrarySong

from .models import Song

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="song-import")


class LyricsAlignServiceError(Exception):
    pass


class LyricsAlignClient:
    def __init__(self):
        self.base_url = settings.LYRICS_ALIGN_SERVICE_URL.rstrip("/")
        self.request_timeout = settings.LYRICS_ALIGN_REQUEST_TIMEOUT_SECONDS
        self.job_timeout = settings.LYRICS_ALIGN_JOB_TIMEOUT_SECONDS
        self.poll_interval = settings.LYRICS_ALIGN_POLL_INTERVAL_SECONDS

    def create_job(self, *, title, artist, language, audio):
        try:
            audio.seek(0)
            response = requests.post(
                f"{self.base_url}/jobs",
                data={"title": title, "artist": artist, "language": language},
                files={
                    "audio": (
                        audio.name,
                        audio,
                        getattr(audio, "content_type", "application/octet-stream"),
                    )
                },
                timeout=self.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["job_id"], payload["status"]
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise LyricsAlignServiceError(
                "Could not create a lyrics alignment job."
            ) from exc

    def wait_for_completion(self, job_id):
        deadline = time.monotonic() + self.job_timeout

        while time.monotonic() < deadline:
            try:
                response = requests.get(
                    f"{self.base_url}/jobs/{job_id}",
                    timeout=self.request_timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise LyricsAlignServiceError(
                    f"Could not read lyrics alignment job {job_id}."
                ) from exc

            job_status = payload.get("status")
            if job_status == "failed":
                raise LyricsAlignServiceError(
                    payload.get("error") or f"Lyrics alignment job {job_id} failed."
                )
            if job_status == "completed":
                downloads = payload.get("downloads") or {}
                defaults = {
                    artifact: f"/jobs/{job_id}/download/{artifact}"
                    for artifact in ("srt", "instrumental", "vocals")
                }
                return {key: downloads.get(key, value) for key, value in defaults.items()}

            time.sleep(self.poll_interval)

        raise LyricsAlignServiceError(
            f"Lyrics alignment job {job_id} did not finish before the timeout."
        )

    def download_artifact(self, download_url):
        url = urljoin(f"{self.base_url}/", download_url.lstrip("/"))
        try:
            response = requests.get(url, stream=True, timeout=self.request_timeout)
            response.raise_for_status()
            output = SpooledTemporaryFile(max_size=10 * 1024 * 1024)
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
            output.seek(0)
            return output
        except requests.RequestException as exc:
            raise LyricsAlignServiceError(
                f"Could not download generated artifact from {url}."
            ) from exc


def complete_song_import(*, job_id, title, artist, user_id):
    close_old_connections()
    client = LyricsAlignClient()
    downloads = client.wait_for_completion(job_id)
    saved_files = []

    try:
        with ExitStack() as stack:
            artifacts = {}
            for artifact in ("srt", "instrumental", "vocals"):
                stream = client.download_artifact(downloads[artifact])
                stack.callback(stream.close)
                artifacts[artifact] = stream

            with transaction.atomic():
                song = Song(
                    title=title,
                    artist=artist,
                    uploaded_by_id=user_id,
                    processing_status=Song.ProcessingStatus.READY,
                )
                song.lyrics_srt_file.save(
                    "lyrics.srt", File(artifacts["srt"]), save=False
                )
                saved_files.append((song.lyrics_srt_file.storage, song.lyrics_srt_file.name))
                song.instrumental_file.save(
                    "instrumental.wav", File(artifacts["instrumental"]), save=False
                )
                saved_files.append(
                    (song.instrumental_file.storage, song.instrumental_file.name)
                )
                song.vocals_file.save(
                    "vocals.wav", File(artifacts["vocals"]), save=False
                )
                saved_files.append((song.vocals_file.storage, song.vocals_file.name))
                song.save()

                library, _ = Library.objects.get_or_create(
                    owner_id=user_id,
                    name="My Library",
                )
                library = Library.objects.select_for_update().get(pk=library.pk)
                maximum = library.librarysong_set.aggregate(Max("position"))[
                    "position__max"
                ]
                LibrarySong.objects.create(
                    library=library,
                    song=song,
                    position=(maximum or 0) + 1,
                )
                return song
    except Exception:
        for storage, name in saved_files:
            storage.delete(name)
        raise
    finally:
        close_old_connections()


def _run_song_import(**kwargs):
    try:
        complete_song_import(**kwargs)
    except Exception:
        logger.exception("Could not import completed lyrics job %s", kwargs["job_id"])


def enqueue_song_import(**kwargs):
    return _executor.submit(_run_song_import, **kwargs)
