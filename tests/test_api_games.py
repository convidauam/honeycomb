# Note: the testapp fixture aborts ZODB writes at the end of every single
# request (see conftest.py), so state never carries over between requests
# even within one test. Cross-request persistence (merge, counters) is
# covered at the model level in test_models.py; tests here only assert on
# what a single request/response can prove.


def _login(testapp):
    testapp.get('/login', status=303)


def test_me_requires_auth(testapp):
    testapp.get('/api/v1/me', status=401)


def test_me_returns_authenticated_user(testapp):
    _login(testapp)
    body = testapp.get('/api/v1/me', status=200).json
    assert body['userid'] == 'convida@unam.social'
    assert set(body.keys()) == {'userid', 'displayname', 'username', 'icon', 'background'}


def test_game_data_requires_auth(testapp):
    testapp.get('/api/v1/games/node-x/data', status=401)
    testapp.post_json('/api/v1/games/node-x/data', {'stats': {}}, status=401)


def test_game_data_get_defaults_when_untouched(testapp):
    _login(testapp)
    body = testapp.get('/api/v1/games/node-untouched/data', status=200).json
    assert body['interactions'] == 0
    assert body['stats'] == {}
    assert body['preferences'] == {}


def test_game_data_post_creates_record_and_counts_first_interaction(testapp):
    _login(testapp)
    body = testapp.post_json('/api/v1/games/node-a/data', {'stats': {'highscore': 10}}, status=200).json
    assert body['interactions'] == 1
    assert body['stats'] == {'highscore': 10}


def test_game_data_post_ignores_client_supplied_interactions(testapp):
    _login(testapp)
    body = testapp.post_json('/api/v1/games/node-c/data', {'interactions': 999, 'stats': {}}, status=200).json
    assert body['interactions'] == 1


def test_game_data_post_accepts_replace_flag(testapp):
    _login(testapp)
    body = testapp.post_json('/api/v1/games/node-d/data', {'stats': {'highscore': 20}, 'replace': True}, status=200).json
    assert body['stats'] == {'highscore': 20}


def test_game_data_post_saves_preferences(testapp):
    _login(testapp)
    body = testapp.post_json('/api/v1/games/node-e/data', {'preferences': {'difficulty': 'hard'}}, status=200).json
    assert body['preferences'] == {'difficulty': 'hard'}


def test_game_data_post_rejects_non_object_stats(testapp):
    _login(testapp)
    testapp.post_json('/api/v1/games/node-f/data', {'stats': 'not-an-object'}, status=400)
