from django.conf.urls import patterns, url
from django.conf import settings

from dark_lang import views

app_name = 'darklang'
urlpatterns = patterns(
    '', url(r'^$', views.DarkLangView.as_view(), name='preview_lang')
)