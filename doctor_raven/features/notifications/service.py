"""Single entry point for raising a notification: always logs the raw factual event to history
(so status/dashboard lookups stay precise), and — unless a dashboard is already open showing it
live — fires a desktop popup phrased in Doctor Raven's voice rather than a raw template string.
Also posts to Discord (if configured) whether or not the dashboard is open — the dashboard-open
suppression exists to avoid a redundant *local* popup when you're already looking at the screen,
but that reasoning doesn't apply to a remote channel you might check from your phone."""

from doctor_raven.config import Config
from doctor_raven.features.notifications import discord_client
from doctor_raven.features.notifications.dashboard_lock import is_dashboard_running
from doctor_raven.features.notifications.store import log_notification
from doctor_raven.features.notifications.voice import phrase_for_popup
from doctor_raven.features.reminders.notifier import notify

POPUP_TITLE = "Doctor Raven"


def send_discord(config: Config, content: str) -> None:
    """Best-effort — a Discord posting failure must never break the caller's flow, since the
    desktop notification (or terminal output, for the digest) has already happened regardless."""
    if not config.discord_webhook_url:
        return
    try:
        discord_client.send_message(config.discord_webhook_url, content)
    except discord_client.DiscordUnavailable:
        pass


def notify_and_log(title: str, message: str, *, source: str, config: Config) -> None:
    log_notification(title, message, source)
    if not is_dashboard_running():
        notify(POPUP_TITLE, phrase_for_popup(message, config))
    send_discord(config, f"**{title}**\n{message}")
