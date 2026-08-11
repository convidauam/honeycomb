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


def test_game_data_award_badge_adds_it():
    record = GameData('user-1', 'node-1')
    badge = record.award_badge('high-score-100', 'Cien puntos', icon='🏆')
    assert badge.id == 'high-score-100'
    assert badge.title == 'Cien puntos'
    assert badge.icon == '🏆'
    assert len(record.badges) == 1


def test_game_data_award_badge_is_idempotent():
    record = GameData('user-1', 'node-1')
    first = record.award_badge('high-score-100', 'Cien puntos')
    second = record.award_badge('high-score-100', 'Titulo distinto ignorado')
    assert first is second
    assert len(record.badges) == 1
    assert record.badges[0].title == 'Cien puntos'


def test_game_data_award_badge_allows_multiple_different_badges():
    record = GameData('user-1', 'node-1')
    record.award_badge('badge-a', 'A')
    record.award_badge('badge-b', 'B')
    assert {b.id for b in record.badges} == {'badge-a', 'badge-b'}


def test_game_data_to_dict_serializes_badges():
    record = GameData('user-1', 'node-1')
    record.award_badge('high-score-100', 'Cien puntos', icon='🏆')
    data = record.to_dict()
    assert data['badges'] == [{
        'id': 'high-score-100', 'title': 'Cien puntos', 'icon': '🏆',
        'awarded_at': record.badges[0].awarded_at,
    }]


def test_beehive_iter_user_badges_empty_for_new_hive():
    hive = BeeHive()
    assert list(hive.iter_user_badges('user-1')) == []


def test_beehive_iter_user_badges_collects_across_nodes():
    hive = BeeHive()
    record_a = hive.get_game_data('user-1', 'node-a', create=True)
    record_a.award_badge('badge-a', 'A')
    record_b = hive.get_game_data('user-1', 'node-b', create=True)
    record_b.award_badge('badge-b', 'B')
    hive.get_game_data('user-2', 'node-a', create=True).award_badge('other-user-badge', 'X')

    results = list(hive.iter_user_badges('user-1'))
    assert {(nodeid, badge.id) for nodeid, badge in results} == {('node-a', 'badge-a'), ('node-b', 'badge-b')}


def test_beehive_resolve_identity_returns_none_when_unlinked():
    hive = BeeHive()
    assert hive.resolve_identity('password:alice') is None


def test_beehive_link_then_resolve_identity():
    hive = BeeHive()
    hive.link_identity('password:alice', 'local:1234')
    assert hive.resolve_identity('password:alice') == 'local:1234'


def test_beehive_link_identity_overwrites_previous_mapping():
    hive = BeeHive()
    hive.link_identity('password:alice', 'local:1234')
    hive.link_identity('password:alice', 'local:5678')
    assert hive.resolve_identity('password:alice') == 'local:5678'


def test_beehive_unlink_identity_removes_it():
    hive = BeeHive()
    hive.link_identity('password:alice', 'local:1234')
    hive.unlink_identity('password:alice')
    assert hive.resolve_identity('password:alice') is None


def test_beehive_unlink_identity_is_safe_when_absent():
    hive = BeeHive()
    hive.unlink_identity('password:never-linked')


def test_beehive_iter_identities_collects_all_credentials_for_a_userid():
    hive = BeeHive()
    hive.link_identity('password:alice', 'local:1234')
    hive.link_identity('fediverse:https://unam.social/users/alice', 'local:1234')
    hive.link_identity('password:bob', 'local:9999')

    assert set(hive.iter_identities('local:1234')) == {
        'password:alice', 'fediverse:https://unam.social/users/alice',
    }
    assert set(hive.iter_identities('local:9999')) == {'password:bob'}
    assert set(hive.iter_identities('local:nobody')) == set()


def test_merge_game_data_is_noop_for_same_userid():
    hive = BeeHive()
    record = hive.get_game_data('user-1', 'node-a', create=True)
    record.register_interaction()
    hive.merge_game_data('user-1', 'user-1')
    assert hive.get_game_data('user-1', 'node-a').interactions == 1


