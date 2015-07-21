from django.shortcuts import render
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import Http404
from calisphere.collection_data import CollectionManager
from constants import *
from cache_retry import SOLR_select, json_loads_url

import operator
import math
import re
import copy
import simplejson as json
import string

# concat query with 'AND'
def concat_query(q, rq):
    if q == '': return rq
    elif rq == '': return q
    else: return q + ' AND ' + rq

# concat filters with 'OR'
def concat_filters(filters, filter_type):
    # OR-ING FILTERS OF ONE TYPE, YET AND-ING FILTERS OF DIFF TYPES
    fq_contents = filter_type + ': '

    for counter, f in enumerate(filters):
        fq_contents = fq_contents + '"' + f + '"'
        # if not at the last filter term, continue OR-ing together terms
        if counter < len(filters)-1:
            fq_contents = fq_contents + " OR " + filter_type + ': '

    return [fq_contents]

# collect filters into an array
def solrize_filters(filters):
    fq = []
    for filter_type in FACET_TYPES:
        if len(filters[filter_type[0]]) > 0:
            fq.extend(concat_filters(filters[filter_type[0]], filter_type[0]))

    return fq

def solrize_sort(sort):
    return 'score desc'
    # if sort == 'relevance':
    #     return 'score desc'
    # if sort == 'a':
    #     return 'title_s desc'
    # if sort == 'z':
    #     return 'title_s asc'
    # if sort == 'oldest':
    #     return 'facet_decade_s asc'
    # if sort == 'newest':
    #     return 'facet_decade_s desc'

def process_facets(facets, filters):
    display_facets = dict((facet, count) for facet, count in facets.iteritems() if count != 0)
    display_facets = sorted(display_facets.iteritems(), key=operator.itemgetter(1), reverse=True)

    for f in filters:
        if not any(f in facet for facet in display_facets):
            display_facets.append((f, 0))

    return display_facets

def getCollectionData(collection_data=None, collection_id=None):
    collection = {}
    if collection_data:
        collection['url'] = collection_data.split('::')[0] if len(collection_data.split('::')) >= 1 else ''
        collection['name'] = collection_data.split('::')[1] if len(collection_data.split('::')) >= 2 else ''

        collection_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/collection/(?P<url>\d*)/?', collection['url'])
        if collection_api_url is None:
            print 'no collection api url:'
            collection['id'] = ''
        else:
            collection['id'] = collection_api_url.group('url')
    elif collection_id:
        collection['url'] = "https://registry.cdlib.org/api/v1/collection/{0}/".format(collection_id)
        collection['id'] = collection_id

        collection_details = json_loads_url("{0}?format=json".format(collection['url']))
        collection['name'] = collection_details['name']
    return collection

def getCollectionMosaic(collection_url):
    collection_details = json_loads_url(collection_url + "?format=json")

    collection_repositories = []

    repository_details = collection_details.get('repository')

    if not (repository_details):
        return
    
    for repository in repository_details:
        if 'campus' in repository and len(repository['campus']) > 0:
            collection_repositories.append(repository['campus'][0]['name'] + ", " + repository['name'])
        else:
            collection_repositories.append(repository['name'])

    collection_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/collection/(?P<url>\d*)/?', collection_url)
    collection_id = collection_api_url.group('url')

    display_items = SOLR_select(
        q='*:*',
        fields='reference_image_md5, url_item, id, title, collection_url, type_ss',
        rows=6,
        start=0,
        fq=['collection_url: \"' + collection_url + '\"']
    )

    return {
        'name': collection_details['name'],
        'institutions': collection_repositories,
        'description': collection_details['description'],
        'collection_id': collection_id,
        'numFound': display_items.numFound,
        'display_items': display_items.results
    }

