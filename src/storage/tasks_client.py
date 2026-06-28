"""
tasks_client.py — Enqueue work onto Cloud Tasks.

A task is an HTTP POST back to this service's internal worker endpoint, carrying
the job id and a shared secret. If Cloud Tasks is unavailable (library missing,
API disabled, local dev), enqueue_job() returns False so the caller can fall
back to running the job inline.
"""

import json
import logging
import os

from config.settings import settings

logger = logging.getLogger(__name__)


def enqueue_job(job_id: str) -> bool:
    """Enqueue a Cloud Task that will POST to the internal worker. Returns success."""
    # Only enqueue when running on Cloud Run (K_SERVICE is set there). Locally,
    # the queue would target the prod URL, so fall back to inline execution.
    if not os.environ.get("K_SERVICE"):
        logger.info(f"[job {job_id}] not on Cloud Run — running inline")
        return False

    try:
        from google.cloud import tasks_v2
    except Exception as e:
        logger.warning(f"Cloud Tasks library unavailable: {e}")
        return False

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            settings.gcp_project_id, settings.tasks_location, settings.tasks_queue
        )
        url = f"{settings.service_url.rstrip('/')}/internal/tasks/run-job"
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {
                    "Content-Type": "application/json",
                    "X-Tasks-Secret": settings.tasks_secret,
                },
                "body": json.dumps({"job_id": job_id}).encode(),
            }
        }
        created = client.create_task(parent=parent, task=task)
        logger.info(f"[job {job_id}] enqueued → {created.name}")
        return True
    except Exception as e:
        logger.warning(f"[job {job_id}] Cloud Tasks enqueue failed, will run inline: {e}")
        return False
