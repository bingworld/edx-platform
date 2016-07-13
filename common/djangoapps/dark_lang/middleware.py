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
from django.conf import settings

from dark_lang import DARK_LANGUAGE_KEY
from dark_lang.models import DarkLangConfig
from openedx.core.djangoapps.user_api.preferences.api import (
    delete_user_preference, get_user_preference, set_user_preference
)
from lang_pref import LANGUAGE_KEY

from django.utils.translation.trans_real import parse_accept_lang_header
from django.utils.translation import LANGUAGE_SESSION_KEY

from .api import Darklang

def dark_parse_accept_lang_header(accept):
    '''
    The use of 'zh-cn' for 'Simplified Chinese' and 'zh-tw' for 'Traditional Chinese'
    are now deprecated, as discussed here: https://code.djangoproject.com/ticket/18419.
    The new language codes 'zh-hans' and 'zh-hant' are now used since django 1.7.
    Although majority of browsers still use the old language codes, some new browsers
    such as IE11 in Windows 8.1 start to use the new ones, which makes the current
    chinese translations of edX don't work properly under these browsers.
    This function can keep compatibility between the old and new language codes. If one
    day edX uses django 1.7 or higher, this function can be modified to support the old
    language codes until there are no browsers use them.
    '''
    browser_langs = parse_accept_lang_header(accept)
    django_langs = []
    for lang, priority in browser_langs:
        lang = CHINESE_LANGUAGE_CODE_MAP.get(lang.lower(), lang)
        django_langs.append((lang, priority))

    return django_langs

# If django 1.7 or higher is used, the right-side can be updated with new-style codes.
CHINESE_LANGUAGE_CODE_MAP = {
    # The following are the new-style language codes for chinese language
    'zh-hans': 'zh-CN',     # Chinese (Simplified),
    'zh-hans-cn': 'zh-CN',  # Chinese (Simplified, China)
    'zh-hans-sg': 'zh-CN',  # Chinese (Simplified, Singapore)
    'zh-hant': 'zh-TW',     # Chinese (Traditional)
    'zh-hant-hk': 'zh-HK',  # Chinese (Traditional, Hongkong)
    'zh-hant-mo': 'zh-TW',  # Chinese (Traditional, Macau)
    'zh-hant-tw': 'zh-TW',  # Chinese (Traditional, Taiwan)
    # The following are the old-style language codes that django does not recognize
    'zh-mo': 'zh-TW',       # Chinese (Traditional, Macau)
    'zh-sg': 'zh-CN',       # Chinese (Simplified, Singapore)
}


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

        self._clean_accept_headers(request)
        self._activate_preview_language(request)

    def _format_accept_value(self, lang, priority=1.0):
        """
        Formats lang and priority into a valid accept header fragment.
        """
        return "{};q={}".format(lang, priority)

    def _clean_accept_headers(self, request):
        """
        Remove any language that is not either in ``self.released_langs`` or
        a territory of one of those languages.
        """
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', None)
        if accept is None or accept == '*':
            return

        new_accept = []
        darklang = Darklang()
        for lang, priority in dark_parse_accept_lang_header(accept):
            fuzzy_code = darklang.fuzzy_match(lang.lower())
            if fuzzy_code:
                new_accept.append(self._format_accept_value(fuzzy_code, priority))

        new_accept = ", ".join(new_accept)

        request.META['HTTP_ACCEPT_LANGUAGE'] = new_accept

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