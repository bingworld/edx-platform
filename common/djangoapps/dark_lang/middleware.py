"""
Middleware for dark-launching languages. These languages won't be used
when determining which translation to give a user based on their browser
header, but can be selected by setting the ``preview-lang`` query parameter
to the language code.

Adding the query parameter ``clear-lang`` will reset the language stored
in the user's session.

This middleware must be placed before the LocaleMiddleware, but after
the SessionMiddleware.
"""
from dark_lang import DARK_LANGUAGE_KEY
from dark_lang.models import DarkLangConfig
from openedx.core.djangoapps.user_api.preferences.api import (
    get_user_preference
)

from django.utils.translation import LANGUAGE_SESSION_KEY

from .api import Darklang


class DarkLangMiddleware(object):
    """
    Middleware for dark-launching languages.

    This is configured by creating ``DarkLangConfig`` rows in the database,
    using the django admin site.
    """

    def process_request(self, request):
        """
        Prevent user from requesting un-released languages except by using the preview-lang query string.
        """
        if not DarkLangConfig.current().enabled:
            return

        Darklang().clean_accept_headers(request)
        self._activate_preview_language(request)

    def _activate_preview_language(self, request):
        """
        Check the user's dark language setting in the sessiona and apply it
        """
        auth_user = request.user.is_authenticated()
        preview_lang = None
        if auth_user:
            # Get the request user's dark lang preference
            preview_lang = get_user_preference(request.user, DARK_LANGUAGE_KEY)

        # User doesn't have a dark lang preference, so just return
        if not preview_lang:
            return

        # Set the session key to the requested preview lang
        request.session[LANGUAGE_SESSION_KEY] = preview_lang
