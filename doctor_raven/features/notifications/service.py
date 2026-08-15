"""Single entry point for raising a notification: always logs the raw factual event to history
(so status/dashboard lookups stay precise), and — unless a dashboard is already open showing it
live — fires a desktop popup phrased in Doctor Raven's voice rather than a raw template string."""

from doctor_raven.config import Config
from doctor_raven.features.notifications.dashboard_lock import is_dashboard_running
from doctor_raven.features.notifications.store import log_notification
from doctor_raven.features.notifications.voice import phrase_for_popup
from doctor_raven.features.reminders.notifier import notify

POPUP_TITLE = "Doctor Raven"


def notify_and_log(title: str, message: str, *, source: str, config: Config) -> None:
    log_notification(title, message, source)
    if not is_dashboard_running():
        notify(POPUP_TITLE, phrase_for_popup(message, config))