def getRepositoryData(repository_data=None, repository_id=None):
    repository = {}
    if repository_data:
        repository['url'] = repository_data.split('::')[0] if len(repository_data.split('::')) >= 1 else ''
        repository['name'] = repository_data.split('::')[1] if len(repository_data.split('::')) >= 2 else ''
        repository['campus'] = repository_data.split('::')[2] if len(repository_data.split('::')) >= 3 else ''

        repository_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/repository/(?P<url>\d*)/', repository['url'])
        if repository_api_url is None:
            print 'no repository api url'
            repository['id'] = ''
        else:
            repository['id'] = repository_api_url.group('url')
    elif repository_id:
        repository['url'] = "https://registry.cdlib.org/api/v1/repository/" + repository_id + "/"
        repository['id'] = repository_id

        repository_details = json_loads_url(repository['url'] + "?format=json")
        repository['name'] = repository_details['name']
        if repository_details['campus']:
            repository['campus'] = repository_details['campus'][0]['name']
        else:
            repository['campus'] = ''
    return repository

def facetQuery(facet_fields, queryParams, solr_search, extra_filter=None):
    facets = {}
    for facet_type in facet_fields:
        if facet_type in queryParams['filters'] and len(queryParams['filters'][facet_type]) > 0:
            # other_filters is all the filters except the ones of the current filter type
            other_filters = {key: value for key, value in queryParams['filters'].items()
                if key != facet_type}
            other_filters[facet_type] = []
            
            fq = solrize_filters(other_filters)
            if extra_filter: 
                fq.append(extra_filter)

            # perform the exact same search, but as though no filters of this type have been selected
            # to obtain the counts for facets for this facet type
            facet_solr_search = SOLR_select(
                q=queryParams['query_terms'],
                rows='0',
                fq=fq,
                facet='true',
                facet_mincount=1,
                facet_limit='-1',
                facet_field=[facet_type]
            )

            facets[facet_type] = process_facets(
                facet_solr_search.facet_counts['facet_fields'][facet_type],
                queryParams['filters'][facet_type]
            )
        else:
            facets[facet_type] = process_facets(
                solr_search.facet_counts['facet_fields'][facet_type],
                queryParams['filters'][facet_type] if facet_type in queryParams['filters'] else []
            )

    return facets

def processQueryRequest(request):
    # concatenate query terms from refine query and query box, set defaults
    q = request.GET['q'] if 'q' in request.GET else ''
    rq = request.GET.getlist('rq')
    query_terms = reduce(concat_query, request.GET.getlist('q') + request.GET.getlist('rq')) if 'q' in request.GET else ''
    rows = request.GET['rows'] if 'rows' in request.GET else '16'
    start = request.GET['start'] if 'start' in request.GET and request.GET['start'] != '' else '0'
    sort = request.GET['sort'] if 'sort' in request.GET else 'relevance'
    view_format = request.GET['view_format'] if 'view_format' in request.GET else 'thumbnails'
    rc_page = int(request.GET['rc_page']) if 'rc_page' in request.GET else 0

    # for each filter_type tuple ('solr_name', 'Display Name') in the list FACET_TYPES
    # create a dictionary with key solr_name of filter and value list of parameters for that filter
    # {'type': ['image', 'audio'], 'repository_name': [...]}
    filters = dict((filter_type[0], request.GET.getlist(filter_type[0])) for filter_type in FACET_TYPES)

    # use collection_id and repository_id to retrieve collection_data and repository_data filter values
    for i, filter_item in enumerate(filters['collection_data']):
        collection = getCollectionData(collection_id=filter_item)
        filters['collection_data'][i] = collection['url'] + "::" + collection['name']
    for i, filter_item in enumerate(filters['repository_data']):
        repository = getRepositoryData(repository_id=filter_item)
        filters['repository_data'][i] = repository['url'] + "::" + repository['name']
        if repository['campus'] != '':
            filters['repository_data'][i] = filters['repository_data'][i] + "::" + repository['campus']

    return {
        'q': q,
        'rq': rq,
        'query_terms': query_terms,
        'rows': rows,
        'start': start,
        'sort': sort,
        'view_format': view_format,
        'filters': filters,
        'rc_page': rc_page
    }

def home(request):
    return render (request, 'calisphere/home.html', {'q': ''})

