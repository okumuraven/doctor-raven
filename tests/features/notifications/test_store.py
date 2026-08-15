from doctor_raven.features.notifications import store


def test_log_notification_persists_and_lists_newest_first(isolated_db):
    store.log_notification("First", "msg 1", source="reminder")
    store.log_notification("Second", "msg 2", source="system_health")

    recent = store.list_recent()
    assert [e.title for e in recent] == ["Second", "First"]
    assert recent[0].source == "system_health"


def test_list_recent_respects_limit(isolated_db):
    for i in range(5):
        store.log_notification(f"Title {i}", f"msg {i}", source="test")

    assert len(store.list_recent(limit=2)) == 2
