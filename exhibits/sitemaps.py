from itertools import chain

from django.contrib.sitemaps import Sitemap

from .models import Exhibit, HistoricalEssay, LessonPlan, Theme

class ExhibitionsSitemap(Sitemap):
    def items(self):
        return list(chain(
            Exhibit.objects.all(),
            HistoricalEssay.objects.all(),
            LessonPlan.objects.all(),
            Theme.objects.all(),
        ))