def test_merge_game_data_is_noop_when_secondary_has_no_data():
    hive = BeeHive()
    hive.get_game_data('into-user', 'node-a', create=True)
    hive.merge_game_data('from-user', 'into-user')
    assert hive.get_game_data('from-user', 'node-a') is None


def test_merge_game_data_copies_node_only_present_in_secondary():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.register_interaction()
    source.merge_stats({'highscore': 10})
    source.award_badge('badge-a', 'A')

    hive.merge_game_data('from-user', 'into-user')

    merged = hive.get_game_data('into-user', 'node-a')
    assert merged is not None
    assert merged.userid == 'into-user'
    assert merged.interactions == 1
    assert merged.stats == {'highscore': 10}
    assert {b.id for b in merged.badges} == {'badge-a'}


def test_merge_game_data_leaves_the_original_bucket_intact():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.register_interaction()

    hive.merge_game_data('from-user', 'into-user')

    original = hive.get_game_data('from-user', 'node-a')
    assert original is not None
    assert original.interactions == 1
    assert original.userid == 'from-user'


def test_merge_game_data_unions_badges_without_duplicating_shared_ones():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.award_badge('shared-badge', 'Compartido')
    source.award_badge('only-in-source', 'Solo en origen')

    target = hive.get_game_data('into-user', 'node-a', create=True)
    target.award_badge('shared-badge', 'Compartido (destino)')
    target_shared_awarded_at = target.badges[0].awarded_at

    hive.merge_game_data('from-user', 'into-user')

    merged = hive.get_game_data('into-user', 'node-a')
    assert {b.id for b in merged.badges} == {'shared-badge', 'only-in-source'}
    # Cuando ambos lados ya tienen el mismo badge_id, gana el que ya tenia
    # into_userid -- no se sobreescribe con la copia de from_userid.
    shared = next(b for b in merged.badges if b.id == 'shared-badge')
    assert shared.title == 'Compartido (destino)'
    assert shared.awarded_at == target_shared_awarded_at


def test_merge_game_data_sums_interactions_when_both_have_the_node():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.register_interaction()
    source.register_interaction()
    target = hive.get_game_data('into-user', 'node-a', create=True)
    target.register_interaction()

    hive.merge_game_data('from-user', 'into-user')

    assert hive.get_game_data('into-user', 'node-a').interactions == 3


def test_merge_game_data_keeps_primary_stats_and_preferences_on_conflict():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.merge_stats({'highscore': 999})
    target = hive.get_game_data('into-user', 'node-a', create=True)
    target.merge_stats({'highscore': 5})

    hive.merge_game_data('from-user', 'into-user')

    assert hive.get_game_data('into-user', 'node-a').stats == {'highscore': 5}


def test_merge_game_data_takes_min_first_seen_and_max_last_seen():
    hive = BeeHive()
    source = hive.get_game_data('from-user', 'node-a', create=True)
    source.first_seen = '2020-01-01T00:00:00+00:00'
    source.last_seen = '2020-01-01T00:00:00+00:00'
    target = hive.get_game_data('into-user', 'node-a', create=True)
    target.first_seen = '2025-01-01T00:00:00+00:00'
    target.last_seen = '2025-06-01T00:00:00+00:00'

    hive.merge_game_data('from-user', 'into-user')

    merged = hive.get_game_data('into-user', 'node-a')
    assert merged.first_seen == '2020-01-01T00:00:00+00:00'
    assert merged.last_seen == '2025-06-01T00:00:00+00:00'


def test_merge_game_data_covers_multiple_nodes_independently():
    hive = BeeHive()
    hive.get_game_data('from-user', 'node-a', create=True).award_badge('a', 'A')
    hive.get_game_data('from-user', 'node-b', create=True).award_badge('b', 'B')
    hive.get_game_data('into-user', 'node-b', create=True).award_badge('existing', 'Existente')

    hive.merge_game_data('from-user', 'into-user')

    assert {b.id for b in hive.get_game_data('into-user', 'node-a').badges} == {'a'}
    assert {b.id for b in hive.get_game_data('into-user', 'node-b').badges} == {'existing', 'b'}