def getHostedContentFile(structmap):
    contentFile = ''
    if structmap['format'] == 'image':
        contentFile = {
            'titleSources': json.dumps(json_loads_url('http://ucldciiifwest-env.elasticbeanstalk.com/' + structmap['id'] + '/info.json')), 
            'format': 'image'
        }
    if structmap['format'] == 'file':
        contentFile = {
            'id': structmap['id'],
            'format': 'file'
        }
    return contentFile

def itemView(request, item_id=''):
    item_id_search_term = 'id:"{0}"'.format(_fixid(item_id))
    item_solr_search = SOLR_select(q=item_id_search_term)
    if not item_solr_search.numFound:
        raise Http404("{0} does not exist".format(item_id))

    for item in item_solr_search.results:
        if 'structmap_url' in item and len(item['structmap_url']) >= 1:
            item['harvest_type'] = 'hosted'
            structmap_url = string.replace(item['structmap_url'], 's3://static', 'https://s3.amazonaws.com/static');
            structmap_data = json_loads_url(structmap_url)

            if 'structMap' in structmap_data:
                # complex object
                if 'order' in request.GET and 'structMap' in structmap_data:
                    # fetch component object
                    item['selected'] = False
                    order = int(request.GET['order'])
                    component = structmap_data['structMap'][order]
                    component['selected'] = True
                    if 'format' in component:
                        item['contentFile'] = getHostedContentFile(component)
                    item['selectedComponent'] = component
                else: 
                    item['selected'] = True
                    if 'format' in structmap_data:
                        item['contentFile'] = getHostedContentFile(structmap_data)
                item['structMap'] = structmap_data['structMap']
            else: 
                # simple object
                if 'format' in structmap_data:
                    item['contentFile'] = getHostedContentFile(structmap_data)    
        else:
            item['harvest_type'] = 'harvested'
            if 'url_item' in item:
                if item['url_item'].startswith('http://ark.cdlib.org/ark:'):
                    item['oac'] = True
                    item['url_item'] = string.replace(item['url_item'], 'http://ark.cdlib.org/ark:', 'http://oac.cdlib.org/ark:')
                    item['url_item'] = item['url_item'] + '/?brand=oac4'
                else:
                    item['oac'] = False
            #TODO: error handling 'else' 
        
        item['parsed_collection_data'] = []
        item['parsed_repository_data'] = []
        for collection_data in item['collection_data']:
            item['parsed_collection_data'].append(getCollectionData(collection_data=collection_data))
        for repository_data in item['repository_data']:
            item['parsed_repository_data'].append(getRepositoryData(repository_data=repository_data))

    # TODO: write related objects version (else)
    if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        queryParams = processQueryRequest(request)
        queryParams['rows'] = 12
        carousel_items = itemViewCarousel(request, queryParams)
        
        filter_display = {}
        for filter_type in queryParams['filters']:
            if filter_type == 'collection_data':
                filter_display['collection_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    collection = getCollectionData(collection_data=filter_item)
                    filter_display['collection_data'].append(collection)
            elif filter_type == 'repository_data':
                filter_display['repository_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    repository = getRepositoryData(repository_data=filter_item)
                    filter_display['repository_data'].append(repository)
            else:
                filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

        return render(request, 'calisphere/itemView.html', {
            'item_solr_search': item_solr_search,
            'item': item_solr_search.results[0],
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': filter_display,
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'search_results': carousel_items['results'],
            # 'facets': facets,
            'FACET_TYPES': FACET_TYPES,
            'numFound': carousel_items['numFound'],
            'pages': int(math.ceil(float(carousel_items['numFound'])/int(queryParams['rows']))),
            # 'view_format': queryParams['view_format'],
            'related_collections': relatedCollections(request, queryParams),
            # 'rc_page': queryParams['rc_page']
        })

        # return render (request, 'calisphere/home.html', {'q': q})

    return render(request, 'calisphere/itemView.html', {
        'q': '',
        'item': item_solr_search.results[0],
        'item_solr_search': item_solr_search,
    })


def search(request):
    if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        queryParams = processQueryRequest(request)

        # define facet fields to retrieve
        facet_fields = list(facet_type[0] for facet_type in FACET_TYPES)

        solr_search = SOLR_select(
            q=queryParams['query_terms'],
            rows=queryParams['rows'],
            start=queryParams['start'],
            sort=solrize_sort(queryParams['sort']),
            fq=solrize_filters(queryParams['filters']),
            facet='true',
            facet_mincount=1,
            facet_limit='-1',
            facet_field=facet_fields
        )

        # TODO: create a no results found page
        if len(solr_search.results) == 0: print 'no results found'

        # get facet counts
        facets = facetQuery(facet_fields, queryParams, solr_search)

        for i, facet_item in enumerate(facets['collection_data']):
            collection = (getCollectionData(collection_data=facet_item[0]), facet_item[1])
            facets['collection_data'][i] = collection
        for i, facet_item in enumerate(facets['repository_data']):
            repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
            facets['repository_data'][i] = repository

        filter_display = {}
        for filter_type in queryParams['filters']:
            if filter_type == 'collection_data':
                filter_display['collection_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    collection = getCollectionData(collection_data=filter_item)
                    filter_display['collection_data'].append(collection)
            elif filter_type == 'repository_data':
                filter_display['repository_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    repository = getRepositoryData(repository_data=filter_item)
                    filter_display['repository_data'].append(repository)
            else:
                filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

        return render(request, 'calisphere/searchResults.html', {
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': filter_display,
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'sort': queryParams['sort'],
            'search_results': solr_search.results,
            'facets': facets,
            'FACET_TYPES': FACET_TYPES,
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
            'view_format': queryParams['view_format'],
            'related_collections': relatedCollections(request, queryParams),
            'num_related_collections': len(queryParams['filters']['collection_data']) if len(queryParams['filters']['collection_data']) > 0 else len(facets['collection_data']),
            'rc_page': queryParams['rc_page'],
            'form_action': reverse('calisphere:search')
        })

    return render (request, 'calisphere/home.html', {'q': ''})

def itemViewCarousel(request, queryParams={}):
    if not queryParams:
        if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
            queryParams = processQueryRequest(request)

        ajaxRequest = True
        queryParams['rows'] = 6
    else:
        ajaxRequest = False
    
    fq = solrize_filters(queryParams['filters'])
    if 'campus_slug' in request.GET:
        campus_id = ''
        for campus in CAMPUS_LIST:
            if request.GET['campus_slug'] == campus['slug']:
                campus_id = campus['id']
        if campus_id == '':
            print "Campus registry ID not found"

        fq.append('campus_url: "https://registry.cdlib.org/api/v1/campus/' + campus_id + '/"')

    # TODO: getting back way more fields than I really need
    carousel_solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows=queryParams['rows'],
        start=queryParams['start'],
        fq=fq
    )

    # except solr.SolrException:
        # TODO: better error handling
        # print solr.SolrException.reason
        # print solr.SolrException.httpcode
        # print solr.SolrException.body

    # search performed, process the results

    # TODO: create a no results found page
    if len(carousel_solr_search.results) == 0:
        print 'no results found'
    
    if ajaxRequest:
        return render(request, 'calisphere/carousel.html', {
            'q': queryParams['q'],
            'start': queryParams['start'],
            'numFound': carousel_solr_search.numFound,
            'search_results': carousel_solr_search.results,
        })

    return {'results': carousel_solr_search.results, 'numFound': carousel_solr_search.numFound}

def relatedCollections(request, queryParams={}):
    if not queryParams:
        queryParams = processQueryRequest(request)
        ajaxRequest = True
    else:
        ajaxRequest = False

    # #####################
    # get list of related collections
    # uncomment to get list of related collections disregarding any selected collection filters
    # #####################
    # if 'collection_name' in queryParams['filters'] and len(queryParams['filters']['collection_name']) > 0:
    #     related_collections_filters = {key: value for key, value in queryParams['filters'].items()
    #         if key != 'collection_name'}
    #     related_collections_filters['collection_name'] = []
    # else:
    related_collections_filters = queryParams['filters']

    related_collections_solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows='0',
        fq=solrize_filters(related_collections_filters),
        facet='true',
        facet_mincount=1,
        facet_limit='-1',
        facet_field=['collection_data']
    )

    # remove collections with a count of 0 and sort by count
    related_collections_counts = process_facets(
        related_collections_solr_search.facet_counts['facet_fields']['collection_data'],
        queryParams['filters']['collection_data'] if 'collection_data' in queryParams['filters'] else []
    )

    # remove 'count'
    related_collections = list(facet for facet, count in related_collections_counts)

    three_related_collections = []
    for i in range(queryParams['rc_page']*3, queryParams['rc_page']*3+3):
        if len(related_collections) > i:
            facet = ["collection_data: \"" + related_collections[i] + "\""]
            collection_solr_search = SOLR_select(q=queryParams['query_terms'], rows='3', fq=facet, fields='collection_data, reference_image_md5, url_item, id, title, type_ss')

            collection_items = collection_solr_search.results
            if len(collection_solr_search.results) < 3:
                collection_solr_search_no_query = SOLR_select(q='', rows='3', fq=facet, fields='collection_data, reference_image_md5, url_item, id, title, type_ss')
                #TODO: in some cases this will result in the same object appearing twice in the related collections preview
                collection_items = collection_items + collection_solr_search_no_query.results
                
            if len(collection_items) > 0 and len(collection_solr_search.results[0]) > 0:
                if 'collection_data' in collection_solr_search.results[0] and len(collection_solr_search.results[0]['collection_data']) > 0:
                    collection = collection_solr_search.results[0]['collection_data'][0]

                    collection_data = {'image_urls': []}
                    for item in collection_items:
                        collection_data['image_urls'].append(item)
                        
                    collection_url = ''.join([
                        collection.rsplit('::')[0],
                        '?format=json'
                    ])
                    collection_details = json_loads_url(collection_url)

                    collection_data['name'] = collection_details['name']
                    collection_data['resource_uri'] = collection_details['resource_uri']
                    col_id = re.match(r'^/api/v1/collection/(?P<collection_id>\d+)/$', collection_details['resource_uri'])
                    collection_data['collection_id'] = col_id.group('collection_id')

                    # TODO: get this from repository_data in solr rather than from the registry API
                    if collection_details['repository'][0]['campus']:
                        collection_data['institution'] = collection_details['repository'][0]['campus'][0]['name'] + ', ' + collection_details['repository'][0]['name']
                    else:
                        collection_data['institution'] = collection_details['repository'][0]['name']
                    
                    three_related_collections.append(collection_data)

    if not ajaxRequest:
        return three_related_collections
    else:
        return render(request, 'calisphere/related-collections.html', {
            'num_related_collections': len(related_collections),
            'related_collections': three_related_collections,
            'rc_page': queryParams['rc_page']
        })

def collectionsDirectory(request):
    solr_collections = CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY)
    collections = []

    page = int(request.GET['page']) if 'page' in request.GET else 1

    for collection_link in solr_collections.shuffled[(page-1)*10:page*10]:
        collections.append(getCollectionMosaic(collection_link.url))
    
    context = {'collections': collections, 'random': True, 'pages': int(math.ceil(float(len(solr_collections.shuffled))/10))}

    if page*10 < len(solr_collections.shuffled):
        context['next_page'] = page+1
    if page-1 > 0:
        context['prev_page'] = page-1

    return render(request, 'calisphere/collectionsRandomExplore.html', context)

def collectionsAZ(request, collection_letter):
    solr_collections = CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY)
    collections_list = solr_collections.split[collection_letter.lower()]
    
    page = int(request.GET['page']) if 'page' in request.GET else 1
    pages = int(math.ceil(float(len(collections_list))/10))

    collections = []
    for collection_link in collections_list[(page-1)*10:page*10]:
        collections.append(getCollectionMosaic(collection_link.url))
    
    alphabet = list((character, True if character.lower() not in solr_collections.no_collections else False) for character in list(string.ascii_uppercase))
    
    context = {'collections': collections,
        'alphabet': alphabet,
        'collection_letter': collection_letter, 
        'page': page,
        'pages': pages,
    }

    if page*10 < len(collections_list):
        context['next_page'] = page+1
    if page-1 > 0:
        context['prev_page'] = page-1

    return render(request, 'calisphere/collectionsAZ.html', context)

