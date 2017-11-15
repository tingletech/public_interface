from __future__ import unicode_literals, print_function
from __future__ import division
from future import standard_library
from functools import reduce
standard_library.install_aliases()
from builtins import range
from past.utils import old_div
from django.apps import apps
from django.shortcuts import render, redirect
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404, JsonResponse, HttpResponse
from calisphere.collection_data import CollectionManager
from .constants import CAMPUS_LIST, DEFAULT_FACET_FILTER_TYPES, FACET_FILTER_TYPES, SORT_OPTIONS, FEATURED_UNITS, getCollectionData, getRepositoryData, collectionFilterDisplay, repositoryFilterDisplay
from .cache_retry import SOLR_select, SOLR_raw, json_loads_url
from static_sitemaps.util import _lazy_load
from static_sitemaps import conf
from requests.exceptions import HTTPError

import os
import operator
import math
import re
import copy
import simplejson as json
import string
import urllib.parse

def process_sort_collection_data(string):
    '''temporary; should parse sort_collection_data
       with either `:` or `::` dlimiter style
    '''
    if '::' in string:
        return string.split('::', 2)
    else:
        part1, remainder = string.split(':', 1)
        part2, part3 = remainder.rsplit(':https:')
        return [part1, part2, 'https:{}'.format(part3)]


def getMoreCollectionData(collection_data):
    collection = getCollectionData(
        collection_data=collection_data,
        collection_id=None, )
    collection_details = json_loads_url(
        "{0}?format=json".format(collection['url']))
    collection['local_id'] = collection_details['local_id']
    collection['slug'] = collection_details['slug']
    return collection



def getCollectionMosaic(collection_url):
    # get collection information from collection registry
    collection_details = json_loads_url(collection_url + "?format=json")
    collection_repositories = []
    for repository in collection_details.get('repository'):
        if 'campus' in repository and len(repository['campus']) > 0:
            collection_repositories.append(repository['campus'][0]['name'] +
                                           ", " + repository['name'])
        else:
            collection_repositories.append(repository['name'])

    # get 6 image items from the collection for the mosaic preview
    search_terms = {
        'q': '*:*',
        'fields': 'reference_image_md5, url_item, id, title, collection_url, type_ss',
        'sort': 'sort_title asc',
        'rows': 6,
        'start': 0,
        'fq': [
            'collection_url: \"' + collection_url + '\"', 'type_ss: \"image\"'
        ]
    }
    display_items = SOLR_select(**search_terms)
    items = display_items.results

    search_terms['fq'] = [
        'collection_url: \"' + collection_url + '\"',
        '(*:* AND -type_ss:\"image\")'
    ]
    ugly_display_items = SOLR_select(**search_terms)
    # if there's not enough image items, get some non-image items for the mosaic preview
    if len(items) < 6:
        items = items + ugly_display_items.results

    return {
        'name': collection_details['name'],
        'description': collection_details['description'],
        'collection_id': collection_details['id'],
        'institutions': collection_repositories,
        'numFound': display_items.numFound + ugly_display_items.numFound,
        'display_items': items
    }

def process_facets(facets, filters, facet_type=None):
    #remove facets with count of zero
    display_facets = dict((facet, count)
                          for facet, count in list(facets.items()) if count != 0)

    #sort facets by facet value, else by count
    if facet_type and facet_type == 'facet_decade':
        display_facets = sorted(
            iter(list(display_facets.items())), key=operator.itemgetter(0))
    else:
        display_facets = sorted(
            iter(list(display_facets.items())),
            key=operator.itemgetter(1),
            reverse=True)

    #append selected filters even if they have a count of 0
    for f in filters:
        if not any(f in facet[0] for facet in display_facets):
            api_url = re.match(
                r'^https://registry\.cdlib\.org/api/v1/(?P<collection_or_repo>collection|repository)/(?P<url>\d*)/?',
                f)
            if api_url is not None:
                if api_url.group('collection_or_repo') == 'collection':
                    collection = getCollectionData(
                        collection_id=api_url.group('url'))
                    display_facets.append(
                        (collection['url'] + "::" + collection['name'], 0))
                elif api_url.group('collection_or_repo') == 'repository':
                    repository = getRepositoryData(
                        repository_id=api_url.group('url'))
                    display_facets.append(
                        (repository['url'] + "::" + repository['name'], 0))
            else:
                display_facets.append((f, 0))

    return display_facets

