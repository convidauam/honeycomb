from pyramid.csrf import new_csrf_token
from pyramid.httpexceptions import HTTPSeeOther, HTTPNotFound
from pyramid.security import (
    remember,
    forget,
    NO_PERMISSION_REQUIRED,
)

from pyramid.view import (
    forbidden_view_config,
    view_config,
)

from deform import Form, ValidationFailure, Button

from .. import security
from .. import models


@view_config(name="login", context=models.BeeHive, renderer='templates/login.jinja2')
@forbidden_view_config(renderer='templates/login.jinja2')
def login_view(context, request):
    next_url = request.params.get('next', request.referrer)
    login_url = '/login'
    if not next_url or next_url == login_url:
        next_url = "/"

    if request.identity:
        return HTTPSeeOther(location=next_url)
    else:
        new_csrf_token(request)
        headers = remember(request, 'convida@unam.social')
        return HTTPSeeOther(location=next_url, headers=headers)

@view_config(name='logout', context=models.BeeHive)
def logout_view(context, request):
    assert request.identity
    next_url = "/"
    new_csrf_token(request)
    headers = forget(request)
    return HTTPSeeOther(location=next_url, headers=headers)
