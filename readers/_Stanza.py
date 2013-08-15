#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import datetime, os, re, sqlite3, time

from lxml import etree

from calibre.utils.zipfile import ZipFile

from calibre_plugins.annotations.reader_app_support import iOSReaderApp
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)


class StanzaReaderApp(iOSReaderApp):
    # Reader-specific characteristics
    annotations_subpath = '/Documents/.Stanza/DB.dat'
    app_name = 'Stanza'
    books_subpath = '/Documents/.Stanza/DB.dat'
    HIGHLIGHT_COLORS = ['Yellow']

    SUPPORTS_FETCHING = True

    # Fetch the active annotations, add them to the annotations_db
    def get_active_annotations(self):
        '''
        For each annotation, construct an AnnotationStruct object with the
        highlight's metadata. Starred items are minimally required. Dashed items
        (highlight_text and note_text) may be one or both.
          AnnotationStruct properties:
            annotation_id: an int uniquely identifying the annotation
           *book_id: The book this annotation is associated with
            highlight_color: [Blue|Gray|Green|Pink|Purple|Underline|Yellow]
           -highlight_text: A list of paragraphs constituting the highlight
            last_modification: The timestamp of the annotation
            location: location of highlight in the book
           -note_text: A list of paragraphs constituting the note
           *timestamp: Unique timestamp of highlight's creation/modification time
        '''
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
                                book_oid,
                                last_access,
                                book_annotations.location,
                                book_annotations.book_position,
                                note,
                                book_annotations.oid as ba_oid
                               FROM book_annotations
                               JOIN book ON book.oid = book_annotations.book_oid
                               ORDER BY book_annotations.book_position
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                annotations = {}
                timestamp = None
                for row in rows:
                    self.opts.pb.increment()
                    book_id = row[b'book_oid']
                    if not book_id in self.installed_books:
                        continue

                    # Annotations are quoted. Anything afterwards is a note.
                    # Assuming that the user hasn't edited the opening/closing quotes,
                    # we can assume that a sequence of '"\n' is a valid split point.
                    full_annotation = row[b'note']
                    highlight_text = None
                    note_text = None
                    if full_annotation.startswith('"') and full_annotation.endswith('"'):
                        # Highlight only - strip opening/closing quotes
                        highlight_text = [full_annotation[1:-1]]
                    elif '"\n' in full_annotation:
                        # Presumed to be a hybrid highlight/note, separated by closing quote/LF
                        tokens = full_annotation.split('"\n')
                        highlight_text = [tokens[0][1:]]
                        note_text = tokens[1].split('\n')
                    else:
                        # User manually removed the quotes, assume it's just a note
                        note_text = full_annotation.split('\n')

                    # Populate an AnnotationStruct
                    a_mi = AnnotationStruct()
                    a_mi.annotation_id = row[b'ba_oid']
                    a_mi.book_id = book_id
                    a_mi.epubcfi = row[b'location']
                    a_mi.highlight_color = 'Yellow'
                    if highlight_text:
                        a_mi.highlight_text = '\n'.join(highlight_text)
                    if note_text:
                        a_mi.note_text = '\n'.join(note_text)

                    section = self._get_spine_index(a_mi.epubcfi)
                    try:
                        a_mi.location = self.tocs[book_id]["%.0f" % (section)]
                    except:
                        a_mi.location = "Section %d" % section
                    a_mi.location_sort = row[b'book_position']

                    # Stanza doesn't timestamp individual annotations
                    # Space them 1 second apart
                    timestamp = row[b'last_access']
                    while timestamp in annotations:
                        timestamp += 1
                    a_mi.last_modification = timestamp + self.NSTimeIntervalSince1970
                    annotations[timestamp] = a_mi

                for timestamp in annotations:
                    self.add_to_annotations_db(cached_db, annotations[timestamp])

                # Update last_annotation in books_db
                if timestamp:
                    self.update_book_last_annotation(books_db,
                                                 timestamp,
                                                 book_id)
                    self.update_timestamp(cached_db)
                    self.commit()

        else:
            self._log(" retrieving cached annotations from %s" % cached_db)

    def get_installed_books(self):
        '''
        For each book, construct a BookStruct object with the book's metadata.
        Starred items are minimally required.
           BookStruct properties:
            *active: [True|False]
            *author: "John Smith"
             author_sort: (if known)
            *book_id: an int uniquely identifying the book.
                     Highlights are associated with books through book_id
             genre: "Fiction" (if known)
            *reader_app: self.app_name
            *title: "The Story of John Smith"
             title_sort: "Story of John Smith, The" (if known)
             uuid: Calibre's uuid for this book, if known
        '''
        self._log("%s:get_installed_books()" % self.app_name)
        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)

        db_profile = self._localize_database_path(self.app_id, self.books_subpath)
        self.book_db = db_profile['path']

        cached_db = self.generate_books_db_name(self.app_name_, self.ios.device_name)

        if self.opts.disable_caching or not self._cache_is_current(db_profile['stats'], cached_db):
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
                cur.execute('''SELECT DISTINCT
                                      author,
                                      oid,
                                      subject,
                                      source,
                                      title,
                                      uuidstr
                               FROM book
                               JOIN book_subjects ON book.oid = book_subjects.book_oid
                            ''')
                rows = cur.fetchall()
                self.opts.pb.set_maximum(len(rows))
                for row in rows:
                    self.opts.pb.increment()
                    book_id = row[b'oid']
                    installed_books.add(book_id)

                    path = self._get_stanza_path(row[b'title'])

                    # Populate a BookStruct
                    b_mi = BookStruct()
                    b_mi.active = True
                    b_mi.author = row[b'author']
                    b_mi.book_id = book_id
                    b_mi.genre = row[b'subject']
                    b_mi.path = path
                    b_mi.title = row[b'title']
                    b_mi.uuid = self._get_uuid(row[b'uuidstr'])

                    # Add book to books_db
                    self.add_to_books_db(cached_db, b_mi)

                    # Get the library cid, confidence
                    cid, confidence = self.parent.generate_confidence(b_mi)
                    toc_entries = None
                    if confidence >= 2:
                        toc_entries = self._get_epub_toc(cid=cid, path=path)
                    elif path is not None:
                        toc_entries = self._get_epub_toc(path=path)
                    self.tocs[book_id] = toc_entries

                # Update the timestamp
                self.update_timestamp(cached_db)
                self.commit()

            installed_books = list(installed_books)

        else:
            # Load installed books from cache
            self._log(" retrieving cached books from %s" % cached_db)
            installed_books = self._get_cached_books(cached_db)

        self.installed_books = installed_books

    def _get_spine_index(self, epubcfi):
        '''
        1,/html/body/div/div/div[2]/p,0,<text>
        '''
        return int(re.match(r'^(\d+),.*$', epubcfi).group(1))

    def _get_stanza_path(self, title):
        '''
        Look through Documents for filename containing title
        '''
        path = None
        files = self.ios.listdir('/Documents')
        for f in files:
            if title in f:
                path = '/'.join(['/Documents', f])
                break
        return path

    def _get_uuid(self, uuidstr):
        uuid = None
        if uuidstr.startswith('urn:calibre:'):
            uuid = re.match(r'urn:calibre:(?P<uuid>.*)$',uuidstr).group('uuid')
        return uuid
