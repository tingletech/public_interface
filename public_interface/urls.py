from django.conf.urls import include, url
from django.contrib import admin
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from fastsitemaps import views

from calisphere.contact_form_view import CalisphereContactFormView
from exhibits.views import calCultures

from calisphere.sitemaps import *
from exhibits.sitemaps import *
from .sitemaps import *

sitemaps = {
    # keys are sitemap P<section>s
    'static': StaticSitemap,
    'exhibitions': ExhibitionsSitemap,
    'collections': CollectionSitemap,
    'institutions': InstitutionSitemap,
    'items': ItemSitemap,
}

admin.autodiscover()

urlpatterns = [
    url(r'^', include('calisphere.urls', namespace="calisphere")),
    url(r'^exhibitions/', include('exhibits.urls', namespace="exhibits")),
    url(r'^for-educators/', include('exhibits.teacher_urls', namespace="for-teachers")),
    url(r'^cal-cultures/', calCultures, name="cal-cultures"),

    url(r'^admin/', admin.site.urls),
    url(r'^contact/$',
        CalisphereContactFormView.as_view(),
        name='contact_form'),
    url(r'^contact/sent/$',
        TemplateView.as_view(
            template_name='contact_form/contact_form_sent.html'),
        name='contact_form_sent'),
    url(r'^sitemap\.xml$', views.index, {'sitemaps': sitemaps}),
    url(r'^sitemap-(?P<section>.+)\.xml$', views.sitemap, {'sitemaps': sitemaps}),
    url(r'^robots.txt$',
        lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")
    )
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
