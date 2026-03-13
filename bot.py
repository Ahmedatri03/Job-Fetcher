"""Telegram bot — handles inline button callbacks and slash commands."""

from __future__ import annotations

from datetime import datetime, timezone

from telegram import Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN
from database import Database
from utils import setup_logger

logger = setup_logger("bot")


def _fmt_job(i: int, j, show_url: bool = False) -> str:
    """Format a single job for list display."""
    company = j.company if j.company != "N/A" else "?"
    line = f"{i}. {j.title}\n   {company} — {j.location} — {j.score}/100"
    if show_url:
        line += f"\n   {j.url}"
    return line


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Job Fetcher actif.\n\n"
        "Commandes disponibles :\n"
        "  /stats — stats du jour + totaux\n"
        "  /top [N] — top N offres (défaut: 5)\n"
        "  /score <min> — offres au-dessus d'un score\n"
        "  /favorites — offres sauvegardées\n"
        "  /search <mot-clé> — recherche en base\n"
        "  /recent [N] — N dernières offres envoyées"
    )


async def _cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = Database()
    stats = db.get_today_stats()
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    all_rows = db.get_all_jobs(limit=99999)
    total_all = len(all_rows)
    favs = len(db.get_favorites(limit=99999))
    db.close()

    text = (
        f"📊 Stats — {today}\n\n"
        f"Aujourd'hui :\n"
        f"  📥 {stats['total_fetched']} offres en base\n"
        f"  ✅ {stats['sent']} envoyées\n"
        f"  ⭐ Meilleur score : {stats['best_score']}/100\n\n"
        f"Total :\n"
        f"  📦 {total_all} offres en base\n"
        f"  💛 {favs} favorites"
    )
    await update.message.reply_text(text)


async def _cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = 5
    if context.args:
        try:
            n = min(int(context.args[0]), 20)
        except ValueError:
            pass

    db = Database()
    jobs = db.get_top_jobs(n=n)
    db.close()

    if not jobs:
        await update.message.reply_text("Aucune offre en base.")
        return

    lines = [f"🏆 Top {len(jobs)} offres :\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(_fmt_job(i, j, show_url=True))
    await update.message.reply_text("\n".join(lines))


async def _cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage : /score <minimum>\nExemple : /score 60")
        return

    try:
        min_score = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Le score doit être un nombre. Ex : /score 60")
        return

    db = Database()
    total = db.count_jobs_by_min_score(min_score)
    jobs = db.get_jobs_by_min_score(min_score, limit=15)
    db.close()

    if not jobs:
        await update.message.reply_text(f"Aucune offre avec score >= {min_score}.")
        return

    header = f"📊 {total} offres avec score >= {min_score}"
    if total > 15:
        header += " (15 premières)"
    lines = [header + " :\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(_fmt_job(i, j, show_url=True))
    await update.message.reply_text("\n".join(lines))


async def _cmd_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = Database()
    jobs = db.get_favorites(limit=10)
    db.close()

    if not jobs:
        await update.message.reply_text("Aucune offre sauvegardée.")
        return

    lines = ["💛 Offres sauvegardées :\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(_fmt_job(i, j, show_url=True))
    await update.message.reply_text("\n".join(lines))


async def _cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage : /search <mot-clé>\nExemple : /search Python")
        return

    keyword = " ".join(context.args)
    db = Database()
    jobs = db.search_jobs(keyword, limit=10)
    db.close()

    if not jobs:
        await update.message.reply_text(f"Aucun résultat pour « {keyword} ».")
        return

    lines = [f"🔍 {len(jobs)} résultats pour « {keyword} » :\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(_fmt_job(i, j, show_url=True))
    await update.message.reply_text("\n".join(lines))


async def _cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = 5
    if context.args:
        try:
            n = min(int(context.args[0]), 20)
        except ValueError:
            pass

    db = Database()
    jobs = db.get_recent_sent(limit=n)
    db.close()

    if not jobs:
        await update.message.reply_text("Aucune offre envoyée récemment.")
        return

    lines = [f"🕐 {len(jobs)} dernières offres envoyées :\n"]
    for i, j in enumerate(jobs, 1):
        lines.append(_fmt_job(i, j, show_url=True))
    await update.message.reply_text("\n".join(lines))


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action, job_id = data.split(":", 1)
    db = Database()

    if action == "save":
        db.mark_favorited(job_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⭐ Offre sauvegardée !")

    elif action == "ignore":
        db.mark_ignored(job_id)
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_reply_markup(reply_markup=None)

    db.close()


def build_bot_app() -> Application:
    """Build and return the Telegram bot Application (not started)."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("stats", _cmd_stats))
    app.add_handler(CommandHandler("top", _cmd_top))
    app.add_handler(CommandHandler("score", _cmd_score))
    app.add_handler(CommandHandler("favorites", _cmd_favorites))
    app.add_handler(CommandHandler("search", _cmd_search))
    app.add_handler(CommandHandler("recent", _cmd_recent))
    app.add_handler(CallbackQueryHandler(_handle_callback))

    async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error if context else None
        if isinstance(err, Conflict):
            logger.warning(
                "Telegram Conflict: another bot instance is running. "
                "Stop the other instance (other terminal, VM, or Cursor) and restart."
            )
        else:
            logger.exception("Bot error: %s", err)

    app.add_error_handler(_on_error)

    return app


if __name__ == "__main__":
    app = build_bot_app()
    logger.info("Bot started in standalone mode (polling)")
    app.run_polling(drop_pending_updates=True)
