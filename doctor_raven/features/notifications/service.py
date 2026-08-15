"""Single entry point for raising a notification: always logs it to history, and fires
the desktop popup unless a dashboard is already open showing it live."""

from doctor_raven.features.notifications.dashboard_lock import is_dashboard_running
from doctor_raven.features.notifications.store import log_notification
from doctor_raven.features.reminders.notifier import notify


def notify_and_log(title: str, message: str, source: str) -> None:
    log_notification(title, message, source)
    if not is_dashboard_running():
        notify(title, message)
