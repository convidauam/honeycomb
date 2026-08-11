# Nota: igual que en test_api_games.py, cada request de `testapp` corre en su
# propia transaccion que se aborta al final (ver conftest.py), asi que las
# pruebas que necesitan que un logro otorgado en un request exista en el
# siguiente usan el fixture `game_data_bridge` (mismo patron que fediverse_stub
# usa para usuarios). Lo que no lo necesita solo prueba lo que un unico
# request/response puede demostrar.


def test_badges_requires_auth(testapp):
    testapp.post_json('/api/v1/sipping/node-x/badges', {'id': 'a', 'title': 'A'}, status=401)


def test_award_badge_creates_it(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.post_json('/api/v1/sipping/node-a/badges', {
        'id': 'high-score-100', 'title': 'Cien puntos', 'icon': '🏆',
    }, status=200).json
    assert body['badges'] == [{
        'id': 'high-score-100', 'title': 'Cien puntos', 'icon': '🏆',
        'awarded_at': body['badges'][0]['awarded_at'],
    }]


def test_award_badge_rejects_missing_id(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'title': 'Sin id'}, status=400)


def test_award_badge_rejects_missing_title(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'x'}, status=400)


def test_award_badge_rejects_non_string_icon(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'x', 'title': 'X', 'icon': 123}, status=400)


def test_achievements_requires_auth(testapp):
    testapp.get('/api/v1/achievements', status=401)


def test_achievements_empty_when_no_badges(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.get('/api/v1/achievements', status=200).json
    assert body['achievements'] == []


def test_share_requires_auth(testapp):
    testapp.post_json('/api/v1/share', {'nodeid': 'a', 'badge_id': 'b'}, status=401)


def test_share_rejects_missing_fields(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/share', {}, status=400)


def test_share_404_when_badge_was_never_awarded(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/share', {'nodeid': 'node-a', 'badge_id': 'never-awarded'}, status=404)


def test_share_publishes_awarded_badge_to_the_fediverse(testapp, login_as_fediverse_user, game_data_bridge, monkeypatch):
    from honeycomb.security import activitypub

    calls = []

    def fake_publish_note(outbox_url, access_token, content, to_public=True):
        calls.append((outbox_url, access_token, content))
        return {'id': 'https://fake.fediverse.test/activities/1'}

    monkeypatch.setattr(activitypub, 'publish_note', fake_publish_note)

    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'high-score-100', 'title': 'Cien puntos'}, status=200)

    body = testapp.post_json('/api/v1/share', {'nodeid': 'node-a', 'badge_id': 'high-score-100'}, status=200).json
    assert body['status'] == 'ok'
    assert body['activity'] == {'id': 'https://fake.fediverse.test/activities/1'}

    assert len(calls) == 1
    outbox_url, access_token, content = calls[0]
    assert outbox_url == 'https://fake.fediverse.test/users/tester/outbox'
    assert access_token == 'fake-access-token'
    assert 'Cien puntos' in content


def test_share_uses_custom_message_when_given(testapp, login_as_fediverse_user, game_data_bridge, monkeypatch):
    from honeycomb.security import activitypub

    calls = []
    monkeypatch.setattr(
        activitypub, 'publish_note',
        lambda outbox_url, access_token, content, to_public=True: calls.append(content) or {'id': 'x'},
    )

    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'badge-x', 'title': 'X'}, status=200)
    testapp.post_json('/api/v1/share', {
        'nodeid': 'node-a', 'badge_id': 'badge-x', 'message': 'Mensaje personalizado!',
    }, status=200)

    assert calls == ['Mensaje personalizado!']


def test_share_returns_400_without_encryption_key_configured(testapp, login_as_fediverse_user, game_data_bridge, monkeypatch):
    monkeypatch.setitem(testapp.app.registry.settings, 'honeycomb.token_encryption_key', '')

    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'badge-x', 'title': 'X'}, status=200)
    testapp.post_json('/api/v1/share', {'nodeid': 'node-a', 'badge_id': 'badge-x'}, status=400)


def test_share_returns_502_when_the_instance_rejects_the_post(testapp, login_as_fediverse_user, game_data_bridge, monkeypatch):
    from honeycomb.security import activitypub, fediverse

    def failing_publish(outbox_url, access_token, content, to_public=True):
        raise fediverse.FediverseError('la instancia rechazo la publicacion')

    monkeypatch.setattr(activitypub, 'publish_note', failing_publish)

    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'badge-x', 'title': 'X'}, status=200)
    testapp.post_json('/api/v1/share', {'nodeid': 'node-a', 'badge_id': 'badge-x'}, status=502)


def test_share_returns_a_distinct_error_for_accounts_without_a_fediverse_identity(
    testapp, register_as_local_user, game_data_bridge,
):
    """Una cuenta local pura (sin Fediverso vinculado) debe recibir un error que
    invite a vincular, distinto del que invita a volver a iniciar sesion."""
    register_as_local_user('alice', 'correct horse battery staple')
    testapp.post_json('/api/v1/sipping/node-a/badges', {'id': 'badge-x', 'title': 'X'}, status=200)

    body = testapp.post_json('/api/v1/share', {'nodeid': 'node-a', 'badge_id': 'badge-x'}, status=400).json
    assert 'vincula' in body['error']