def facetQuery(facet_filter_types, params, solr_search, extra_filter=None):
    # get facet counts
    # if the user's selected some of the available facets (ie - there are
    # filters selected for this field type) perform a search as if those
    # filters were not applied to obtain facet counts
    #
    # since we AND filters of the same type, counts should go UP when
    # more than one facet is selected as a filter, not DOWN (or'ed filters
    # of the same type)

    facets = {}
    for i, facet_filter_type in enumerate(facet_filter_types):
        facet_type = facet_filter_type['facet']
        if (len(params.getlist(facet_type)) > 0):
            exclude_facets_of_type = params.copy()
            exclude_facets_of_type.pop(facet_type)

            solrParams = solrEncode(exclude_facets_of_type, facet_filter_types, [facet_filter_type])
            if extra_filter:
                solrParams['fq'].append(extra_filter)
            facet_search = SOLR_select(**solrParams)

            facets[facet_type] = process_facets(
                facet_search.facet_counts['facet_fields'][facet_type],
                list(map(facet_filter_type['filter_transform'], params.getlist(facet_type))), facet_type)
        else:
            facets[facet_type] = process_facets(
                solr_search.facet_counts['facet_fields'][facet_type],
                list(map(facet_filter_type['filter_transform'], params.getlist(facet_type)))
                if facet_type in params else [], facet_type)

        # facets[facet_type] = list(map(lambda facet_item : (facet_filter_type['facet_transform'](facet_item[0]), facet_item[1]), facets[facet_type]))
        for j, facet_item in enumerate(facets[facet_type]):
            facets[facet_type][j] = (facet_filter_type['facet_transform'](facet_item[0]), facet_item[1])

    return facets


def searchDefaults(params):
    context = {
        'q': params.get('q', ''),
        'rq': params.getlist('rq'),
        'rows': params.get('rows', '24'),
        'start': params.get('start', 0),
        'sort': params.get('sort', 'relevance'),
        'view_format': params.get('view_format', 'thumbnails'),
        'rc_page': params.get('rc_page', 0)
    }
    return context


def solrEncode(params, filter_types, facet_types = []):
    if len(facet_types) == 0:
        facet_types = filter_types

    # concatenate query terms from refine query and query box
    query_terms = []
    q = params.get('q')
    if q:
        query_terms.append(q)
    for qt in params.getlist('rq'):
        if qt:
            query_terms.append(qt)

    if len(query_terms) == 1:
        query_terms_string = query_terms[0]
    else:
        query_terms_string = " AND ".join(query_terms)


    filters = []
    for filter_type in filter_types:
        selected_filters = params.getlist(filter_type['facet'])
        if (len(selected_filters) > 0):
            filter_transform = filter_type['filter_transform']

            selected_filters = list(map(
                lambda filterVal :
                    '{0}: "{1}"'.format(filter_type['filter'], filter_transform(filterVal)),
                selected_filters))
            selected_filters = " OR ".join(selected_filters)
            filters.append(selected_filters)

    return {
        'q': query_terms_string,
        'rows': params.get('rows', '24'),
        'start': params.get('start', 0),
        'sort': SORT_OPTIONS[params.get('sort', 'relevance' if query_terms else 'a')],
        'fq': filters,
        'facet': 'true',
        'facet_mincount': 1,
        'facet_limit': '-1',
        'facet_field': list(facet_type['facet'] for facet_type in facet_types)
    }

def getHostedContentFile(structmap):
    contentFile = ''
    if structmap['format'] == 'image':
        structmap_url = '{}{}/info.json'.format(settings.UCLDC_IIIF,
                                                structmap['id'])
        if structmap_url.startswith('//'):
            structmap_url = ''.join(['http:', structmap_url])
        size = json_loads_url(structmap_url)['sizes'][-1]
        if size['height'] > size['width']:
            access_size = {
                'width': (old_div((size['width'] * 1024), size['height'])),
                'height': 1024
            }
            access_url = json_loads_url(
                structmap_url)['@id'] + "/full/,1024/0/default.jpg"
        else:
            access_size = {
                'width': 1024,
                'height': (old_div((size['height'] * 1024), size['width']))
            }
            access_url = json_loads_url(
                structmap_url)['@id'] + "/full/1024,/0/default.jpg"

        contentFile = {
            'titleSources': json.dumps(json_loads_url(structmap_url)),
            'format': 'image',
            'size': access_size,
            'url': access_url
        }
    if structmap['format'] == 'file':
        contentFile = {
            'id': structmap['id'],
            'format': 'file',
        }
    if structmap['format'] == 'video':
        access_url = os.path.join(settings.UCLDC_MEDIA, structmap['id'])
        contentFile = {
            'id': structmap['id'],
            'format': 'video',
            'url': access_url
        }
    if structmap['format'] == 'audio':
        access_url = os.path.join(settings.UCLDC_MEDIA, structmap['id'])
        contentFile = {
            'id': structmap['id'],
            'format': 'audio',
            'url': access_url
        }

    return contentFile


