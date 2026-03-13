"""Telegram notifier — sends rich job-offer cards via Telegram Bot API."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from config import JobOffer
from utils import extract_snippet, extract_techs, setup_logger

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_RATE_LIMIT_DELAY = 0.5

_MD2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")


class TelegramNotifier:
    """Send job-offer notifications to a Telegram chat using MarkdownV2."""

    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id
        self._url = _API_URL.format(token=token)
        self._logger = setup_logger("TelegramNotifier")

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        return _MD2_SPECIAL.sub(r"\\\1", text)

    def send_job(self, job: JobOffer) -> bool:
        """Send a single job offer card with inline keyboard. Returns *True* on success."""
        message = self._format_message(job)
        reply_markup = self._build_keyboard(job)
        try:
            return self._post_message(message, reply_markup=reply_markup)
        except Exception as exc:
            self._logger.error("Failed to send job %s: %s", job.id, exc)
            return False

    def send_jobs(self, jobs: list[JobOffer]) -> int:
        """Send multiple jobs with rate limiting. Returns the count of successful sends."""
        sent = 0
        for i, job in enumerate(jobs):
            if self.send_job(job):
                sent += 1
            if i < len(jobs) - 1:
                time.sleep(_RATE_LIMIT_DELAY)
        self._logger.info("Sent %d/%d job notifications", sent, len(jobs))
        return sent

    def send_daily_summary(self, stats: dict[str, int]) -> bool:
        """Send a daily statistics summary message."""
        text = self._format_summary(stats)
        try:
            return self._post_message(text)
        except Exception as exc:
            self._logger.error("Failed to send daily summary: %s", exc)
            return False

    def _format_summary(self, stats: dict[str, int]) -> str:
        total = stats.get("total_fetched", 0)
        after = stats.get("after_filter", 0)
        sent = stats.get("sent", 0)
        best = stats.get("best_score", 0)

        e = self._escape_md
        lines = [
            f"*{e('📊 Résumé du jour')}*",
            "",
            f"{e('📥')} {e(str(total))} {e('offres scannées')}",
            f"{e('🔍')} {e(str(after))} {e('après filtrage')}",
            f"{e('✅')} {e(str(sent))} {e('pertinentes envoyées')}",
            f"{e('⭐ Meilleur score :')} {e(str(best))}{e('/100')}",
        ]
        return "\n".join(lines)

    def _format_message(self, job: JobOffer) -> str:
        """Build a MarkdownV2 card for a single job offer."""
        e = self._escape_md

        title = f"*{e(job.title)}*"

        company = (
            e("Entreprise non communiquée")
            if not job.company or job.company == "N/A"
            else e(job.company)
        )
        location_line = f"🏢 {company} — 📍 {e(job.location)}"

        lines: list[str] = [title, location_line]

        if job.salary and job.salary.strip():
            lines.append(f"💰 {e(job.salary)}")

        if job.remote_type and job.remote_type.strip():
            lines.append(f"🏠 {e(job.remote_type)}")

        techs = extract_techs(job.description)
        if techs:
            techs_str = e(", ".join(techs))
            lines.append(f"🛠 *Technos :* {techs_str}")

        snippet = extract_snippet(job.description)
        if snippet:
            lines.append(f">{e(snippet)}")

        lines.append(f"⭐ {e('Score :')} {e(str(job.score))}{e('/100')}")
        lines.append(f"🔗 [{e('Voir l' + chr(39) + 'offre')}]({e(job.url)})")
        lines.append(f"📡 {e('Source :')} {e(job.source)}")

        return "\n".join(lines)

    @staticmethod
    def _build_keyboard(job: JobOffer) -> dict[str, Any]:
        """Build an inline keyboard with save / ignore / apply buttons."""
        return {
            "inline_keyboard": [[
                {"text": "⭐ Sauvegarder", "callback_data": f"save:{job.id}"},
                {"text": "❌ Ignorer", "callback_data": f"ignore:{job.id}"},
                {"text": "🔗 Postuler", "url": job.url},
            ]]
        }

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1), reraise=True)
    def _post_message(
        self,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """POST the message to the Telegram API with one automatic retry."""
        payload: dict[str, Any] = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = json.dumps(reply_markup)

        resp = requests.post(self._url, json=payload, timeout=10)

        if resp.status_code == 200 and resp.json().get("ok"):
            return True

        self._logger.warning(
            "Telegram API responded %d: %s", resp.status_code, resp.text
        )
        return False
