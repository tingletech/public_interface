""" logic for cache / retry for solr and JSON from registry
"""
from django.core.cache import cache
from django.conf import settings

import urllib2
import solr
from retrying import retry
import pickle
import hashlib
import json

SOLR_DEFAULTS = {
    'mm': '100%',
    'pf3': 'title',
    'pf': 'text,title',
    'qs': 12,
    'ps': 12,
}

"""
    qf:
        fields and the "boosts" `fieldOne^2.3 fieldTwo fieldThree^0.4`
    mm: (Minimum 'Should' Match)
    qs:
        Query Phrase Slop (in qf fields; affects matching).

    pf: Phrase Fields
	"pf" with the syntax
        field~slop.
        field~slop^boost.
    ps:
	Default amount of slop on phrase queries built with "pf",
	"pf2" and/or "pf3" fields (affects boosting).
    pf2: (Phrase bigram fields)
    ps2: (Phrase bigram slop)
	<!> Solr4.0 As with 'ps' but for 'pf2'. If not specified,
	'ps' will be used.
    pf3 (Phrase trigram fields)
	As with 'pf' but chops the input into tri-grams, e.g. "the
	brown fox jumped" is queried as "the brown fox" "brown fox
	jumped"
    ps3 (Phrase trigram slop)
    tie (Tie breaker)
	Float value to use as tiebreaker in DisjunctionMaxQueries
	(should be something much less than 1)
        Typically a low value (ie: 0.1) is useful.

"""


# create a hash for a cache key
def kwargs_md5(**kwargs):
    m = hashlib.md5()
    m.update(pickle.dumps(kwargs))
    return m.hexdigest()


# wrapper function for json.loads(urllib2.urlopen)
@retry(stop_max_delay=3000)  # milliseconds
def json_loads_url(url_or_req):
    key = kwargs_md5(key='json_loads_url', url=url_or_req)
    data = cache.get(key)
    if not data:
        try:
            data = json.loads(urllib2.urlopen(url_or_req).read())
        except urllib2.HTTPError:
            data = {}
    return data


# dummy class for holding cached data
class SolrCache(object):
    pass


# wrapper function for solr queries
@retry(stop_max_delay=3000)  # milliseconds
def SOLR_select(**kwargs):
    kwargs.update(SOLR_DEFAULTS)
    # set up solr handler with auth token
    SOLR = solr.SearchHandler(
        solr.Solr(
            settings.SOLR_URL,
            post_headers={
                'X-Authentication-Token': settings.SOLR_API_KEY,
            },
        ),
        "/query"
    )
    # look in the cache
    key = 'SOLR_select_{0}'.format(kwargs_md5(**kwargs))
    sc = cache.get(key)
    if not sc:
        # do the solr look up
        sr = SOLR(**kwargs)
        # copy attributes that can be pickled to new object
        sc = SolrCache()
        sc.results = sr.results
        sc.header = sr.header
        sc.facet_counts = getattr(sr, 'facet_counts', None)
        sc.numFound = sr.numFound
        cache.set(key, sc, settings.DJANGO_CACHE_TIMEOUT)  # seconds
    return sc


@retry(stop_max_delay=3000)
def SOLR_raw(**kwargs):
    kwargs.update(SOLR_DEFAULTS)
    # set up solr handler with auth token
    SOLR = solr.SearchHandler(
        solr.Solr(
            settings.SOLR_URL,
            post_headers={
                'X-Authentication-Token': settings.SOLR_API_KEY,
            },
        ),
        "/query"
    )
    # look in the cache
    key = 'SOLR_raw_{0}'.format(kwargs_md5(**kwargs))
    sr = cache.get(key)
    if not sr:
        # do the solr look up
        sr = SOLR.raw(**kwargs)
        cache.set(key, sr, settings.DJANGO_CACHE_TIMEOUT)  # seconds
    return sr

@retry(stop_max_delay=3000)
def SOLR_select_nocache(**kwargs):
    kwargs.update(SOLR_DEFAULTS)
    # set up solr handler with auth token
    SOLR = solr.SearchHandler(
        solr.Solr(
            settings.SOLR_URL,
            post_headers={
                'X-Authentication-Token': settings.SOLR_API_KEY,
            },
        ),
        "/query"
    )

    # do the solr look up
    sr = SOLR(**kwargs)

    return sr 
 