def itemView(request, item_id=''):
    item_id_search_term = 'id:"{0}"'.format(item_id)
    item_solr_search = SOLR_select(q=item_id_search_term)
    if not item_solr_search.numFound:
        # second level search
        def _fixid(id):
            return re.sub(r'^(\d*--http:/)(?!/)', r'\1/', id)

        old_id_search = SOLR_select(
            q='harvest_id_s:*{}'.format(_fixid(item_id)))
        if old_id_search.numFound:
            return redirect('calisphere:itemView',
                            old_id_search.results[0]['id'])
        else:
            raise Http404("{0} does not exist".format(item_id))

    for item in item_solr_search.results:
        if 'structmap_url' in item and len(item['structmap_url']) >= 1:
            item['harvest_type'] = 'hosted'
            structmap_url = string.replace(item['structmap_url'],
                                           's3://static',
                                           'https://s3.amazonaws.com/static')
            structmap_data = json_loads_url(structmap_url)

            if 'structMap' in structmap_data:
                # complex object
                if 'order' in request.GET and 'structMap' in structmap_data:
                    # fetch component object
                    item['selected'] = False
                    order = int(request.GET['order'])
                    item['selectedComponentIndex'] = order
                    component = structmap_data['structMap'][order]
                    component['selected'] = True
                    if 'format' in component:
                        item['contentFile'] = getHostedContentFile(component)
                    # remove emptry strings from list
                    for k, v in list(component.items()):
                        if isinstance(v, list):
                            if isinstance(v[0], str):
                                component[k] = [name for name in v if name.strip()]
                    # remove empty lists and empty strings from dict
                    item['selectedComponent'] = dict(
                        (k, v) for k, v in list(component.items()) if v)
                else:
                    item['selected'] = True
                    # if parent content file, get it
                    if 'format' in structmap_data:
                        item['contentFile'] = getHostedContentFile(
                            structmap_data)
                    # otherwise get first component file
                    else:
                        component = structmap_data['structMap'][0]
                        item['contentFile'] = getHostedContentFile(component)
                item['structMap'] = structmap_data['structMap']

                # single or multi-format object
                formats = [
                    component['format']
                    for component in structmap_data['structMap']
                    if 'format' in component
                ]
                if len(set(formats)) > 1:
                    item['multiFormat'] = True
                else:
                    item['multiFormat'] = False

                # carousel has captions or not
                if all(f == 'image' for f in formats):
                    item['hasComponentCaptions'] = False
                else:
                    item['hasComponentCaptions'] = True

                # number of components
                item['componentCount'] = len(structmap_data['structMap'])

                # has fixed item thumbnail image
                if 'reference_image_md5' in item:
                    item['has_fixed_thumb'] = True
                else:
                    item['has_fixed_thumb'] = False
            else:
                # simple object
                if 'format' in structmap_data:
                    item['contentFile'] = getHostedContentFile(structmap_data)
        else:
            item['harvest_type'] = 'harvested'
            if 'url_item' in item:
                if item['url_item'].startswith('http://ark.cdlib.org/ark:'):
                    item['oac'] = True
                    item['url_item'] = string.replace(
                        item['url_item'], 'http://ark.cdlib.org/ark:',
                        'http://oac.cdlib.org/ark:')
                    item['url_item'] = item['url_item'] + '/?brand=oac4'
                else:
                    item['oac'] = False
            #TODO: error handling 'else'

        item['parsed_collection_data'] = []
        item['parsed_repository_data'] = []
        item['institution_contact'] = []
        for collection_data in item['collection_data']:
            item['parsed_collection_data'].append(
                getMoreCollectionData(collection_data))
        if 'repository_data' in item:
            for repository_data in item['repository_data']:
                item['parsed_repository_data'].append(
                    getRepositoryData(repository_data=repository_data))

                institution_url = item['parsed_repository_data'][0]['url']
                institution_details = json_loads_url(institution_url +
                                                     "?format=json")
                if 'ark' in institution_details and institution_details['ark'] != '':
                    contact_information = json_loads_url(
                        "http://dsc.cdlib.org/institution-json/" +
                        institution_details['ark'])
                else:
                    contact_information = ''

                item['institution_contact'].append(contact_information)

    meta_image = False
    if item_solr_search.results[0].get('reference_image_md5', False):
        meta_image = urllib.parse.urljoin(
            settings.UCLDC_FRONT,
            '/crop/999x999/{0}'.format(
                item_solr_search.results[0]['reference_image_md5']), )

    fromItemPage = request.META.get("HTTP_X_FROM_ITEM_PAGE")
    if fromItemPage:
        return render(request, 'calisphere/itemViewer.html', {
            'q': '',
            'item': item_solr_search.results[0],
            'item_solr_search': item_solr_search,
            'meta_image': meta_image,
        })
    search_results = {'reference_image_md5': None}
    search_results.update(item_solr_search.results[0])
    return render(request, 'calisphere/itemView.html', {
        'q': '',
        'item': search_results,
        'item_solr_search': item_solr_search,
        'meta_image': meta_image,
        'rc_page': None,
        'related_collections': None,
        'slug': None,
        'title': None,
        'num_related_collections': None,
        'rq': None,
    })

