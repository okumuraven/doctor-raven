from doctor_raven.features.research import store


def test_add_and_list_topics(isolated_db):
    store.add_topic("Rust", description="evaluate")
    topics = store.list_topics()
    assert len(topics) == 1
    assert topics[0].name == "Rust"
    assert topics[0].active is True


def test_deactivate_topic_hides_from_active_only_listing(isolated_db):
    topic = store.add_topic("Old topic")
    assert store.deactivate_topic(topic.id) is True

    assert store.list_topics() == []
    assert len(store.list_topics(active_only=False)) == 1


def test_deactivate_topic_returns_false_for_missing_id(isolated_db):
    assert store.deactivate_topic(999) is False
