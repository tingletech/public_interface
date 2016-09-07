import os
import gzip
import shutil
from django.template import loader
from django.conf import settings
from django.contrib.sitemaps import Sitemap as RegularDjangoSitemap
from static_sitemaps.generator import SitemapGenerator
from static_sitemaps import conf
from xml.etree.ElementTree import Element, SubElement, ElementTree
from six import BytesIO

class CalisphereSitemapGenerator(SitemapGenerator):
    ''' subclass django-static-sitemaps '''
    def __init__(self, verbosity):
        SitemapGenerator.__init__(self, verbosity)
        self.baseurl = self.normalize_url(conf.get_url())

    def write_index(self):
        ''' write sitemap.xml index file and the sitemap files it references ''' 
        parts = []

        for section, site in self.sitemaps.items():
            if issubclass(site, RegularDjangoSitemap): 
                parts.extend(self.write_data_regular(section, site))
            else:
                parts.extend(self.write_data_fast(section, site))

        path = os.path.join(conf.ROOT_DIR, 'sitemap.xml')
        self.out('Writing index file.', 2)

        output = loader.render_to_string(conf.INDEX_TEMPLATE, {'sitemaps': parts})
        self._write(path, output)


    def write_data_regular(self, section, site):
        ''' process regular Django sitemap, which assumes list data '''
        if callable(site):
            pages = site().paginator.num_pages
        else:
            pages = site.paginator.num_pages

        parts = []
        for page in range(1, pages + 1):
            filename = conf.FILENAME_TEMPLATE % {'section': section,
                                                 'page': page}
            lastmod = self.write_page(site, page, filename)

            if conf.USE_GZIP:
                filename += '.gz'

            parts.append({
                'location': '%s%s' % (self.baseurl, filename),
                'lastmod': lastmod
            })

        return parts

    def write_data_fast(self, section, site):
        ''' process data using generator and streaming xml ''' 
        items = site().items() # generator yielding all items

        parts = []

        for page in xrange(site().num_pages):
            filename = conf.FILENAME_TEMPLATE % {'section': section, 'page': page + 1}
            self.out('Writing sitemap %s' % filename, 2)
            path = os.path.join(conf.ROOT_DIR, filename)
            with open(path, 'w+') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>')
                f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">')
                for n in xrange(site().limit):
                    # https://pymotw.com/2/xml/etree/ElementTree/create.html#serializing-xml-to-a-stream
                    item = next(items)
                    url = Element('url')
                    loc = SubElement(url, 'loc')
                    loc.text = u'https://calisphere.org/item/{0}/'.format(item['id']) # TODO: use location
                    # <lastmod>
                    # <changefreq>
                    # <priority>
                    if item['reference_image_md5']:
                        image = SubElement(url, 'image:image')
                        imageloc = SubElement(image, 'image:loc')
                        imageloc.text = u'https://calisphere.org/crop/999x999/{0}'.format(item['reference_image_md5'])
                    ElementTree(url).write(f)
                f.write('</urlset>')
 
            if conf.USE_GZIP:
                self.compress(path)
                filename += '.gz'
            # implement lastmod?
            parts.append({'lastmod': None, 'location': '{}{}'.format(self.baseurl, filename)})

        return parts

    def compress(self, path):
        self.out('Compressing...')
        with open(path, 'rb') as f_in, gzip.open('{}.gz'.format(path), 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