def search(request):
    if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        params = request.GET.copy()
        context = searchDefaults(params)
        solr_search = SOLR_select(**solrEncode(params, FACET_FILTER_TYPES))

        # TODO: create a no results found page
        if len(solr_search.results) == 0: print('no results found')

        context['facets'] = facetQuery(FACET_FILTER_TYPES, params, solr_search)

        context.update({
            'search_results': solr_search.results,
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(old_div(float(solr_search.numFound), int(context['rows'])))),
            'related_collections': relatedCollections(request),
            'num_related_collections': len(params.getlist('collection_data'))
            if len(params.getlist('collection_data')) > 0 else
            len(context['facets']['collection_data']),
            'form_action': reverse('calisphere:search'),
            'FACET_FILTER_TYPES': FACET_FILTER_TYPES,
            'filters': {}
        })

        for filter_type in FACET_FILTER_TYPES:
            param_name = filter_type['facet']
            display_name = filter_type['filter']
            filter_transform = filter_type['filter_display']

            if len(params.getlist(param_name)) > 0:
                context['filters'][display_name] = list(map(filter_transform, params.getlist(param_name)))

        return render(request, 'calisphere/searchResults.html', context)

    return redirect('calisphere:home')

def itemViewCarousel(request):
    params = request.GET.copy()
    item_id = params.get('itemId')
    if item_id is None:
        raise Http404("No item id specified")

    referral = params.get('referral')
    linkBackId = ''
    extra_filter = ''
    facet_filter_types = FACET_FILTER_TYPES
    if referral == 'institution':
        linkBackId = params.get('repository_data', None)
    elif referral == 'collection':
        linkBackId = params.get('collection_data', None)
        # get any collection-specific facets
        collection_url = 'https://registry.cdlib.org/api/v1/collection/' + linkBackId + '/'
        collection_details = json_loads_url(collection_url + '?format=json')
        custom_facets = collection_details.get('custom_facet', [])
        for custom_facet in custom_facets:
            facet_filter_types.append({
                'facet': custom_facet['facet_field'],
                'display_name': custom_facet['label'],
                'filter': custom_facet['facet_field'],
                'filter_transform': lambda (a) : a,
                'facet_transform': lambda (a) : a,
                'filter_display': lambda (a) : a
            })
    elif referral == 'campus':
        linkBackId = params.get('campus_slug', None)
        if linkBackId:
            campus = filter(lambda c: c['slug'] == linkBackId, CAMPUS_LIST)
            campus_id = campus[0]['id']
            if not campus_id or campus_id == '':
                raise Http404("Campus registry ID not found")
            extra_filter = 'campus_url: "https://registry.cdlib.org/api/v1/campus/' + campus_id + '/"'

    solrParams = solrEncode(params, facet_filter_types)
    if extra_filter:
        solrParams['fq'].append(extra_filter)

    #if no query string or filters, do a "more like this" search
    if solrParams['q'] == '' and len(solrParams['fq']) == 0:
        carousel_solr_search = SOLR_raw(
            q='id:' + item_id,
            fields='id, type_ss, reference_image_md5, title',
            mlt='true',
            mlt_count='24',
            mlt_fl='title,collection_name,subject',
            mlt_mintf=1, )
        if json.loads(carousel_solr_search)['response']['numFound'] == 0:
            raise Http404('No object with id "' + item_id + '" found.')
        search_results = json.loads(
            carousel_solr_search)['response']['docs'] + json.loads(
                carousel_solr_search)['moreLikeThis'][item_id]['docs']
        numFound = len(search_results)
        # numFound = json.loads(carousel_solr_search)['moreLikeThis'][item_id]['numFound']
    else:
        solrParams.update({'facet': 'false',
            'fields': 'id, type_ss, reference_image_md5, title'})
        if solrParams.get('start') == 'NaN':
            solrParams['start'] = 0
        try:
            carousel_solr_search = SOLR_select(**solrParams)
        except HTTPError as e:
            # https://stackoverflow.com/a/19384641/1763984
            print(request.get_full_path())
            raise(e)
        search_results = carousel_solr_search.results
        numFound = carousel_solr_search.numFound

    if 'init' in params:
        context = searchDefaults(params)

        context['filters'] = {}
        for filter_type in facet_filter_types:
            param_name = filter_type['facet']
            display_name = filter_type['filter']
            filter_transform = filter_type['filter_display']

            if len(params.getlist(param_name)) > 0:
                context['filters'][display_name] = list(map(filter_transform, params.getlist(param_name)))

        context.update({
            'numFound': numFound,
            'search_results': search_results,
            'item_id': item_id,
            'referral': request.GET.get('referral'),
            'referralName': request.GET.get('referralName'),
            'campus_slug': request.GET.get('campus_slug'),
            'linkBackId': linkBackId
        })

        return render(request, 'calisphere/carouselContainer.html', context)
    else:
        return render(request, 'calisphere/carousel.html', {
            'start': params.get('start', 0),
            'search_results': search_results,
            'item_id': item_id
        })


