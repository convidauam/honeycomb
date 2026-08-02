# Note: the testapp fixture aborts ZODB writes at the end of every single
# request (see conftest.py), so state never carries over between requests
# even within one test. Cross-request persistence (merge, counters) is
# covered at the model level in test_models.py; tests here only assert on
# what a single request/response can prove.


def test_me_requires_auth(testapp):
    testapp.get('/api/v1/me', status=401)


def test_me_returns_authenticated_user(testapp, login_as_fediverse_user):
    fediverse_account = login_as_fediverse_user()
    body = testapp.get('/api/v1/me', status=200).json
    assert body['userid'] == fediverse_account['userid']
    assert set(body.keys()) == {'userid', 'displayname', 'username', 'icon', 'background'}


def test_game_data_requires_auth(testapp):
    testapp.get('/api/v1/sipping/node-x', status=401)
    testapp.post_json('/api/v1/sipping/node-x', {'stats': {}}, status=401)


def test_game_data_get_defaults_when_untouched(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.get('/api/v1/sipping/node-untouched', status=200).json
    assert body['interactions'] == 0
    assert body['stats'] == {}
    assert body['preferences'] == {}


def test_game_data_post_creates_record_and_counts_first_interaction(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.post_json('/api/v1/sipping/node-a', {'stats': {'highscore': 10}}, status=200).json
    assert body['interactions'] == 1
    assert body['stats'] == {'highscore': 10}


def test_game_data_post_ignores_client_supplied_interactions(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.post_json('/api/v1/sipping/node-c', {'interactions': 999, 'stats': {}}, status=200).json
    assert body['interactions'] == 1


def test_game_data_post_accepts_replace_flag(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.post_json('/api/v1/sipping/node-d', {'stats': {'highscore': 20}, 'replace': True}, status=200).json
    assert body['stats'] == {'highscore': 20}


def test_game_data_post_saves_preferences(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.post_json('/api/v1/sipping/node-e', {'preferences': {'difficulty': 'hard'}}, status=200).json
    assert body['preferences'] == {'difficulty': 'hard'}


def test_game_data_post_rejects_non_object_stats(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    testapp.post_json('/api/v1/sipping/node-f', {'stats': 'not-an-object'}, status=400)
