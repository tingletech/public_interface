import re

from django.apps import apps
from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse
from django.conf import settings
from calisphere.collection_data import CollectionManager

app = apps.get_app_config('calisphere')


class StaticSitemap(Sitemap):


    def items(self):
        return [
          'calisphere:collectionsDirectory',
          'calisphere:about',
          'calisphere:help',
          'calisphere:termsOfUse',
          'calisphere:privacyStatement',
          'calisphere:outreach',
          'calisphere:contribute',
        ]


    def location(self, item):
        return reverse(item)


class InstitutionSitemap(Sitemap):


    def items(self):
        return app.registry.repository_data.keys()


    def location(self, item):
        return reverse(
            'calisphere:repositoryView',
            kwargs={'repository_id': item, 'subnav': 'items'}
        )


class CollectionSitemap(Sitemap):


    def items(self):
        return CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY).parsed


    def location(self, item):
        col_id = re.match(r'^https://registry.cdlib.org/api/v1/collection/(?P<collection_id>\d+)/$',
                          item.url)
        return reverse(
            'calisphere:collectionView',
            kwargs={'collection_id': col_id.group('collection_id')}
        )


class ItemSitemap(Sitemap):
    pass
