"""
sentry.utils.auth
~~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2014 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
from __future__ import absolute_import

import time
import logging

from django.conf import settings
from django.contrib.auth import login as _login
from django.contrib.auth.backends import ModelBackend
from django.core.urlresolvers import reverse

from sentry.models import User, Authenticator

logger = logging.getLogger('sentry.auth')


def _make_key_value(val):
    return val.strip().split('=', 1)


def parse_auth_header(header):
    try:
        return dict(map(_make_key_value, header.split(' ', 1)[1].split(',')))
    except Exception:
        return {}


def get_auth_providers():
    return [
        key for key, cfg_names
        in settings.AUTH_PROVIDERS.iteritems()
        if all(getattr(settings, c, None) for c in cfg_names)
    ]


def get_pending_2fa_user(request):
    rv = request.session.get('_pending_2fa')
    if rv is None:
        return

    user_id, created_at = rv
    if created_at < time.time() - 60 * 5:
        return None

    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        pass


def has_pending_2fa(request):
    return request.session.get('_pending_2fa') is not None


def get_login_redirect(request, default=None):
    if default is None:
        default = reverse('sentry')

    # If there is a pending 2fa authentication bound to the session then
    # we need to go to the 2fa dialog.
    if has_pending_2fa(request):
        return reverse('sentry-2fa-dialog')

    login_url = request.session.pop('_next', None) or default
    if login_url.startswith(('http://', 'https://')):
        login_url = default
    elif login_url.startswith(reverse('sentry-login')):
        login_url = default
    return login_url


def find_users(username, with_valid_password=True):
    """
    Return a list of users that match a username
    and falling back to email
    """
    qs = User.objects
    if with_valid_password:
        qs = qs.exclude(password='!')

    try:
        # First, assume username is an iexact match for username
        user = qs.get(username__iexact=username)
        return [user]
    except User.DoesNotExist:
        # If not, we can take a stab at guessing it's an email address
        if '@' in username:
            # email isn't guaranteed unique
            return list(qs.filter(email__iexact=username))
    return []


def login(request, user, passed_2fa=False):
    has_2fa = Authenticator.objects.user_has_2fa(user)
    if has_2fa and not passed_2fa:
        request.session['_pending_2fa'] = [user.id, time.time()]
    else:
        # If there is no authentication backend, just attach the first
        # one and hope it goes through.  This apparently is a thing we
        # have been doing for a long time, just moved it to a more
        # reasonable place.
        if not hasattr(user, 'backend'):
            user.backend = settings.AUTHENTICATION_BACKENDS[0]
        _login(request, user)
        log_auth_success(request, user.username)


def log_auth_success(request, username):
    logger.info(
        'User authenticated successfully [ip:%s username:%r]',
        request.META['REMOTE_ADDR'],
        username,
        extra={
            'request': request,
        }
    )


def log_auth_failure(request, username=None):
    logger.info(
        'User failed authentication [ip:%s username:%r]',
        request.META['REMOTE_ADDR'],
        username or '',
        extra={
            'request': request,
        }
    )


class EmailAuthBackend(ModelBackend):
    """
    Authenticate against django.contrib.auth.models.User.

    Supports authenticating via an email address or a username.
    """
    def authenticate(self, username=None, password=None):
        users = find_users(username)
        if users:
            for user in users:
                try:
                    if user.password and user.check_password(password):
                        return user
                except ValueError:
                    continue
        return None