def relatedCollections(request, slug=None, repository_id=None):
    params = request.GET.copy()
    ajaxRequest = True if 'rc_page' in params else False

    # get list of related collections
    solrParams = solrEncode(params, FACET_FILTER_TYPES, [{'facet': 'collection_data'}])
    solrParams['rows'] = 0

    if 'campus_slug' in params:
        slug = params.get('campus_slug')

    if slug:
        campus = filter(lambda c: c['slug'] == slug, CAMPUS_LIST)
        extra_filter = 'campus_url: "https://registry.cdlib.org/api/v1/campus/' + campus[0]['id'] + '/"'
        solrParams['fq'].append(extra_filter)
    if repository_id:
        extra_filter = 'repository_url: "https://registry.cdlib.org/api/v1/repository/' + repository_id + '/"'
        solrParams['fq'].append(extra_filter)
    related_collections = SOLR_select(**solrParams)
    related_collections = related_collections.facet_counts['facet_fields']['collection_data']

    # TODO: WHY IS THIS NECESSARY?
    field = filter(lambda f: f['facet'] == 'collection_data', FACET_FILTER_TYPES)
    collection_urls = list(map(
        field[0]['filter_transform'],
        params.getlist('collection_data')))
    # remove collections with a count of 0 and sort by count
    related_collections = process_facets(
        related_collections, collection_urls)
    # remove 'count'
    related_collections = list(facet
                               for facet, count in related_collections)

    # get three items for each related collection
    three_related_collections = []
    rc_page = int(params.get('rc_page', 0))
    for i in range(rc_page * 3, rc_page * 3 + 3):
        if len(related_collections) > i:
            collection = getCollectionData(related_collections[i])

            rc_solrParams = {
                'q': solrParams['q'],
                'rows': '3',
                'fq': ["collection_url: \"" + collection['url'] + "\""],
                'fields': 'collection_data, reference_image_md5, url_item, id, title, type_ss'
            }

            collection_items = SOLR_select(**rc_solrParams)
            collection_items = collection_items.results

            if len(collection_items) < 3:
                rc_solrParams['q'] = ''
                collection_items_no_query = SOLR_select(**rc_solrParams)
                collection_items = collection_items + collection_items_no_query.results

            if len(collection_items) > 0:
                collection_data = {
                    'image_urls': collection_items,
                    'name': collection['name'],
                    'collection_id': collection['id']
                }

                # TODO: get this from repository_data in solr rather than from the registry API
                collection_details = json_loads_url(collection['url'] + "?format=json")
                if collection_details['repository'][0]['campus']:
                    collection_data['institution'] = collection_details[
                        'repository'][0]['campus'][0]['name'] + ', ' + collection_details[
                            'repository'][0]['name']
                else:
                    collection_data['institution'] = collection_details[
                        'repository'][0]['name']

                three_related_collections.append(collection_data)

    if not ajaxRequest:
        return three_related_collections
    else:
        return render(request, 'calisphere/related-collections.html', {
            'q': params.get('q'),
            'rq': params.getlist('rq'),
            'num_related_collections': len(related_collections),
            'related_collections': three_related_collections,
            'rc_page': params.get('rc_page'),
        })


def collectionsDirectory(request):
    solr_collections = CollectionManager(settings.SOLR_URL,
                                         settings.SOLR_API_KEY)
    collections = []

    page = int(request.GET['page']) if 'page' in request.GET else 1

    for collection_link in solr_collections.shuffled[(page - 1) * 10:
                                                     page * 10]:
        collections.append(getCollectionMosaic(collection_link.url))

    context = {
        'collections': collections,
        'random': True,
        'pages': int(math.ceil(old_div(float(len(solr_collections.shuffled)), 10)))
    }

    if page * 10 < len(solr_collections.shuffled):
        context['next_page'] = page + 1
    if page - 1 > 0:
        context['prev_page'] = page - 1

    return render(request, 'calisphere/collectionsRandomExplore.html', context)


def collectionsAZ(request, collection_letter):
    solr_collections = CollectionManager(settings.SOLR_URL,
                                         settings.SOLR_API_KEY)
    collections_list = solr_collections.split[collection_letter.lower()]

    page = int(request.GET['page']) if 'page' in request.GET else 1
    pages = int(math.ceil(old_div(float(len(collections_list)), 10)))

    collections = []
    for collection_link in collections_list[(page - 1) * 10:page * 10]:
        collections.append(getCollectionMosaic(collection_link.url))

    alphabet = list(
        (character, True if
         character.lower() not in solr_collections.no_collections else False)
        for character in list(string.ascii_uppercase))

    context = {
        'collections': collections,
        'alphabet': alphabet,
        'collection_letter': collection_letter,
        'page': page,
        'pages': pages,
        'random': None,
    }

    if page * 10 < len(collections_list):
        context['next_page'] = page + 1
    if page - 1 > 0:
        context['prev_page'] = page - 1

    return render(request, 'calisphere/collectionsAZ.html', context)


