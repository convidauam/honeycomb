import pytest

from honeycomb.security import activitypub, fediverse


class _FakeJSONResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.is_redirect = False
        self.is_permanent_redirect = False

    def json(self):
        return self._payload


def _stub_request(monkeypatch, response):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured['method'] = method
        captured['url'] = url
        captured['kwargs'] = kwargs
        return response

    monkeypatch.setattr(fediverse.requests, 'request', fake_request)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)
    return captured


OUTBOX = 'https://example.social/users/tester/outbox'


def test_publish_note_sends_authenticated_create_request(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(201, {'id': 'https://example.social/activities/1'}))
    result = activitypub.publish_note(OUTBOX, 'tok123', 'Logre algo!')
    assert captured['method'] == 'POST'
    assert captured['url'] == OUTBOX
    assert captured['kwargs']['headers']['Authorization'] == 'Bearer tok123'
    assert captured['kwargs']['headers']['Content-Type'] == activitypub.C2S_CONTENT_TYPE
    note = captured['kwargs']['json']
    assert note['type'] == 'Note'
    assert note['content'] == 'Logre algo!'
    assert note['to'] == ['https://www.w3.org/ns/activitystreams#Public']
    assert result == {'id': 'https://example.social/activities/1'}


def test_publish_note_not_public_omits_to_field(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(201, {}))
    activitypub.publish_note(OUTBOX, 'tok123', 'privado', to_public=False)
    assert 'to' not in captured['kwargs']['json']


def test_publish_note_requires_outbox_url():
    with pytest.raises(fediverse.FediverseError):
        activitypub.publish_note(None, 'tok123', 'hola')


def test_publish_note_requires_access_token():
    with pytest.raises(fediverse.FediverseError):
        activitypub.publish_note(OUTBOX, None, 'hola')


def test_publish_note_raises_on_error_status(monkeypatch):
    _stub_request(monkeypatch, _FakeJSONResponse(403, {'error': 'forbidden'}))
    with pytest.raises(fediverse.FediverseError):
        activitypub.publish_note(OUTBOX, 'tok123', 'hola')


def test_publish_note_raises_on_network_error(monkeypatch):
    def fail(*a, **k):
        raise fediverse.requests.RequestException('boom')
    monkeypatch.setattr(fediverse.requests, 'request', fail)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)
    with pytest.raises(fediverse.FediverseError):
        activitypub.publish_note(OUTBOX, 'tok123', 'hola')


def test_read_outbox_returns_collection_with_direct_items(monkeypatch):
    collection = {'type': 'OrderedCollection', 'orderedItems': [{'type': 'Note', 'content': 'hola'}]}
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, collection))
    result = activitypub.read_outbox(OUTBOX)
    assert result == collection
    assert captured['url'] == OUTBOX
    assert 'Authorization' not in captured['kwargs']['headers']


def test_read_outbox_includes_bearer_when_token_given(monkeypatch):
    _stub_request(monkeypatch, _FakeJSONResponse(200, {'orderedItems': []}))
    activitypub.read_outbox(OUTBOX, access_token='tok123')


def test_read_outbox_follows_first_page_when_summary_only(monkeypatch):
    first_page_url = OUTBOX + '?page=true'
    responses = {
        OUTBOX: _FakeJSONResponse(200, {'type': 'OrderedCollection', 'first': first_page_url}),
        first_page_url: _FakeJSONResponse(200, {'type': 'OrderedCollectionPage', 'orderedItems': [{'content': 'hi'}]}),
    }

    def fake_request(method, url, **kwargs):
        return responses[url]

    monkeypatch.setattr(fediverse.requests, 'request', fake_request)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)

    result = activitypub.read_outbox(OUTBOX)
    assert result['orderedItems'] == [{'content': 'hi'}]


def test_read_outbox_follows_first_page_given_as_object_with_id(monkeypatch):
    first_page_url = OUTBOX + '?page=true'
    responses = {
        OUTBOX: _FakeJSONResponse(200, {'first': {'id': first_page_url}}),
        first_page_url: _FakeJSONResponse(200, {'orderedItems': []}),
    }

    def fake_request(method, url, **kwargs):
        return responses[url]

    monkeypatch.setattr(fediverse.requests, 'request', fake_request)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)

    result = activitypub.read_outbox(OUTBOX)
    assert result == {'orderedItems': []}


def test_read_outbox_requires_outbox_url():
    with pytest.raises(fediverse.FediverseError):
        activitypub.read_outbox(None)


def test_read_outbox_raises_on_error_status(monkeypatch):
    _stub_request(monkeypatch, _FakeJSONResponse(404, {}))
    with pytest.raises(fediverse.FediverseError):
        activitypub.read_outbox(OUTBOX)


def test_read_outbox_raises_on_network_error(monkeypatch):
    def fail(*a, **k):
        raise fediverse.requests.RequestException('boom')
    monkeypatch.setattr(fediverse.requests, 'request', fail)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)
    with pytest.raises(fediverse.FediverseError):
        activitypub.read_outbox(OUTBOX)
