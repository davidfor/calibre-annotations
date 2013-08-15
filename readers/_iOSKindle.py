#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import os, re, sqlite3

from cStringIO import StringIO

from calibre.ebooks.BeautifulSoup import UnicodeDammit

from calibre_plugins.annotations.reader_app_support import iOSReaderApp
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct,
    UnknownAnnotationTypeException)


class KindleReaderApp(iOSReaderApp):
    """
    Kindle for iOS implementation
    Books are stored in BookData.sqlite
    Annotations are stored in AnnotationStorage.
    Three types:
        highlight (always yellow)
        note (no highlight text)
        lpr (last position read?)
    """

    # Reader-specific characteristics
    annotations_subpath = '/Library/AnnotationStorage'
    app_name = 'Kindle'
    books_subpath = '/Library/Preferences/BookData.sqlite'
    HIGHLIGHT_COLORS = ['Yellow']
    SUPPORTS_FETCHING = True

    ''' Class overrides '''
    def get_active_annotations(self):
        '''
        Kindle for iOS handles notes a bit differently. To add a note to a highlight,
        first create the highlight, then tap it to add a note.
        In the AnnotationStorage db, highlight/note pairs created in this fashion will
        have the same ZRAWEND and ZRAWPOSITION values. Also, a note like this can only
        be attached to a highlight that already exists. So only when parsing a note
        do we need to check to see if a companion highlight exists.
        One other annoyance is that there doesn't seem to be a timestamp for highlights.
        BookData.sqlite has ZRAWLASTACCESSTIME, which is as close as I can get to a timestamp.
        '''

        self._log("%s:get_active_annotations()" % (self.app_name))

        self.opts.pb.set_label("Getting active annotations for %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id, self.annotations_subpath)
        remote_annotations_db = db_profile['path']
        ra_db_path_stats = db_profile['stats']

        db_profile = self._localize_database_path(self.app_id, self.books_subpath)
        remote_books_db = db_profile['path']

        # Test timestamp against cached value
        cached_db = self.generate_annotations_db_name(self.app_name_, self.ios.device_name)
        books_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        if self.opts.disable_caching or not self._cache_is_current(ra_db_path_stats, cached_db):
            self._log(" fetching annotations from %s on %s" % (self.app_name, self.ios.device_name))

            # Create the annotations table as needed
            self.create_annotations_table(cached_db)

            annotations = {}

            con_a = sqlite3.connect(remote_annotations_db)
            con_a.row_factory = sqlite3.Row
            con_b = sqlite3.connect(remote_books_db)
            con_b.row_factory = sqlite3.Row

            with con_a:
                cur = con_a.cursor()
                cur.execute('''SELECT
                                ZRAWANNOTATIONTYPE,
                                Z_PK,
                                ZRAWEND,
                                ZRAWPOSITION,
                                ZRAWSTART,
                                ZRAWBOOKID,
                                ZUSERTEXT
                               FROM ZANNOTATION
                            ''')
                rows = cur.fetchall()

                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()
                    book_id = row[b'ZRAWBOOKID']
                    if not book_id in self.installed_books:
                        continue

                    annotation_type = row[b'ZRAWANNOTATIONTYPE']
                    if annotation_type == 'lpr':
                        continue
                    if annotation_type not in ['highlight', 'note']:
                        raise UnknownAnnotationTypeException(annotation_type)

                    # Collect the metadata
                    highlight_color = None
                    highlight_text = None
                    note_text = None

                    # Get the last accessed timestamp from BookData
                    with con_b:
                        cur_b = con_b.cursor()
                        cur_b.execute('''
                                      SELECT
                                       ZRAWLASTACCESSTIME
                                      FROM ZBOOK
                                      WHERE ZBOOKID = '{0}'
                                      '''.format(book_id))
                        ans = cur_b.fetchone()
                    timestamp = ans[b'ZRAWLASTACCESSTIME']

                    # Sanitize ZUSERTEXT to unicode
                    highlight_text = re.sub('\xa0', ' ', row[b'ZUSERTEXT'])
                    highlight_text = UnicodeDammit(highlight_text).unicode
                    highlight_text = highlight_text.rstrip('\n').split('\n')
                    while highlight_text.count(''):
                        highlight_text.remove('')
                    highlight_text = [line.strip() for line in highlight_text]
                    highlight_text = '\n'.join(highlight_text)

                    if annotation_type == 'highlight':
                        highlight_color = 'Yellow'
                    elif annotation_type == 'note':
                        note_text = unicode(highlight_text)
                        highlight_text = None
                        highlight_color = 'Yellow'
                    annotation_id = row[b'Z_PK']

                    # If note, check to see if there's a peer highlight already captured
                    companion_found = False
                    if annotation_type == 'note':
                        for ts in annotations:
                            if annotations[ts]['ZRAWEND'] == row[b'ZRAWEND'] and \
                                annotations[ts]['ZRAWPOSITION'] == row[b'ZRAWPOSITION']:
                                annotations[ts]['note_text'] = note_text
                                companion_found = True
                                break

                    if not companion_found:
                        # Store the annotation locally
                        while timestamp in annotations:
                            timestamp += 1

                        annotations[timestamp] = dict(
                            annotation_id=annotation_id,
                            book_id=book_id,
                            highlight_color=highlight_color,
                            highlight_text=highlight_text,
                            last_modification=timestamp,
                            location="Location %d" % (int(row[b'ZRAWSTART'] / 150) + 1),
                            location_sort="%06d" % (int(row[b'ZRAWSTART'] / 150) + 1),
                            note_text=note_text,
                            ZRAWEND=row[b'ZRAWEND'],
                            ZRAWPOSITION=row[b'ZRAWPOSITION']
                            )

                    # Update last_annotation in books_db
                    self.update_book_last_annotation(books_db, timestamp, book_id)

                # Write the annotations
                for timestamp in annotations:
                    ann_mi = AnnotationStruct()

                    # Required items
                    ann_mi.book_id = annotations[timestamp]['book_id']
                    ann_mi.last_modification = timestamp

                    # Optional items
                    ann_mi.annotation_id = annotations[timestamp]['annotation_id']
                    ann_mi.highlight_color = annotations[timestamp]['highlight_color']
                    ann_mi.highlight_text = annotations[timestamp]['highlight_text']
                    ann_mi.location = annotations[timestamp]['location']
                    ann_mi.location_sort = annotations[timestamp]['location_sort']
                    ann_mi.note_text = annotations[timestamp]['note_text']

                    # Add annotation to self.annotations_db
                    self.add_to_annotations_db(cached_db, ann_mi)

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.opts.conn.commit()

        else:
            self._log(" retrieving cached annotations from %s" % cached_db)

    def get_installed_books(self):
        """
        Fetch installed books from mainDb.sqlite or cached_db
        """
        self._log("%s:get_installed_books(%s)" % (self.__class__.__name__, self.app_name))

        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id, self.books_subpath)
        remote_books_db = db_profile['path']

        cached_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        # Test timestamp against cached value
        if self.opts.disable_caching or not self._cache_is_current(db_profile['stats'], cached_db):
            # (Re)load installed books from device
            self._log(" fetching installed books from %s on %s" % (self.app_name, self.ios.device_name))

            # Mount the ios container
            self.ios.mount_ios_app(app_id=self.app_id)

            installed_books = set([])

            # Create the books table as needed
            self.create_books_table(cached_db)

            con = sqlite3.connect(remote_books_db)
            with con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT ZDISPLAYAUTHOR,
                                      ZDISPLAYTITLE,
                                      ZPATH,
                                      ZBOOKID
                               FROM ZBOOK
                               WHERE ZBOOKID LIKE 'L:%'
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    book_id = row[b'ZBOOKID']
                    installed_books.add(book_id)
                    path = self._fix_Kindle_path(row[b'ZPATH'])
                    mi = self._get_metadata(path)
                    book_mi = BookStruct()
                    book_mi.path = path
                    # Required items
                    book_mi.active = True

                    # Massage last, first authors back to normalcy
                    book_mi.author = ''
                    for i, author in enumerate(mi.authors):
                        this_author = author.split(', ')
                        this_author.reverse()
                        book_mi.author += ' '.join(this_author)
                        if i < len(mi.authors) - 1:
                            book_mi.author += ' & '

                    book_mi.book_id = book_id
                    book_mi.reader_app = self.app_name
                    book_mi.title = mi.title

                    # Optional items
                    if hasattr(mi, 'author_sort'):
                        book_mi.author_sort = mi.author_sort
                    if getattr(mi, 'title_sort', None) is not None:
                        book_mi.title_sort = mi.title_sort
                    else:
                        book_mi.title_sort = re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', mi.title).rstrip()
                    if hasattr(mi, 'uuid'):
                        book_mi.uuid = mi.uuid

                    if mi.tags:
                        book_mi.genre = ', '.join([tag for tag in mi.tags])

                    # Add book to self.books_db
                    self.add_to_books_db(cached_db, book_mi)
                    self.opts.pb.increment()

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.opts.conn.commit()

            installed_books = list(installed_books)

        else:
            self._log(" retrieving cached books from %s" % cached_db)
            installed_books = self._get_cached_books(cached_db)

        self.installed_books = installed_books

    ''' Helpers '''
    def _fix_Kindle_path(self, original_path):
        # Two storage locations: .../Documents or .../Library
        if 'Documents/' in original_path:
            partial_path = original_path[original_path.find('/Documents/'):]
        elif 'Library/' in original_path:
            partial_path = original_path[original_path.find('/Library/'):]
        return partial_path

    def _get_metadata(self, path):

        if False:
            from calibre.ebooks.metadata.mobi import MetadataUpdater
            mi = {'uuid': None, 'genre': None}
            mobi_file = None
            with open(os.path.join(self.mount_point, path), 'rb') as f:
                stream = StringIO(f.read())
                mobi_file = MetadataUpdater(stream)
            if 105 in mobi_file.original_exth_records:
                mi['genre'] = mobi_file.original_exth_records[105]
            if 112 in mobi_file.original_exth_records:
                mi['uuid'] = re.sub('calibre:', '', mobi_file.original_exth_records[112])
            return mi

        from calibre.ebooks.metadata.mobi import get_metadata
        f = StringIO(self.ios.read(path, mode='rb'))
        return get_metadata(f)
