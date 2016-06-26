from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse


class CalisphereSitemap(Sitemap):
    pass


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
