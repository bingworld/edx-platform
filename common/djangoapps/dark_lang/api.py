"""
Support code for dark-launching languages.  These languages won't be used
when determining which translation to give a user based on their browser
header, but can be selected by setting the ``preview-lang`` query parameter
to the language code.
"""
from django.conf import settings
from edxmako.shortcuts import render_to_response

from openedx.core.djangoapps.user_api.preferences.api import (
    delete_user_preference, get_user_preference, set_user_preference
)
from lang_pref import LANGUAGE_KEY

from django.utils.translation.trans_real import parse_accept_lang_header
from django.utils.translation import LANGUAGE_SESSION_KEY

from dark_lang import DARK_LANGUAGE_KEY
from dark_lang.models import DarkLangConfig


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
LANGUAGE_INPUT_FIELD = 'preview_lang'
RESET_SUBMIT = 'reset'
SET_LANGUAGE_SUBMIT = 'set_language'

class Darklang(object):
    """
    Support class and code for dark-launching languages.

    This is configured by creating ``DarkLangConfig`` rows in the database,
    using the django admin site.
    """

    @property
    def released_langs(self):
        """
        Current list of released languages
        """
        language_options = DarkLangConfig.current().released_languages_list
        if settings.LANGUAGE_CODE not in language_options:
            language_options.append(settings.LANGUAGE_CODE)
        return language_options

    def process_darklang_request(self, request):
        """
        Prevent user from requesting un-released languages
        """
        if not DarkLangConfig.current().enabled:
            return None

        if RESET_SUBMIT in request.POST:
            # Reset and clear the language preference
            return 'Language reset to %s' % self.clear_preview_language(request)
        if SET_LANGUAGE_SUBMIT in request.POST:
            # Set the Preview Language
            return self.set_preview_language(request)



    def set_preview_language(self, request):
        """
        Attempt to set the Preview language
        :param preview_lang: The language code to set the Preview Langauge to
        :return dark language setting code
        """
        if not DarkLangConfig.current().enabled:
            return None

        if LANGUAGE_INPUT_FIELD not in request.POST:
            return None

        preview_lang = request.POST[LANGUAGE_INPUT_FIELD]

        if preview_lang == '':
            return None

        auth_user = request.user.is_authenticated()

        # Set the session key to the requested preview lang
        request.session[LANGUAGE_SESSION_KEY] = preview_lang

        # Make sure that we set the requested preview lang as the dark lang preference for the
        # user, so that the lang_pref middleware doesn't clobber away the dark lang preview.
        if auth_user:
            set_user_preference(request.user, DARK_LANGUAGE_KEY, preview_lang)
        return 'Language set to %s' % preview_lang

    def clear_preview_language(self, request):
        """
        Clears the dark language preview
        :param request: The incoming Django Request
        :return: The Response message
        """
        auth_user = request.user.is_authenticated()

        # delete the session language key (if one is set)
        if LANGUAGE_SESSION_KEY in request.session:
            del request.session[LANGUAGE_SESSION_KEY]

        if auth_user:
            # Reset user's dark lang preference to null
            delete_user_preference(request.user, DARK_LANGUAGE_KEY)
            # Get & set user's preferred language
            user_pref = get_user_preference(request.user, LANGUAGE_KEY)
            if user_pref:
                request.session[LANGUAGE_SESSION_KEY] = user_pref
        return user_pref

    def fuzzy_match(self, lang_code):
        """Returns a fuzzy match for lang_code"""
        if lang_code in self.released_langs:
            return lang_code

        lang_prefix = lang_code.partition('-')[0]
        for released_lang in self.released_langs:
            released_prefix = released_lang.partition('-')[0]
            if lang_prefix == released_prefix:
                return released_lang
        return None

    def dark_parse_accept_lang_header(self, accept):
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


