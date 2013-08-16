#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import os, re, sqlite3

from lxml import etree, html

from calibre.ebooks.BeautifulSoup import UnicodeDammit
from calibre.gui2 import Application

from calibre_plugins.annotations.reader_app_support import iOSReaderApp
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct,
    get_clippings_cid)


class MarvinReaderApp(iOSReaderApp):
    """
    Marvin implementation
    """

    # Reader-specific characteristics
    annotations_subpath = '/Library/mainDb.sqlite'
    app_name = 'Marvin'
    app_aliases = [b'com.appstafarian.Marvin', b'com.appstafarian.MarvinIP']
    books_subpath = '/Library/mainDb.sqlite'
    HIGHLIGHT_COLORS = ['Pink', 'Yellow', 'Blue', 'Green', 'Purple']

    import_dialog_title = "Import Marvin annotations"
    # import_help_text
    if True:
        import_help_text = ('''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>Exporting from Marvin</title>
            <style type="text/css">
                body {
                font-family:Tahoma, Geneva, sans-serif;
                font-size:medium;
                }
                div.steps_with_header h3 {
                    margin:0;
                }
                div.steps_with_header ol, ul {
                    margin-top:0;
                }
                div.steps_with_header_indent p {
                    margin:0 0 0 1em;
                }
                div.steps_with_header_indent ol, ul {
                    margin-left:1em;
                    margin-top:0;
                }
                h2, h3 {
                    font-family:Tahoma, Geneva, sans-serif;
                    text-align: left;
                    font-weight: normal;
                }
            </style>
            </head>
            <body>
                <h2 style="text-align:center">Exporting Marvin annotations</h2>
                <h3>Exporting annotations from a single book:</h3>
                <div class="steps_with_header_indent">
                  <p><i>From within an open book:</i></p>
                  <ol>
                    <li>Tap <b>Table of Contents</b> (book icon at top left)</li>
                    <li>Tap <b>Share</b> (arrow icon at top right)</li>
                    <li>Tap <b>Export Annotations</b>, then email the annotations file to yourself</li>
                  </ol>
                </div>
                <div class="steps_with_header_indent">
                  <p><i>From the Library screen in Marvin:</i></p>
                  <ol>
                    <li>Slide the book to the left, then tap <b>Share</b></li>
                    <li>Tap <b>Export Annotations</b></li>
                    <li>Email the annotations file to yourself</li>
                  </ol>
                </div>
                <div class="steps_with_header_indent">
                  <p><i>After receiving the emailed annotations file on your computer:</i></p>
                  <ol start="4">
                    <li>Drag the exported annotations file to the <b>Import Marvin annotations</b> window</li>
                    <li>Click <b>Import</b></li>
                  </ol>
                </div>

                <hr width="80%" />

                <div class="steps_with_header">
                    <h3>Exporting all annotations:</h3>
                    <ol>
                        <li>In the Marvin Home screen tap <b>Settings</b> (gear icon at top left)</li>
                        <li>Choose the <b>Services</b> tab, then swipe left to the Calibre icon</li>
                    </ol>
                </div>
                <div class="steps_with_header_indent">
                  <p><i>Via Email:</i></p>
                  <ol start="3">
                      <li>Tap the <b>Export File</b> button, then choose <b>Email</b></li>
                      <li>Email the annotations to yourself</li>
                      <li>Drag the received annotations file to the <b>Import Marvin annotations</b> window</li>
                      <li>Click <b>Import</b></li>
                  </ol>
                </div>
                <div class="steps_with_header_indent">
                  <p><i>Via iTunes:</i></p>
                  <ol start="3">
                      <li>Tap the <b>Export File</b> button, then choose <b>Documents directory</b></li>
                      <li>In iTunes, select your connected iDevice in the <b>DEVICES</b> menu</li>
                      <li>Click the <b>Apps</b> tab</li>
                      <li>Scroll down to <b>File Sharing</b>, then select Marvin in the <b>Apps</b> list</li>
                      <li>Drag <tt>library.mrvi</tt> from <b>Marvin Documents</b> to your desktop</li>
                      <li>Drag <tt>library.mrvi</tt> from your desktop to the <b>Import Marvin annotations</b> window</li>
                      <li>Click <b>Import</b></li>
                  </ol>
                </div>
            </body>
            </html>''')

    import_fingerprint = True
    initial_dialog_text = "Drag an exported {0} annotations file (*.mrv, *.mrvi) to this window".format(app_name)
    SUPPORTS_EXPORTING = True
    SUPPORTS_FETCHING = True

    ''' Class overrides '''

    def get_active_annotations(self):

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
            obsolete_bookmarks = 0
            deleted_bookmarks = 0

            con = sqlite3.connect(self.annotations_db)
            with con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT * FROM Highlights
                               ORDER BY NoteDateTime
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()

                    book_id = row[b'BookID']
                    if not book_id in self.installed_books:
                        obsolete_bookmarks += 1
                        continue

                    # Collect the markup/highlight count for all installed books
                    if row[b'Deleted'] == 1:
                        deleted_bookmarks += 1
                        continue

                    this_is_news = self.collect_news_clippings and 'News' in self.get_genres(books_db, book_id)

                    # Sanitize text, note to unicode
                    highlight_text = re.sub('\xa0', ' ', row[b'Text'])
                    highlight_text = UnicodeDammit(highlight_text).unicode
                    highlight_text = highlight_text.rstrip('\n').split('\n')
                    while highlight_text.count(''):
                        highlight_text.remove('')
                    highlight_text = [line.strip() for line in highlight_text]

                    note_text = None
                    if row[b'Note']:
                        note_text = UnicodeDammit(row[b'Note']).unicode
                        note_text = note_text.rstrip('\n').split('\n')[0]

                    # Populate an AnnotationStruct
                    a_mi = AnnotationStruct()
                    a_mi.annotation_id = row[b'UUID']
                    a_mi.book_id = book_id
                    a_mi.highlight_color = self.HIGHLIGHT_COLORS[row[b'Colour']]
                    a_mi.highlight_text = '\n'.join(highlight_text)
                    a_mi.last_modification = row[b'NoteDateTime']

                    section = str(int(row[b'Section']) - 1)
                    try:
                        a_mi.location = self.tocs[book_id][section]
                    except:
                        if this_is_news:
                            a_mi.location = self.get_title(books_db, book_id)
                        else:
                            a_mi.location = "Section %s" % row[b'Section']

                    a_mi.note_text = note_text

                    # If empty highlight_text and empty note_text, not a useful annotation
                    if not highlight_text and not note_text:
                        continue

                    # Generate location_sort
                    if this_is_news:
                        a_mi.location_sort = row[b'NoteDateTime']
                    else:
                        interior = self._generate_interior_location_sort(row[b'StartXPath'])
                        if not interior:
                            self._log("Marvin: unable to parse xpath:")
                            self._log(row[b'StartXPath'])
                            self._log(a_mi)
                            continue

                        a_mi.location_sort = "%04d.%s.%04d" % (
                            int(row[b'Section']),
                            interior,
                            int(row[b'StartOffset']))

                    # Add annotation
                    self.add_to_annotations_db(cached_db, a_mi)

                    # Update last_annotation in books_db
                    self.update_book_last_annotation(books_db, row[b'NoteDateTime'], book_id)

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.commit()

        else:
            self._log(" retrieving cached annotations from %s" % cached_db)

    def get_installed_books(self):
        """
        Fetch installed books from mainDb.sqlite or cached_db
        Populate self.tocs: {book_id: {toc_entries} ...}
        """
        self._log("%s:get_installed_books()" % self.app_name)

        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id, self.books_subpath)
        self.books_db = db_profile['path']

        cached_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        if self.opts.disable_caching or not self._cache_is_current(db_profile['stats'], cached_db):
            # (Re)load installed books from device
            self._log(" fetching installed books from %s on %s" % (self.app_name, self.ios.device_name))

            # Mount the ios container
            self.ios.mount_ios_app(app_id=self.app_id)

            installed_books = set([])
            self.tocs = {}

            # Create the books table as needed
            self.create_books_table(cached_db)

            con = sqlite3.connect(self.books_db)
            with con:
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                cur.execute('''SELECT
                                  Author,
                                  AuthorSort,
                                  Title,
                                  CalibreTitleSort,
                                  FileName,
                                  Books.ID AS id_,
                                  UUID
                               FROM Books
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()
                    this_is_news = False

                    path = self._fix_Marvin_path(row[b'FileName'])
                    book_id = row[b'id_']

                    # Get the genre(s) for this book
                    genre_cur = con.cursor()
                    genre_cur.execute("""SELECT
                                            Subject
                                         FROM BookSubjects
                                         WHERE BookID = '{0}'
                                      """.format(book_id))
                    genres = None
                    genre_rows = genre_cur.fetchall()
                    if genre_rows is not None:
                        genres = ', '.join([genre[b'Subject'] for genre in genre_rows])
                    genre_cur.close()

                    if 'News' in genres:
                        if not self.collect_news_clippings:
                            continue
                        this_is_news = True

                    installed_books.add(book_id)

                    # Populate a BookStruct
                    b_mi = BookStruct()
                    b_mi.active = True
                    b_mi.author = row[b'Author']
                    b_mi.author_sort = row[b'AuthorSort']
                    b_mi.book_id = book_id
                    b_mi.genre = genres
                    b_mi.title = row[b'Title']
                    b_mi.title_sort = row[b'CalibreTitleSort']
                    b_mi.uuid = row[b'UUID']

                    # Add book to books_db
                    self.add_to_books_db(cached_db, b_mi)

                    # Get the library cid, confidence
                    toc_entries = None
                    if this_is_news:
                        cid = self.news_clippings_cid
                        confidence = 5
                        if path is not None:
                            toc_entries = self._get_epub_toc(path=path, prepend_title=b_mi.title)
                    else:
                        cid, confidence = self.parent.generate_confidence(b_mi)
                        if confidence >= 2:
                            toc_entries = self._get_epub_toc(cid=cid, path=path)
                        elif path is not None:
                            toc_entries = self._get_epub_toc(path=path)
                    self.tocs[book_id] = toc_entries

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.commit()

            self.ios.disconnect_idevice()

            installed_books = list(installed_books)

        else:
            # Load installed books from cache
            self._log(" retrieving cached books from %s" % cached_db)
            self.opts.pb.set_maximum(2)
            self.opts.pb.set_value(1)
            Application.processEvents()
            installed_books = self._get_cached_books(cached_db)

        self.installed_books = installed_books

    def parse_exported_highlights(self, raw, log_failure=True):
        """
        Extract highlights from .mrv, .mrvi file, add to db
        """
        # html parser flattens attributes to lower case
        # {.MRVI: local}
        xl = {
              'author': 'author',
              'authorsort': 'author_sort',
              'bookid': 'book_id',
              'calibretitlesort': 'title_sort',
              'title': 'title',
              'uuid': 'uuid',
              }

        def _process_individual_book(book):
            book_mi = BookStruct()
            book_mi['reader_app'] = self.app_name
            book_mi['cid'] = None
            for md in xl:
                book_mi[xl[md]] = book.get(md)
            book_mi['active'] = True
            book_mi['annotations'] = 0
            subjects = book.find('subjects')
            if subjects is not None:
                sl = [s.text for s in subjects]
                book_mi['genre'] = ', '.join(sl)

            this_is_news = False
            if 'News' in book_mi['genre']:
                if not self.collect_news_clippings:
                    return
                this_is_news = True

            # Get the last update, count active annotations
            last_update = 0
            hls = book.find('highlights')
            for hl in hls:
                this_ts = hl.get('datetime')
                if this_ts > last_update:
                    last_update = this_ts
                if hl.get('deleted') == '0':
                    book_mi['annotations'] += 1
            book_mi['last_update'] = float(last_update)

            # Get the library cid, confidence
            toc_entries = None
            if this_is_news:
                cid = self.news_clippings_cid
                confidence = 5
            else:
                cid, confidence = self.parent.generate_confidence(book_mi)
                if confidence >= 2:
                    toc_entries = self._get_epub_toc(cid=cid)

            # Add annotated book to the db, master_list
            if len(hls):
                self.add_to_books_db(self.books_db, book_mi)
                self.annotated_book_list.append(book_mi)

                # Add the active annotations for this book to the db
                highlights = {}
                for hl in hls:
                    if hl.get('deleted') == '1':
                        continue
                    datetime = hl.get('datetime')
                    highlights[datetime] = {}
                    for md in ['text', 'note', 'color', 'key', 'deleted', 'section',
                               'startx', 'startoffset']:
                        highlights[datetime][md] = hl.get(md)

                sorted_keys = sorted(highlights.iterkeys())
                for datetime in sorted_keys:
                    highlight_text = highlights[datetime]['text']
                    note_text = highlights[datetime]['note']

                    # Populate an AnnotationStruct
                    a_mi = AnnotationStruct()
                    a_mi.annotation_id = highlights[datetime]['key']
                    a_mi.book_id = book_mi['book_id']
                    a_mi.highlight_color = self.HIGHLIGHT_COLORS[int(highlights[datetime]['color'])]
                    a_mi.highlight_text = highlight_text
                    a_mi.last_modification = datetime
                    try:
                        section = str(int(highlights[datetime]['section']) - 1)
                        a_mi.location = toc_entries[section]
                    except:
                        if this_is_news:
                            a_mi.location = book_mi['title']
                        else:
                            a_mi.location = "Section %s" % highlights[datetime]['section']
                    a_mi.note_text = note_text

                    # If empty highlight_text and empty note_text, not a useful annotation
                    if (not highlight_text.strip() and not note_text.strip()):
                        continue

                    # Generate location_sort
                    if this_is_news:
                        a_mi.location_sort = datetime
                    else:
                        interior = self._generate_interior_location_sort(highlights[datetime]['startx'])
                        if not interior:
                            self._log("Marvin: unable to parse xpath:")
                            self._log(" %s" % highlights[datetime]['startx'])
                            self._log(a_mi)
                            continue

                        a_mi.location_sort = "%04d.%s.%04d" % (
                            int(highlights[datetime]['section']),
                            interior,
                            int(highlights[datetime]['startoffset']))

                    self.add_to_annotations_db(self.annotations_db, a_mi)
                    self.update_book_last_annotation(self.books_db, datetime, book_mi['book_id'])

            # Update the timestamps
            self.update_timestamp(self.annotations_db)
            self.update_timestamp(self.books_db)
            self.commit()

        # ~~~~~~~~~~~~~~ Entry point ~~~~~~~~~~~~~~

        # Create the annotations, books table as needed
        self.annotations_db = "%s_imported_annotations" % self.app_name_
        self.create_annotations_table(self.annotations_db)
        self.books_db = "%s_imported_books" % self.app_name_
        self.create_books_table(self.books_db)

        self.annotated_book_list = []
        self.selected_books = None

        # Parse the incoming XML
        marvin = html.fromstring(raw)
        scope = marvin.get('scope')
        if scope == 'library':
            # Collect a group of library annotations
            books = marvin.findall('book')
            for book in books:
                _process_individual_book(book)
        elif scope == 'book':
            # Collect a single book metadata
            _process_individual_book(marvin)
        else:
            if log_failure:
                self._log("Marvin:parse_exported_highlights()")
                self._log(" unrecognized scope '%s' in imported Marvin highlights" % scope)
                self._log(" --- Contents of imported highlights ---")
                self._log(etree.tostring(marvin, pretty_print=True))
            return False
        return True

    ''' Helpers '''
    def _fix_Marvin_path(self, original_path):
        path = '/'.join(['/Documents', original_path])
        return path

    def _generate_interior_location_sort(self, xpath):
        try:
            match = re.match(r'\/x:html\[1\]\/x:body\[1\]\/x:div\[1\]\/x:div\[1\]\/x:(.*)\/text.*$', xpath)
            steps = len(match.group(1).split('/x:'))
            full_ladder = []
            for item in match.group(1).split('/x:'):
                full_ladder.append(int(re.match(r'.*\[(\d+)\]', item).group(1)))
            if len(full_ladder) < self.MAX_ELEMENT_DEPTH:
                for x in range(steps, self.MAX_ELEMENT_DEPTH):
                    full_ladder.append(0)
            else:
                full_ladder = full_ladder[:self.MAX_ELEMENT_DEPTH]
            fmt_str = '.'.join(["%04d"] * self.MAX_ELEMENT_DEPTH)
            return fmt_str % tuple(full_ladder)
        except:
            return False

