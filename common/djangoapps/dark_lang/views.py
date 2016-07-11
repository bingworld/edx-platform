"""
Views file for the Darklang Django App
"""
from openedx.core.lib.api.view_utils import view_auth_classes

from django.http import HttpResponse
from django.views.generic.base import View
from edxmako.shortcuts import render_to_response


@view_auth_classes(is_authenticated=False)
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

    def get(self, request, error=None):
        """
        Displays the Form for setting/resetting a User's dark language setting
        :param request: The Django Request Object
        :return: View containing the form for setting the preview lang
        """
        return render_to_response("darklang/preview_lang.html")