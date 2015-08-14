from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from calisphere.home import HomeView

urlpatterns = patterns('calisphere',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^search/$', 'views.search', name='search'),
    url(r'^item/(?P<item_id>.*)/$', 'views.itemView', name='itemView'),

    url(r'^collections/$', 'views.collectionsDirectory', name='collectionsDirectory'),
    url(r'^collections/(?P<collection_letter>[a-zA-Z]{1})/', 'views.collectionsAZ', name='collectionsAZ'),
    url(r'^collections/(?P<collection_letter>num)/', 'views.collectionsAZ', name='collectionsAZ'),
    url(r'^collections/(?P<collection_id>\d*)/', 'views.collectionView', name='collectionView'),
    url(r'^collections/themedCollections/', 'views.themedCollections', name='themedCollections'),
    url(r'^collections/titleSearch/$', 'views.collectionsSearch', name='collectionsTitleSearch'),
    url(r'^collections/', 'views.collectionsSearch', name='collectionsSearch'),

    url(r'^institution/(?P<repository_id>\d*)(?:/(?P<subnav>items|collections))?/', 'views.repositoryView', name='repositoryView'),
    url(r'^(?P<campus_slug>UC\w{1,2})(?:/(?P<subnav>items|collections|institutions))?/', 'views.campusView', name='campusView'),
    url(r'^institutions/uc-partners/$', 'views.campusDirectory', name='campusDirectory'),
    url(r'^institutions/statewide-partners/$', 'views.statewideDirectory', name='statewideDirectory'),

    url(r'about/$', TemplateView.as_view(template_name='calisphere/about.html'), name='about'),
    url(r'contact/$', TemplateView.as_view(template_name='calisphere/contact.html'), name='contact'),
    url(r'help/$', TemplateView.as_view(template_name='calisphere/help.html'), name='help'),
    url(r'terms/$', TemplateView.as_view(template_name='calisphere/termsOfUse.html'), name='termsOfUse'),
    url(r'privacy/$', TemplateView.as_view(template_name='calisphere/privacyStatement.html'), name='privacyStatement'),
    url(r'siteMap/$', TemplateView.as_view(template_name='calisphere/siteMap.html'), name='siteMap'),

    # AJAX HELPERS
    url(r'^relatedCollections/', 'views.relatedCollections', name='relatedCollections'),
    url(r'^carousel/', 'views.itemViewCarousel', name='carousel'),
)
