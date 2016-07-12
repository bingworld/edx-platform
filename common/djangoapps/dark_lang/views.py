"""
Views file for the Darklang Django App
"""
from openedx.core.lib.api.view_utils import view_auth_classes
from django.views.generic.base import View

from edxmako.shortcuts import render_to_response

LANGUAGE_INPUT_FIELD = 'input_language'
RESET_SUBMIT = 'reset'
SET_LANGUAGE_SUBMIT = 'set_language'
SET_LANGUAGE_CODE = 'set_language_code'

@view_auth_classes()
class DarkLangView(View):
    """
    View used when a user is attempting to change the preview language using Darklang.

    Expected Behavior:
    GET - returns a form for setting/resetting the user's dark language
    POST - updates the setting to the given dark language
    DELETE - removes the dark language settings and resets to default behavior

    Note: This class and View are meant to replace DarkLang as a middleware, which was determined to be a
    security risk.
    """
    template_name = 'darklang/preview_lang.html'

    def get(self, request, error=None):
        """
        Displays the Form for setting/resetting a User's dark language setting
        :param request: The Django Request Object
        :return: View containing the form for setting the preview lang
        """
        context = {
            'disable_courseware_js': True,
            'uses_pattern_library': True
        }

        return render_to_response(self.template_name, context)

    def post(self, request):
        context = {
            'disable_courseware_js': True,
            'uses_pattern_library': True
        }

        post_data = request.POST

        if RESET_SUBMIT in post_data:
            # TODO Clear the language setting
            context.update({SET_LANGUAGE_CODE: 'RESET'})
        if SET_LANGUAGE_SUBMIT in post_data and LANGUAGE_INPUT_FIELD in post_data:
                context.update({SET_LANGUAGE_CODE: post_data[LANGUAGE_INPUT_FIELD]})

        return render_to_response(self.template_name, context)
