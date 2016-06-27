from django.conf.urls import url
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page
from django.conf import settings

from . import views

t = settings.DJANGO_CACHE_TIMEOUT

urlpatterns = [
    url(r'^$',
        cache_page(t)(views.exhibitRandom),
        name='randomExplore'),
    url(r'jarda-related-resources/$',
        cache_page(t)(
            TemplateView.as_view(
                template_name='exhibits/jarda-related-resources.html'
            )),
        name='jarda-related-resources'),
    url(r'^search/',
        cache_page(t)(views.exhibitSearch),
        name='exhibitSearch'),
    url(r'^browse/(?P<category>[-\w]+)/$',
        cache_page(t)(views.exhibitDirectory),
        name='exhibitDirectory'),
    url(r'^(?P<exhibit_id>\d+)/(?P<exhibit_slug>[-\w]+)/$',
        cache_page(t)(views.exhibitView),
        name='exhibitView'),
    url(r'^(?P<exhibit_id>\d+)/items/(?P<item_id>.+)/$',
        cache_page(t)(views.itemView),
        name='itemView'),
    url(r'^essay/(?P<essay_id>\d+)/(?P<essay_slug>[-\w]+)/$',
        cache_page(t)(views.essayView),
        name='essayView'),
    url(r'^t(?P<theme_id>\d+)/(?P<theme_slug>[-_\w]+)/$',
        cache_page(t)(views.themeView),
        name='themeView'),
]