def collectionsTitles(request):
    '''create JSON/data for the collections search page'''

    def djangoize(uri):
        '''turn registry URI into URL on django site'''
        collection_id = uri.split(
            'https://registry.cdlib.org/api/v1/collection/', 1)[1][:-1]
        return reverse(
            'calisphere:collectionView',
            kwargs={'collection_id': collection_id})

    collections = CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY)
    data = [{
        'uri': djangoize(uri),
        'title': title
    } for (uri, title) in collections.parsed]
    return JsonResponse(data, safe=False)


def collectionsSearch(request):
    return render(request, 'calisphere/collectionsTitleSearch.html',
                  {'collections': [],
                   'collection_q': True})


def collectionView(request, collection_id):
    collection_url = 'https://registry.cdlib.org/api/v1/collection/' + collection_id + '/'
    collection_details = json_loads_url(collection_url + '?format=json')
    for repository in collection_details['repository']:
        repository['resource_id'] = repository['resource_uri'].split('/')[-2]

    params = request.GET.copy()
    context = searchDefaults(params)

    # Collection Views don't allow filtering or faceting by collection_data or repository_data
    facet_filter_types = filter(lambda facet_filter_type: facet_filter_type['facet'] != 'collection_data' and facet_filter_type['facet'] != 'repository_data', FACET_FILTER_TYPES)
    # Add Custom Facet Filter Types
    if collection_details['custom_facet']:
        for custom_facet in collection_details['custom_facet']:
            facet_filter_types.append({
                'facet': custom_facet['facet_field'],
                'display_name': custom_facet['label'],
                'filter': custom_facet['facet_field'],
                'filter_transform': lambda (a) : a,
                'facet_transform': lambda (a) : a,
                'filter_display': lambda (a) : a
            })
    extra_filter = 'collection_url: "' + collection_url + '"'

    # perform the search
    solrParams = solrEncode(params, facet_filter_types)
    solrParams['fq'].append(extra_filter)
    solr_search = SOLR_select(**solrParams)
    context['search_results'] = solr_search.results
    context['numFound'] = solr_search.numFound
    context['pages'] = int(math.ceil(old_div(float(solr_search.numFound), int(context['rows']))))

    context['facets'] = facetQuery(facet_filter_types, params, solr_search, extra_filter)

    context['filters'] = {}
    for filter_type in facet_filter_types:
        param_name = filter_type['facet']
        display_name = filter_type['filter']
        filter_transform = filter_type['filter_display']

        if len(params.getlist(param_name)) > 0:
            context['filters'][display_name] = list(map(filter_transform, params.getlist(param_name)))

    context.update({
        'FACET_FILTER_TYPES': facet_filter_types,
        'collection': collection_details,
        'collection_id': collection_id,
        'form_action': reverse(
            'calisphere:collectionView',
            kwargs={'collection_id': collection_id}),
    })

    return render(request, 'calisphere/collectionView.html', context)

def campusDirectory(request):
    repositories_solr_query = SOLR_select(
        q='*:*',
        rows=0,
        start=0,
        facet='true',
        facet_mincount=1,
        facet_field=['repository_url'],
        facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields'][
        'repository_url']

    repositories = []
    for repository_url in solr_repositories:
        repository = getRepositoryData(repository_url=repository_url)
        if repository['campus']:
            repositories.append({
                'name':
                repository['name'],
                'campus':
                repository['campus'],
                'repository_id':
                re.match(
                    r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?',
                    repository['url']).group('repository_id')
            })

    repositories = sorted(
        repositories,
        key=lambda repository: (repository['campus'], repository['name']))
    # Use hard-coded campus list so UCLA ends up in the correct order
    # campuses = sorted(list(set([repository['campus'] for repository in repositories])))

    return render(request, 'calisphere/campusDirectory.html', {
        'repositories': repositories,
        'campuses': CAMPUS_LIST,
        'state_repositories': None,
        'description': None,
    })


def statewideDirectory(request):
    repositories_solr_query = SOLR_select(
        q='*:*',
        rows=0,
        start=0,
        facet='true',
        facet_mincount=1,
        facet_field=['repository_url'],
        facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields'][
        'repository_url']
    repositories = []
    for repository_url in solr_repositories:
        repository = getRepositoryData(repository_url=repository_url)
        if repository['campus'] == '':
            repositories.append({
                'name':
                repository['name'],
                'repository_id':
                re.match(
                    r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?',
                    repository['url']).group('repository_id')
            })

    binned_repositories = []
    bin = []
    for repository in repositories:
        if repository['name'][0] in string.punctuation:
            bin.append(repository)
    if len(bin) > 0:
        binned_repositories.append({'punctuation': bin})

    for char in string.ascii_uppercase:
        bin = []
        for repository in repositories:
            if repository['name'][0] == char or repository['name'][0] == char.upper:
                bin.append(repository)
        if len(bin) > 0:
            bin.sort()
            binned_repositories.append({char: bin})

    return render(request, 'calisphere/statewideDirectory.html', {
        'state_repositories': binned_repositories,
        'campuses': None,
        'meta_image': None,
        'description': None,
        'q': None,
    })


