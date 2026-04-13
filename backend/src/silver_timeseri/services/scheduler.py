from __future__ import annotations

import logging
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from silver_timeseri.config import get_settings
from silver_timeseri.services.app_service import morning_check_and_sync, sync_incremental


logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_job_lock = Lock()


def _run_job(job_name: str, fn: callable) -> None:
    if not _job_lock.acquire(blocking=False):
        logger.info("Skip scheduler job %s because another sync job is still running.", job_name)
        return

    try:
        logger.info("Starting scheduler job: %s", job_name)
        result = fn()
        logger.info("Finished scheduler job %s with result: %s", job_name, result)
    except Exception:
        logger.exception("Scheduler job %s failed.", job_name)
    finally:
        _job_lock.release()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled by configuration.")
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=settings.scheduler_tzinfo)
    scheduler.add_job(
        lambda: _run_job(
            "incremental_sync",
            lambda: sync_incremental(timeframe="1d", force_refresh=True),
        ),
        trigger=CronTrigger(hour="0,6,12,18,22", minute=0, timezone=settings.scheduler_tzinfo),
        id="silver_sync_every_6h_and_22h",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: _run_job("morning_check", lambda: morning_check_and_sync(timeframe="1d")),
        trigger=CronTrigger(
            hour=settings.scheduler_morning_check_hour,
            minute=0,
            timezone=settings.scheduler_tzinfo,
        ),
        id="silver_morning_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Silver scheduler started in timezone %s with incremental sync at 0,6,12,18,22 and morning check at %02d:00.",
        settings.scheduler_timezone,
        settings.scheduler_morning_check_hour,
    )
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
