"""
jobs.py — Dispatch and run async jobs (report generation, etc.).

process_job() is called by the Cloud Tasks worker endpoint, or inline as a
fallback when Cloud Tasks is unavailable. It loads the job, marks it running,
runs the work by type, and records the result or error.
"""

import logging

from src.storage import job_store

logger = logging.getLogger(__name__)


async def process_job(job_id: str) -> dict:
    """Run a queued job to completion. Returns the job's final result dict."""
    job = job_store.get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    if job.get("status") == "done":
        return job.get("result") or {}

    job_store.set_running(job_id)
    try:
        result = await _dispatch(job["type"], job.get("params") or {})
        job_store.set_done(job_id, result)
        return result
    except Exception as e:
        logger.exception(f"[job {job_id}] failed")
        job_store.set_error(job_id, str(e))
        raise


async def _dispatch(job_type: str, params: dict) -> dict:
    if job_type == "report":
        from src.agents.orchestrator import orchestrator
        report = await orchestrator.generate_report(
            project_id=params["project_id"],
            transcript_files=params.get("transcript_files") or None,
        )
        return {"report_id": report["report_id"]}

    raise ValueError(f"Unknown job type: {job_type}")
