"""Main orchestrator — fetches jobs, scores, deduplicates, notifies, and runs the bot."""

from __future__ import annotations

import argparse
import sys
import threading

from config import (
    FETCH_INTERVAL_HOURS,
    LOG_LEVEL,
    SCORE_THRESHOLD,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from database import Database
from fetchers import FranceTravailFetcher
from notifier import TelegramNotifier
from scoring import KeywordScorer, filter_offers
from utils import setup_logger


def run_pipeline() -> dict:
    """Execute one full pipeline run. Returns stats dict."""
    logger = setup_logger("main", LOG_LEVEL)
    logger.info("=== Starting job fetch pipeline ===")

    db = Database()
    scorer = KeywordScorer()
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

    fetchers = [
        FranceTravailFetcher(),
    ]

    all_jobs = []
    for fetcher in fetchers:
        try:
            jobs = fetcher.fetch()
            logger.info("[%s] %d offres récupérées", fetcher.name, len(jobs))
            all_jobs.extend(jobs)
        except Exception as exc:
            logger.error("[%s] Erreur: %s", fetcher.name, exc)

    logger.info("Total brut: %d offres", len(all_jobs))

    filtered_jobs = filter_offers(all_jobs)
    logger.info("Après filtrage: %d offres", len(filtered_jobs))

    for job in filtered_jobs:
        job.score = scorer.score(job)

    new_jobs: list = []
    for job in filtered_jobs:
        if db.insert_job(job):
            new_jobs.append(job)

    logger.info("Nouvelles offres: %d", len(new_jobs))

    sent_count = 0
    good_jobs = [j for j in new_jobs if j.score >= SCORE_THRESHOLD]
    good_jobs.sort(key=lambda j: j.score, reverse=True)

    if good_jobs:
        sent_count = notifier.send_jobs(good_jobs)
        for job in good_jobs[:sent_count]:
            db.mark_sent(job.id)
        logger.info("Envoyées sur Telegram: %d/%d", sent_count, len(good_jobs))
    else:
        logger.info("Aucune nouvelle offre pertinente à envoyer")

    db.close()
    logger.info("=== Pipeline terminé ===")

    return {
        "total_fetched": len(all_jobs),
        "after_filter": len(filtered_jobs),
        "sent": sent_count,
        "best_score": max((j.score for j in filtered_jobs), default=0),
    }


def send_summary() -> None:
    """Send daily summary via Telegram."""
    logger = setup_logger("summary", LOG_LEVEL)
    db = Database()
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    stats = db.get_today_stats()
    notifier.send_daily_summary(stats)
    db.close()
    logger.info("Daily summary sent")


def main() -> None:
    """Entry point — supports ``--once`` for a single run."""
    parser = argparse.ArgumentParser(description="Job Fetcher & CV Matching Tool")
    parser.add_argument(
        "--once", action="store_true",
        help="Run the pipeline once then exit (no scheduler, no bot)",
    )
    parser.add_argument(
        "--bot-only", action="store_true",
        help="Run only the Telegram bot (no pipeline, no scheduler)",
    )
    args = parser.parse_args()

    logger = setup_logger("scheduler", LOG_LEVEL)

    if args.bot_only:
        from bot import build_bot_app
        logger.info("Starting bot in standalone mode")
        app = build_bot_app()
        app.run_polling(drop_pending_updates=True)
        return

    run_pipeline()

    if args.once:
        logger.info("Single run completed (--once flag)")
        sys.exit(0)

    from apscheduler.schedulers.background import BackgroundScheduler
    from bot import build_bot_app

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_pipeline, "interval", hours=FETCH_INTERVAL_HOURS)
    scheduler.add_job(send_summary, "cron", hour=20, minute=0)
    scheduler.start()

    logger.info(
        "Scheduler started — pipeline every %dh, summary at 20:00",
        FETCH_INTERVAL_HOURS,
    )

    app = build_bot_app()
    logger.info("Bot polling started — listening for commands and button clicks")

    try:
        app.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