def institutionView(request,
                    institution_id,
                    subnav=False,
                    institution_type='repository|campus'):
    institution_url = 'https://registry.cdlib.org/api/v1/' + institution_type + '/' + institution_id + '/'
    institution_details = json_loads_url(institution_url + "?format=json")
    if 'ark' in institution_details and institution_details['ark'] != '':
        contact_information = json_loads_url(
            "http://dsc.cdlib.org/institution-json/" +
            institution_details['ark'])
    else:
        contact_information = ''

    if 'campus' in institution_details and len(
            institution_details['campus']) > 0:
        uc_institution = institution_details['campus']
    else:
        uc_institution = False

    if subnav == 'items':
        params = request.GET.copy()

        facet_filter_types = list(FACET_FILTER_TYPES)
        extra_filter = None
        if institution_type == 'repository':
            facet_filter_types = filter(lambda f: f['facet'] != 'repository_data', FACET_FILTER_TYPES)
            extra_filter = 'repository_url: "' + institution_url + '"'
        elif institution_type == 'campus':
            extra_filter = 'campus_url: "' + institution_url + '"'

        solrParams = solrEncode(params, facet_filter_types)
        if extra_filter:
            solrParams['fq'].append(extra_filter)
        solr_search = SOLR_select(**solrParams)

        facets = facetQuery(facet_filter_types, params, solr_search, extra_filter)

        filter_display = {}
        for filter_type in facet_filter_types:
            param_name = filter_type['facet']
            display_name = filter_type['filter']
            filter_transform = filter_type['filter_display']

            if len(params.getlist(param_name)) > 0:
                filter_display[display_name] = list(map(filter_transform, params.getlist(param_name)))

        context = searchDefaults(params)
        context.update({
            'filters': filter_display,
            'search_results': solr_search.results,
            'facets': facets,
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(old_div(float(solr_search.numFound), int(context['rows'])))),
            'institution': institution_details,
            'contact_information': contact_information,
            'FACET_FILTER_TYPES': facet_filter_types
        })

        if institution_type == 'campus':
            context.update({
                'repository_id': None,
                'title': institution_details['name'],
                'campus_slug': institution_details['slug'],
                'related_collections': relatedCollections(request, slug=institution_details['slug']),
                'form_action':
                reverse('calisphere:campusView',
                kwargs={'campus_slug': institution_details['slug'],
                'subnav': 'items'})
            })
            for campus in CAMPUS_LIST:
                if institution_id == campus['id'] and 'featuredImage' in campus:
                    context['featuredImage'] = campus['featuredImage']

        if institution_type == 'repository':
            context.update({
                'repository_id': institution_id,
                'uc_institution': uc_institution,
                'related_collections': relatedCollections(request, repository_id=institution_id),
                'form_action':
                reverse('calisphere:repositoryView',
                kwargs={'repository_id': institution_id,
                'subnav': 'items'})
            })

            # title for UC institutions needs to show parent campus
            if uc_institution:
                context['title'] = '{0} / {1}'.format(
                    uc_institution[0]['name'], institution_details['name'])
            else:
                context['title'] = institution_details['name']

            if uc_institution is False:
                for unit in FEATURED_UNITS:
                    if unit['id'] == institution_id:
                        context['featuredImage'] = unit['featuredImage']

        if len(params.getlist('collection_data')):
            context['num_related_collections'] = len(params.getlist('collection_data'))
        else:
            context['num_related_collections'] = len(facets['collection_data'])

        return render(request, 'calisphere/institutionViewItems.html', context)

    else:
        page = int(request.GET['page']) if 'page' in request.GET else 1

        if institution_type == 'repository':
            institutions_fq = ['repository_url: "' + institution_url + '"']
        if institution_type == 'campus':
            institutions_fq = ['campus_url: "' + institution_url + '"']

        collectionsParams = {
            'q': '',
            'rows': 0,
            'start': 0,
            'fq': institutions_fq,
            'facet': 'true',
            'facet_mincount': 1,
            'facet_limit': '-1',
            'facet_field': ['sort_collection_data'],
            'facet_sort': 'index'
        }

        collections_solr_search = SOLR_select(**collectionsParams)

        pages = int(
            math.ceil(
                old_div(float(
                    len(collections_solr_search.facet_counts['facet_fields'][
                        'sort_collection_data'])), 10)))
        # doing the search again;
        # could we slice this from the results above?
        collectionsParams['facet_offset'] = (page-1) * 10
        collectionsParams['facet_limit'] = 10
        collectionsParams['facet_sort'] = 'index'
        collections_solr_search = SOLR_select(**collectionsParams)

        # solrpy gives us a dict == unsorted (!)
        # use the `facet_decade` mode of process_facets to do a lexical sort by value ....
        related_collections = list(
            collection[0]
            for collection in process_facets(
                collections_solr_search.facet_counts['facet_fields'][
                    'sort_collection_data'],
                [],
                'facet_decade', ))
        for i, related_collection in enumerate(related_collections):
            collection_parts = process_sort_collection_data(related_collection)
            collection_data = getCollectionData(
                collection_data='{0}::{1}'.format(
                    collection_parts[2],
                    collection_parts[1], ))
            related_collections[i] = getCollectionMosaic(
                collection_data['url'])

        context = {
            'page': page,
            'pages': pages,
            'collections': related_collections,
            'contact_information': contact_information,
            'institution': institution_details,
        }

        if page + 1 <= pages:
            context['next_page'] = page + 1
        if page - 1 > 0:
            context['prev_page'] = page - 1

        if institution_type == 'campus':
            context['campus_slug'] = institution_details['slug']
            context['title'] = institution_details['name']
            for campus in CAMPUS_LIST:
                if institution_id == campus['id'] and 'featuredImage' in campus:
                    context['featuredImage'] = campus['featuredImage']
            context['repository_id'] = None
            context['institution']['campus'] = None

        if institution_type == 'repository':
            context['repository_id'] = institution_id
            context['uc_institution'] = uc_institution
            # title for UC institutions needs to show parent campus
            # refactor, as this is copy/pasted in this commit
            if uc_institution:
                context['title'] = '{0} / {1}'.format(
                    uc_institution[0]['name'], institution_details['name'])
            else:
                context['title'] = institution_details['name']

            if uc_institution is False:
                for unit in FEATURED_UNITS:
                    if unit['id'] == institution_id:
                        context['featuredImage'] = unit['featuredImage']

            if 'featuredImage' not in context:
                context['featuredImage'] = None

        return render(request, 'calisphere/institutionViewCollections.html',
                      context)


