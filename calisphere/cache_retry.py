""" logic for cache / retry for solr and JSON from registry
"""
from django.core.cache import cache
from django.conf import settings

import urllib2
import solr
from retrying import retry
import pickle
import hashlib
import simplejson


# create a hash for a cache key
def kwargs_md5(**kwargs):
    m = hashlib.md5()
    m.update(pickle.dumps(kwargs))
    return m.hexdigest()


# wrapper function for json.loads(urllib2.urlopen)
@retry(stop_max_delay=3000)  # milliseconds
def json_loads_url(url):
    key = kwargs_md5(key='json_loads_url', url=url)
    json = cache.get(key)
    if not json:
        json = simplejson.loads(urllib2.urlopen(url).read())
    return json


# dummy class for holding cached data
class SolrCache(object):
    pass


# wrapper function for solr queries
@retry(stop_max_delay=3000)  # milliseconds
def SOLR_select(**kwargs):
    # figure out what the solr_url is
    # look in the cache
    key = kwargs_md5(**kwargs)
    sc = cache.get(key)
    if not sc:
        solr_url = kwargs.pop('solr_url')
        SOLR = solr_handler(solr_url, settings.SOLR_API_KEY)
        # do the solr look up
        # q=None, fields=None, highlight=None, score=True, sort=None, sort_order="asc", **params
        sr = SOLR(**kwargs) 
        # copy attributes that can be pickled to new object
        sc = SolrCache()
        sc.results = sr.results
        sc.header = sr.header
        sc.facet_counts = getattr(sr, 'facet_counts', None)
        sc.numFound = sr.numFound
        cache.set(key, sc, 60*15)  # seconds
    return sc


def solr_handler(solr_url, solr_api_key):
    # set up solr handler with auth token
    return solr.SearchHandler(
        solr.Solr(
            solr_url,
            post_headers={
                'X-Authentication-Token': solr_api_key,
            },
        ),
        "/query"
    )


def request_to_solr_url(request):
    return request.GET.get('solr_url', settings.SOLR_URL)
