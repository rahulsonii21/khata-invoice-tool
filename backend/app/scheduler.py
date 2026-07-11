"""
Runs create_backup() automatically every night at 2 AM server time.
Started once on app startup (see main.py), stopped cleanly on shutdown.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from . import backup

logger = logging.getLogger("uvicorn")

scheduler = BackgroundScheduler()


def _run_nightly_backup():
    try:
        result = backup.create_backup()
        logger.info(f"[auto-backup] created {result['filename']} -> {result['destinations']}")
        if result["errors"]:
            logger.error(f"[auto-backup] some destinations failed: {result['errors']}")
    except Exception as e:
        logger.error(f"[auto-backup] failed: {e}")


def start_scheduler():
    scheduler.add_job(
        _run_nightly_backup,
        trigger="cron",
        hour=2,
        minute=0,
        id="nightly_backup",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)