def collectionsSearch(request):
    return render(request, 'calisphere/collectionsTitleSearch.html', {'collections': [], 'collection_q': True})

def themedCollections(request):
    return render(request, 'calisphere/collectionsThemedCollections.html', {'themedCollections': True})

def collectionView(request, collection_id):
    collection_url = 'https://registry.cdlib.org/api/v1/collection/' + collection_id + '/?format=json'
    collection_details = json_loads_url(collection_url)
    for repository in collection_details['repository']:
        repository['resource_id'] = repository['resource_uri'].split('/')[-2]

    # if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
    queryParams = processQueryRequest(request)
    collection = getCollectionData(collection_id=collection_id)
    fq = solrize_filters(queryParams['filters'])
    fq.append('collection_url: "' + collection['url'] + '"')
        
    facet_fields = list(facet_type[0] for facet_type in FACET_TYPES if facet_type[0] != 'collection_data')

    # perform the search
    solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows=queryParams['rows'],
        start=queryParams['start'],
        sort=solrize_sort(queryParams['sort']),
        fq=fq,
        facet='true',
        facet_mincount=1,
        facet_limit='-1',
        facet_field=facet_fields
    )
    
    facets = facetQuery(facet_fields, queryParams, solr_search, 'collection_url: "' + collection['url'] + '"')

    for i, facet_item in enumerate(facets['repository_data']):
        repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
        facets['repository_data'][i] = repository

    filter_display = {}
    for filter_type in queryParams['filters']:
        if filter_type == 'collection_data':
            filter_display['collection_data'] = []
        elif filter_type == 'repository_data':
            filter_display['repository_data'] = []
            for filter_item in queryParams['filters'][filter_type]:
                repository = getRepositoryData(repository_data=filter_item)
                filter_display['repository_data'].append(repository)
        else:
            filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

    return render(request, 'calisphere/collectionView.html', {
        'q': queryParams['q'],
        'rq': queryParams['rq'],
        'filters': filter_display,
        'rows': queryParams['rows'],
        'start': queryParams['start'],
        'sort': queryParams['sort'],
        'search_results': solr_search.results,
        'facets': facets,
        'FACET_TYPES': list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES if facet_type[0] != 'collection_data' and facet_type[0] != 'repository_data'),
        'numFound': solr_search.numFound,
        'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
        'view_format': queryParams['view_format'],
        'collection': collection_details,
        'collection_id': collection_id,
        'form_action': reverse('calisphere:collectionView', kwargs={'collection_id': collection_id})
    })

