from honeycomb.models import BeeHive, GameData


def test_game_data_defaults():
    record = GameData('user-1', 'node-1')
    assert record.interactions == 0
    assert record.stats == {}
    assert record.preferences == {}
    assert record.badges == []


def test_game_data_register_interaction_increments():
    record = GameData('user-1', 'node-1')
    record.register_interaction()
    record.register_interaction()
    assert record.interactions == 2


def test_game_data_merge_stats_keeps_previous_keys():
    record = GameData('user-1', 'node-1')
    record.merge_stats({'highscore': 10, 'level': 1})
    record.merge_stats({'highscore': 20})
    assert record.stats == {'highscore': 20, 'level': 1}


def test_game_data_merge_stats_replace_clears_previous():
    record = GameData('user-1', 'node-1')
    record.merge_stats({'highscore': 10, 'level': 1})
    record.merge_stats({'highscore': 20}, replace=True)
    assert record.stats == {'highscore': 20}


def test_game_data_to_dict_shape():
    record = GameData('user-1', 'node-1')
    data = record.to_dict()
    assert set(data.keys()) == {
        'userid', 'nodeid', 'interactions', 'stats',
        'preferences', 'badges', 'first_seen', 'last_seen',
    }


def test_beehive_get_game_data_returns_none_without_create():
    hive = BeeHive()
    assert hive.get_game_data('user-1', 'node-1') is None


def test_beehive_get_game_data_creates_and_persists_in_memory():
    hive = BeeHive()
    created = hive.get_game_data('user-1', 'node-1', create=True)
    created.merge_stats({'highscore': 5})

    fetched = hive.get_game_data('user-1', 'node-1')
    assert fetched is created
    assert fetched.stats == {'highscore': 5}


def test_beehive_get_game_data_isolated_per_user_and_node():
    hive = BeeHive()
    a = hive.get_game_data('user-1', 'node-1', create=True)
    b = hive.get_game_data('user-2', 'node-1', create=True)
    c = hive.get_game_data('user-1', 'node-2', create=True)

    a.merge_stats({'highscore': 1})
    assert b.stats == {}
    assert c.stats == {}
