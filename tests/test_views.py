from honeycomb.models import BeeHive
from honeycomb.views.default import beehive_view
from honeycomb.views.notfound import notfound_view


def test_beehive_view(app_request):
    context = BeeHive()
    info = beehive_view(context, app_request)
    assert app_request.response.status_int == 200
    assert info['project'] == 'BeeHive Project'
    assert info['honeycombs'] == []

def test_notfound_view(app_request):
    info = notfound_view(app_request)
    assert app_request.response.status_int == 404
    assert info == {}