def campusDirectory(request):
    repositories_solr_query = SOLR_select(q='*:*', rows=0, start=0, facet='true', facet_mincount=1, facet_field=['repository_data'], facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields']['repository_data']

    repositories = []
    for repository_data in solr_repositories:
        repository = getRepositoryData(repository_data=repository_data)
        if repository['campus']:
            repositories.append({
                'name': repository['name'],
                'campus': repository['campus'],
                'repository_id': re.match(r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?', repository['url']).group('repository_id')
            })

    repositories = sorted(repositories, key=lambda repository: (repository['campus'], repository['name']))
    # Use hard-coded campus list so UCLA ends up in the correct order
    # campuses = sorted(list(set([repository['campus'] for repository in repositories])))

    return render(request, 'calisphere/campusDirectory.html', {'repositories': repositories,
        'campuses': CAMPUS_LIST})

def statewideDirectory(request):
    repositories_solr_query = SOLR_select(q='*:*', rows=0, start=0, facet='true', facet_mincount=1, facet_field=['repository_data'], facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields']['repository_data']
    
    repositories = []
    for repository_data in solr_repositories:
        repository = getRepositoryData(repository_data=repository_data)
        if repository['campus'] == '':
            repositories.append({
                'name': repository['name'],
                'repository_id': re.match(r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?', repository['url']).group('repository_id')
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
            binned_repositories.append({char: bin})

    return render(request, 'calisphere/statewideDirectory.html', {'state_repositories': binned_repositories})


def institutionView(request, institution_id, subnav=False, institution_type='repository|campus'):
    institution_url = 'https://registry.cdlib.org/api/v1/' + institution_type + '/' + institution_id + '/'
    institution_details = json_loads_url(institution_url + "?format=json")
    
    if 'ark' in institution_details and institution_details['ark'] != '':
        contact_information = json_loads_url("http://dsc.cdlib.org/institution-json/" + institution_details['ark'])
    else:
        contact_information = ''
    
    if 'campus' in institution_details and len(institution_details['campus']) > 0:
        uc_institution = institution_details['campus']
    else:
        uc_institution = False
        
    if subnav == 'items':
        queryParams = processQueryRequest(request)
    
        fq = solrize_filters(queryParams['filters'])
    
        if institution_type == 'repository':
            fq.append('repository_url: "' + institution_url + '"')
            facet_fields = list(facet_type[0] for facet_type in FACET_TYPES if facet_type[0] != 'repository_data')
        
        if institution_type == 'campus':
            fq.append('campus_url: "' + institution_url + '"')
            facet_fields = list(facet_type[0] for facet_type in FACET_TYPES)
        
        solr_search = SOLR_select(
            q=queryParams['query_terms'],
            rows=queryParams['rows'],
            start=queryParams['start'],
            sort=solrize_sort(queryParams['sort']),
            fq=fq,
            facet='true',
            facet_mincount=1,
            facet_limit='-1',
            facet_field=facet_fields
        )
        
        if institution_type == 'repository':
            facets = facetQuery(facet_fields, queryParams, solr_search, 'repository_url: "' + institution_url + '"')
        elif institution_type == 'campus':
            facets = facetQuery(facet_fields, queryParams, solr_search, 'campus_url: "' + institution_url + '"')
        else:
            facets = facetQuery(facet_fields, queryParams, solr_search)

        for i, facet_item in enumerate(facets['collection_data']):
            collection = (getCollectionData(collection_data=facet_item[0]), facet_item[1])
            facets['collection_data'][i] = collection
    
        if institution_type == 'campus':
            for i, facet_item in enumerate(facets['repository_data']):
                repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
                facets['repository_data'][i] = repository
    
        filter_display = {}
        for filter_type in queryParams['filters']:
            if filter_type == 'repository_data':
                filter_display['repository_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    repository = getRepositoryData(repository_data=filter_item)
                    filter_display['repository_data'].append(repository)
            elif filter_type == 'collection_data':
                filter_display['collection_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    collection = getCollectionData(collection_data=filter_item)
                    filter_display['collection_data'].append(collection)
            else:
                filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])
    
        context = {
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': filter_display,
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'sort': queryParams['sort'],
            'search_results': solr_search.results,
            'facets': facets,
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
            'view_format': queryParams['view_format'],
            'institution': institution_details,
            'contact_information': contact_information,
        }
    
        if institution_type == 'campus': 
            context['FACET_TYPES'] = list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES)
            context['campus_slug'] = institution_details['slug']
            context['form_action'] = reverse('calisphere:campusView', kwargs={'campus_slug': institution_details['slug'], 'subnav': 'items'})
            for campus in CAMPUS_LIST:
                if institution_id == campus['id'] and 'featuredImage' in campus:
                    context['featuredImage'] = campus['featuredImage']
        
        if institution_type == 'repository':
            context['FACET_TYPES'] = list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES if facet_type[0] != 'repository_data')
            context['repository_id'] = institution_id
            context['uc_institution'] = uc_institution
            context['form_action'] = reverse('calisphere:repositoryView', kwargs={'repository_id': institution_id, 'subnav': 'items'})
            
            if uc_institution == False:
                for unit in FEATURED_UNITS:
                    if unit['id'] == institution_id:
                        context['featuredImage'] = unit['featuredImage']
            
            
        return render(request, 'calisphere/institutionViewItems.html', context)

    else:
        page = int(request.GET['page']) if 'page' in request.GET else 1
        
        if institution_type == 'repository':      
            institutions_fq = ['repository_url: "' + institution_url + '"']
        if institution_type == 'campus':
            institutions_fq = ['campus_url: "' + institution_url + '"']
    
        collections_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=institutions_fq,
            facet='true',
            facet_mincount=1,
            facet_limit='-1',
            facet_field=['collection_data']
        )

        pages = int(math.ceil(float(len(collections_solr_search.facet_counts['facet_fields']['collection_data']))/10))

        collections_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=institutions_fq,
            facet='true',
            facet_mincount=1,
            facet_offset=(page-1)*10,
            facet_limit='10',
            facet_field = ['collection_data']
        )
    
        related_collections = list(collection[0] for collection in process_facets(collections_solr_search.facet_counts['facet_fields']['collection_data'], []))

        for i, related_collection in enumerate(related_collections):
            collection_data = getCollectionData(collection_data=related_collection)
            related_collections[i] = getCollectionMosaic(collection_data['url'])
    
        context = {
            'page': page,
            'pages': pages,
            'collections': related_collections,
            'contact_information': contact_information,
            'institution': institution_details,
        }
    
        if page+1 <= pages:
            context['next_page'] = page+1
        if page-1 > 0:
            context['prev_page'] = page-1

        if institution_type == 'campus':
            context['campus_slug'] = institution_details['slug']
            for campus in CAMPUS_LIST:
                if institution_id == campus['id'] and 'featuredImage' in campus:
                    context['featuredImage'] = campus['featuredImage']
        if institution_type == 'repository':
            context['repository_id'] = institution_id
            context['uc_institution'] = uc_institution
            
            if uc_institution == False:
                for unit in FEATURED_UNITS:
                    if unit['id'] == institution_id:
                        context['featuredImage'] = unit['featuredImage']
            

        return render(request, 'calisphere/institutionViewCollections.html', context)

def campusView(request, campus_slug, subnav=False):
    campus_id = ''
    featured_image = ''
    for campus in CAMPUS_LIST:
        if campus_slug == campus['slug']:
            campus_id = campus['id']
            if 'featuredImage' in campus:
                featured_image = campus['featuredImage']
    if campus_id == '':
        print "Campus registry ID not found"

    if subnav == 'institutions':
        campus_url = 'https://registry.cdlib.org/api/v1/campus/' + campus_id + '/'
        campus_details = json_loads_url(campus_url + "?format=json")
    
        if 'ark' in campus_details and campus_details['ark'] != '':
            contact_information = json_loads_url("http://dsc.cdlib.org/institution-json/" + campus_details['ark'])
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
            facet_field = ['repository_data']
        )

        related_institutions = list(institution[0] for institution in process_facets(institutions_solr_search.facet_counts['facet_fields']['repository_data'], []))

        for i, related_institution in enumerate(related_institutions):
            related_institutions[i] = getRepositoryData(repository_data=related_institution)

        return render(request, 'calisphere/institutionViewInstitutions.html', {
            'featuredImage': featured_image,
            'campus_slug': campus_slug,
            'institutions': related_institutions,
            'institution': campus_details,
            'contact_information': contact_information
        })

    else:
        return institutionView(request, campus_id, subnav, 'campus')

def repositoryView(request, repository_id, subnav=False):
    return institutionView(request, repository_id, subnav, 'repository')

def _fixid(id):
    return re.sub(r'^(\d*--http:/)(?!/)', r'\1/', id)