def campusView(request, campus_slug, subnav=False):
    campus_id = ''
    featured_image = ''
    for campus in CAMPUS_LIST:
        if campus_slug == campus['slug']:
            campus_id = campus['id']
            campus_name = campus['name']
            if 'featuredImage' in campus:
                featured_image = campus['featuredImage']
    if campus_id == '':
        print('Campus registry ID not found')

    if subnav == 'institutions':
        campus_url = 'https://registry.cdlib.org/api/v1/campus/' + campus_id + '/'
        campus_details = json_loads_url(campus_url + "?format=json")

        if 'ark' in campus_details and campus_details['ark'] != '':
            contact_information = json_loads_url(
                "http://dsc.cdlib.org/institution-json/" +
                campus_details['ark'])
        else:
            contact_information = ''

        campus_fq = ['campus_url: "' + campus_url + '"']

        institutions_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=campus_fq,
            facet='true',
            facet_mincount=1,
            facet_limit='-1',
            facet_field=['repository_data'])

        related_institutions = list(
            institution[0]
            for institution in process_facets(
                institutions_solr_search.facet_counts['facet_fields'][
                    'repository_data'], []))

        for i, related_institution in enumerate(related_institutions):
            related_institutions[i] = getRepositoryData(
                repository_data=related_institution)
        related_institutions = sorted(
            related_institutions,
            key=lambda related_institution: related_institution['name'])

        return render(request, 'calisphere/institutionViewInstitutions.html', {
            # 'campus': campus_name,
            'title': campus_name,
            'featuredImage': featured_image,
            'campus_slug': campus_slug,
            'institutions': related_institutions,
            'institution': campus_details,
            'contact_information': contact_information,
            'repository_id': None,
        })

    else:
        return institutionView(request, campus_id, subnav, 'campus')


def repositoryView(request, repository_id, subnav=False):
    return institutionView(request, repository_id, subnav, 'repository')


def contactOwner(request):
    # print request.GET
    return render(request, 'calisphere/thankyou.html')


def posters(request):
    this_dir = os.path.dirname(os.path.realpath(__file__))
    this_data = os.path.join(this_dir, 'poster-data.json')
    poster_data = json.loads(open(this_data).read())
    poster_data = sorted(poster_data.items())

    return render(request, 'calisphere/posters.html',
                  {'poster_data': poster_data})


def sitemapSection(request, section):
    storage = _lazy_load(conf.STORAGE_CLASS)(location=conf.ROOT_DIR)
    path = os.path.join(conf.ROOT_DIR, 'sitemap-{}.xml'.format(section))

    f = storage.open(path)
    content = f.readlines()
    f.close()
    return HttpResponse(content, content_type='application/xml')


def sitemapSectionZipped(request, section):
    storage = _lazy_load(conf.STORAGE_CLASS)(location=conf.ROOT_DIR)
    path = os.path.join(conf.ROOT_DIR, 'sitemap-{}.xml.gz'.format(section))

    f = storage.open(path)
    content = f.readlines()
    f.close()
    return HttpResponse(content, content_type='application/zip')
