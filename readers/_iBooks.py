#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import cStringIO, os, re, sqlite3

from lxml import etree

from calibre.ebooks.BeautifulSoup import UnicodeDammit

from calibre_plugins.annotations.reader_app_support import iOSReaderApp
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct,
    get_clippings_cid)


class iBooksReaderApp(iOSReaderApp):
    """
    iBooks implementation
    """

    # Reader-specific characteristics
    annotations_subpath = '/Documents/storeFiles/AEAnnotation_*.sqlite'
    app_name = 'iBooks'
    app_aliases = [b'com.apple.iBooks']
    books_subpath = '/Documents/BKLibrary_database/iBooks_*.sqlite'
    EPUBCFI_REGEX = r'epubcfi\(\/(?P<spine_loc>\d+)\/(?P<spine_index>\d+).*!\/(?P<interior>[\[\]\w\/]+),.*?:(?P<start>\d+),.*?:(?P<end>\d+)\)$'
    HIGHLIGHT_COLORS = ['Underline', 'Green', 'Blue', 'Yellow', 'Pink', 'Purple']
    SUPPORTS_FETCHING = True

    ''' Class overrides '''
    def get_active_annotations(self):
        """
        Fetch active iBooks annotations from AEAnnotation_*.sqlite
        """
        self._log("%s:get_active_annotations()" % self.app_name)

        self.opts.pb.set_label("Getting active annotations for %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id, self.annotations_subpath)
        self.annotations_db = db_profile['path']

        # Test timestamp against cached value
        cached_db = self.generate_annotations_db_name(self.app_name_, self.ios.device_name)
        books_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        if self.opts.disable_caching or not self._cache_is_current(db_profile['stats'], cached_db):
            self._log(" fetching annotations from %s on %s" % (self.app_name, self.ios.device_name))

            # Create the annotations table as needed
            self.create_annotations_table(cached_db)

            con = sqlite3.connect(self.annotations_db)
            with con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT
                                ZANNOTATIONASSETID,
                                ZANNOTATIONLOCATION,
                                ZANNOTATIONMODIFICATIONDATE,
                                ZANNOTATIONNOTE,
                                ZANNOTATIONSELECTEDTEXT,
                                ZANNOTATIONSTYLE,
                                ZANNOTATIONUUID
                               FROM ZAEANNOTATION
                               WHERE ZANNOTATIONDELETED = 0 and ZANNOTATIONTYPE = 2
                               ORDER BY ZANNOTATIONMODIFICATIONDATE
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()
                    book_id = row[b'ZANNOTATIONASSETID']
                    if not book_id in self.installed_books:
                        continue

                    # Collect the metadata

                    # Sanitize text, note to unicode
                    highlight_text = re.sub('\xa0', ' ', row[b'ZANNOTATIONSELECTEDTEXT'])
                    highlight_text = UnicodeDammit(highlight_text).unicode
                    highlight_text = highlight_text.rstrip('\n').split('\n')
                    while highlight_text.count(''):
                        highlight_text.remove('')
                    highlight_text = [line.strip() for line in highlight_text]

                    note_text = None
                    if row[b'ZANNOTATIONNOTE']:
                        note_text = UnicodeDammit(row[b'ZANNOTATIONNOTE']).unicode
                        note_text = note_text.rstrip('\n').split('\n')[0]

                    # Populate an AnnotationStruct
                    a_mi = AnnotationStruct()
                    a_mi.annotation_id = row[b'ZANNOTATIONUUID']
                    a_mi.book_id = book_id
                    a_mi.epubcfi = row[b'ZANNOTATIONLOCATION']
                    a_mi.highlight_color = self.HIGHLIGHT_COLORS[row[b'ZANNOTATIONSTYLE']]
                    a_mi.highlight_text = '\n'.join(highlight_text)
                    a_mi.last_modification = row[b'ZANNOTATIONMODIFICATIONDATE'] + self.NSTimeIntervalSince1970
                    if a_mi.epubcfi:
                        section = self._get_spine_index(a_mi.epubcfi)
                        try:
                            a_mi.location = self.tocs[book_id]["%.0f" % (section - 1)]
                        except:
                            a_mi.location = "Section %d" % section
                        if self.collect_news_clippings and 'News' in self.get_genres(books_db, book_id):
                            a_mi.location_sort = a_mi.last_modification
                        else:
                            a_mi.location_sort = self._generate_location_sort(a_mi.epubcfi)
                    else:
                        if self.collect_news_clippings and 'News' in self.get_genres(books_db, book_id):
                            a_mi.location = self.get_title(books_db, book_id)
                            a_mi.location_sort = a_mi.last_modification

                    a_mi.note_text = note_text

                    # Add annotation
                    self.add_to_annotations_db(cached_db, a_mi)

                    # Update last_annotation in books_db
                    self.update_book_last_annotation(books_db,
                                                 row[b'ZANNOTATIONMODIFICATIONDATE'] + self.NSTimeIntervalSince1970,
                                                 book_id)

                self.update_timestamp(cached_db)
                self.commit()

        else:
            self._log(" retrieving cached annotations from %s" % cached_db)

    def get_installed_books(self):
        """
        Fetch installed books from iBooks_*.sqlite or cache
        """
        self._log("%s:get_installed_books()" % self.app_name)

        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id,  self.books_subpath)
        self.books_db = db_profile['path']

        cached_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        # Test timestamp against cached value
        if self.opts.disable_caching or not self._cache_is_current(db_profile['stats'], cached_db):
            # (Re)load installed books from device
            self._log(" fetching installed books from %s on %s" % (self.app_name, self.ios.device_name))

            # Mount the Media folder
            self.ios.mount_ios_media_folder()

            installed_books = set([])
            self.tocs = {}

            # Create the books table as needed
            self.create_books_table(cached_db)

            con = sqlite3.connect(self.books_db)
            with con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT ZASSETURL,
                                      ZBOOKAUTHOR,
                                      ZSORTAUTHOR,
                                      ZBOOKTITLE,
                                      ZSORTTITLE,
                                      ZDATABASEKEY
                               FROM ZBKBOOKINFO
                               WHERE ZASSETURL LIKE 'file://localhost%' AND
                                     ZASSETURL LIKE '%.epub/'
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()
                    this_is_news = False

                    path = self._fix_iBooks_path(row[b'ZASSETURL'])
                    mi = self._get_metadata(path, row[b'ZBOOKTITLE'])
                    genres = mi['genre'].split(', ')
                    if 'News' in genres:
                        if not self.collect_news_clippings:
                            continue
                        this_is_news = True

                    book_id = row[b'ZDATABASEKEY']
                    installed_books.add(book_id)

                    # Populate a BookStruct
                    b_mi = BookStruct()
                    b_mi.active = True
                    b_mi.author = row[b'ZBOOKAUTHOR']
                    b_mi.author_sort = row[b'ZSORTAUTHOR']
                    b_mi.book_id = book_id
                    b_mi.genre = mi['genre']
                    b_mi.title = row[b'ZBOOKTITLE']
                    b_mi.title_sort = row[b'ZSORTTITLE']
                    b_mi.uuid = mi['uuid']

                    # Add book to books_db
                    self.add_to_books_db(cached_db, b_mi)

                    # Get the library cid, confidence
                    toc_entries = None
                    if this_is_news:
                        cid = self.news_clippings_cid
                        confidence = 5
                        if path is not None:
                            toc_entries = self._get_epub_toc(path=path, prepend_title=b_mi.title)
                    elif self.ios.exists(path):
                            cid, confidence = self.parent.generate_confidence(b_mi)
                            if confidence >= 2:
                                toc_entries = self._get_epub_toc(cid=cid, path=path)
                            elif path is not None:
                                toc_entries = self._get_epub_toc(path=path)
                    self.tocs[book_id] = toc_entries

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.commit()

            self.ios.dismount_ios_media_folder()
            installed_books = list(installed_books)

        else:
            self._log(" retrieving cached books from %s" % cached_db)
            installed_books = self._get_cached_books(cached_db)

        self.installed_books = installed_books

    ''' Helpers '''
    def _fix_iBooks_path(self, original_path):
        path = original_path[original_path.find('Media/') + len('Media'):-1]
        path = path.replace('%20', ' ')
        return str(path)

    def _get_spine_index(self, epubcfi):
        '''
        Given an epubcfi, generate a location string
        epubcfi(/6/60[id1247]!/4/10/2/1,:0,:26)
        '''
        match = re.match(self.EPUBCFI_REGEX, epubcfi)
        spine_index = 0
        if match:
            spine_index = int(match.group('spine_index')) / 2
        return spine_index

    def _generate_location_sort(self, epubcfi):
        '''
        Given an epubcfi, generate a location_sort string
        epubcfi(/6/60[id1247]!/4/10/2/1,:0,:26)
        '''
        match = re.match(self.EPUBCFI_REGEX, epubcfi)
        if match:
            spine_index = int(match.group('spine_index')) / 2
            start = int(match.group('start'))

            # Parse interior
            steps = match.group('interior').split('/')
            steps = [re.sub(r'\[\w+\]','', step) for step in steps]
            steps = [int(s) / 2 for s in steps[:-1]]

            # Populate the ladder
            full_ladder = steps
            if len(full_ladder) < self.MAX_ELEMENT_DEPTH:
                for x in range(len(steps), self.MAX_ELEMENT_DEPTH):
                    full_ladder.append(0)
            else:
                full_ladder = full_ladder[:self.MAX_ELEMENT_DEPTH]

            str_fmt = '.'.join(["%04d"] * self.MAX_ELEMENT_DEPTH)
            middle = str_fmt % tuple(full_ladder)
            result = "%04d.%s.%04d" % (spine_index, middle, start)
            return result
        else:
            print("problem parsing epubcfi: %s" % epubcfi)
            import traceback
            traceback.print_exc()
            return 0

    def _get_metadata(self, path, title):
        mi = {'uuid': None, 'genre': ''}

        OPF_path = None
        container = '/'.join([path, 'META-INF', 'container.xml'])
        if self.ios.exists(container):
            f = cStringIO.StringIO(self.ios.read(container))
            tree = etree.parse(f).getroot()
            #self._log(etree.tostring(tree, pretty_print=True))
            rootfiles = tree[0]
            rootfile = rootfiles[0]
            OPF_path = '/'.join([path, rootfile.get('full-path')])

        if OPF_path and self.ios.exists(OPF_path):
            f = cStringIO.StringIO(self.ios.read(OPF_path))
            opf_tree = etree.parse(f).getroot()

            if False:
                # This works without depending on calibre
                identifiers = opf_tree.xpath('*[local-name()="metadata"]/*[local-name()="identifier"]')
                for elem in identifiers:
                    for key in elem.attrib:
                        if key.endswith('scheme') and elem.attrib[key] == 'calibre':
                            uuid_id = elem.text
                            break
                    if uuid_id is not None:
                        break
            else:
                # More robust, needs access to calibre namespaces
                from calibre.ebooks.oeb.base import OPF2_NSMAP
                uuid_el = opf_tree.xpath('//dc:identifier[@opf:scheme="calibre"]', namespaces=OPF2_NSMAP)
                if len(uuid_el):
                    mi['uuid'] = uuid_el[0].text

                subject_el = opf_tree.xpath('//dc:subject', namespaces=OPF2_NSMAP)
                if len(subject_el):
                    subjects = [el.text for el in subject_el]
                    mi['genre'] = ', '.join(subjects)

        else:
            self._log_location("unable to locate OPF file")
            self._log("  title: '%s'" % title)
            self._log("   path: %s" % path)

        return mi
