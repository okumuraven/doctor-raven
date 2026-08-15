import contextlib
from pathlib import Path

import pytest

from doctor_raven.core import db as db_module
from doctor_raven.features.daemon import vuln_tracker
from doctor_raven.features.notifications import store as notifications_store
from doctor_raven.features.reminders import store as reminders_store
from doctor_raven.features.research import store as research_store
from doctor_raven.features.schedule import store as schedule_store


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirects every store module's get_conn() to a throwaway sqlite file, and stops
    init_db() from touching the real ~/.local/share/doctor-raven.

    Each store module did `from doctor_raven.core.db import get_conn`, which binds its
    own independent name at import time — patching db_module.get_conn (or its __defaults__,
    which a @contextmanager wrapper doesn't even expose) never reaches these call sites.
    The three names must each be patched directly in the module that actually calls them."""
    test_db_path = tmp_path / "raven-test.db"

    @contextlib.contextmanager
    def fake_get_conn(db_path: Path = test_db_path):
        with db_module.get_conn(db_path) as conn:
            yield conn

    monkeypatch.setattr(db_module, "ensure_data_dir", lambda: tmp_path)
    monkeypatch.setattr(schedule_store, "get_conn", fake_get_conn)
    monkeypatch.setattr(reminders_store, "get_conn", fake_get_conn)
    monkeypatch.setattr(research_store, "get_conn", fake_get_conn)
    monkeypatch.setattr(notifications_store, "get_conn", fake_get_conn)
    monkeypatch.setattr(vuln_tracker, "get_conn", fake_get_conn)
    return test_db_path
