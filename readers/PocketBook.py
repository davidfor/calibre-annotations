#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2021 William Ouwehand <> with parts by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import os, re, json

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)
from calibre.devices.usbms.driver import USBMS


class PocketBookFetchingApp(USBReader):
    """
    Fetching annotations takes place in two stages:
    1) get_installed_books():
        add the installed books' metadata to the database
    2) get_active_annotations():
        add the annotations for installed books to the database
    """
    # The app name should be the first word from the
    # device's name property, e.g., 'Kindle' or 'SONY'. Drivers are located in
    app_name = 'PocketBook'

    # Change this to True when developing a new class from this template
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

        self._log_location("Start!!!!")
        self._log("%s:get_active_annotations()" % self.app_name)

        self.opts.pb.set_label("Getting active annotations for %s" % self.app_name)
        self.opts.pb.set_value(0)

        annotations_db = self.generate_annotations_db_name(self.app_name_, self.opts.device_name)
        self.books_db = self.generate_books_db_name(self.app_name_, self.opts.device_name)

        # Create the annotations table
        self.create_annotations_table(annotations_db)

        self._fetch_annotations()
        # Initialize the progress bar
        self.opts.pb.set_label("Getting highlights from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.set_maximum(len(self.active_annotations))

        # Add annotations to the database
        for annotation in sorted(list(self.active_annotations.values()), key=lambda k: (k['book_id'], k['location_sort'], k['last_modification'])):
            # Populate an AnnotationStruct with available data
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = annotation['book_id']
            ann_mi.last_modification = annotation['last_modification']

            # Optional items with PB modifications
            if 'annotation_id' in annotation:
                ann_mi.annotation_id = annotation['annotation_id']
            if 'highlight_color' in annotation:
                ann_mi.highlight_color = annotation['highlight_color'].capitalize()
            if 'highlight_text' in annotation:
                highlight_text = annotation['highlight_text']
                ann_mi.highlight_text = highlight_text
            if 'note_text' in annotation:
                note_text = annotation['note_text']
                ann_mi.note_text = note_text
            if 'page' in annotation:
                ann_mi.location = annotation['page']
            if 'location_sort' in annotation:
                ann_mi.location_sort = "%08d" % annotation['location_sort']
            if 'epubcfi' in annotation:
                ann_mi.epubcfi = annotation['epubcfi']

            # Add annotation to annotations_db
            self.add_to_annotations_db(annotations_db, ann_mi)

            # Increment the progress bar
            self.opts.pb.increment()

            # Update last_annotation in books_db
            self.update_book_last_annotation(self.books_db, ann_mi.last_modification, ann_mi.book_id)

        # Update the timestamp
        self.update_timestamp(annotations_db)
        self.commit()
        self._log_location("Finish!!!!")

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

        self._log_location("Start!!!!")
        self._log("%s:get_installed_books()" % self.app_name)
        self.installed_books = []

        self.device = self.opts.gui.device_manager.device

        # Calibre already knows what books are on the device, so use it.
        db = self.opts.gui.library_view.model().db
        self.onDeviceIds = set(db.search_getting_ids('ondevice:True', None, sort_results=False, use_virtual_library=False))
        self._log("%s:get_installed_books() - self.onDeviceIds=" % self.onDeviceIds)

        self._log("%s:get_installed_books() - about to call self.generate_books_db_name" % self.app_name)
        self.books_db = self.generate_books_db_name(self.app_name_, self.opts.device_name)
        installed_books = set([])

        # Used by get_active_annotations() to look up metadata based on title
        self.installed_books_by_title = {}

        # Create the books table
        self.create_books_table(self.books_db)

        # Initialize the progress bar
        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.set_maximum(len(self.onDeviceIds))
        self._log("Number of books on the device=%d" % len(self.onDeviceIds))

        #  Add installed books to the database
        for book_id in self.onDeviceIds:
            mi = db.get_metadata(book_id, index_is_id=True)
            installed_books.add(book_id)

            # Populate a BookStruct with available metadata
            book_mi = BookStruct()
#            book_mi.path = resolved_path_map[book_id]            # Add book_id to list of installed_books (make this a sql function)
            installed_books.add(book_id)

            # Populate a BookStruct with available metadata
            book_mi = BookStruct()

            # Required items
            book_mi.active = True
            # Massage last, first authors back to normalcy
            book_mi.author = ''
            for i, author in enumerate(mi.authors):
#                self._log_location("author=%s, author.__class__=%s" % (author, author.__class__))
                this_author = author.split(', ')
                this_author.reverse()
                book_mi.author += ' '.join(this_author)
                if i < len(mi.authors) - 1:
                    book_mi.author += ' & '

            book_mi.book_id = book_id
            book_mi.reader_app = self.app_name
            book_mi.title = mi.title

            if hasattr(mi, 'author_sort'):
                book_mi.author_sort = mi.author_sort

            if hasattr(mi, 'title_sort'):
                book_mi.title_sort = mi.title_sort
            else:
                book_mi.title_sort = re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', mi.title).rstrip()

            if hasattr(mi, 'uuid'):
                book_mi.uuid = mi.uuid

            # Add book to self.books_db
            self.add_to_books_db(self.books_db, book_mi)

            # Add book to indexed_books
            self.installed_books_by_title[mi.title] = {'book_id': book_id, 'author_sorted': mi.author_sort}

            # Increment the progress bar
            self.opts.pb.increment()

        # Update the timestamp
        self.update_timestamp(self.books_db)
        self.commit()

        self.installed_books = list(installed_books)
        self._log_location("Finish!!!!")


    def location_split(self, string):
        '''Returns page (int), offset (int) and cfi (string, with either epubcfi or pdfloc) tuple
        from PB location string.'''

        page = re.findall(r'(?<=page=)\d*', string) or None
        offs = re.findall(r'(?<=offs=)\d*', string) or None
        cfi = re.findall(r'(?<=#).*', string) or None

        if page:
            page = int(page[0])
        if offs:
            offs = int(offs[0])
        if cfi:
            cfi = cfi[0]

        return page, offs, cfi


    def _fetch_annotations(self):
        self._log_location("Start!!!!")

        count_bookmark_query = (
            '''
            SELECT COUNT(*) AS num_bookmarks FROM Tags t
            WHERE TagID = 102 AND ItemID IN (SELECT OID from Items WHERE State = 0)
            '''
        )

        books_metadata_query = (
            '''
            SELECT b.OID book_oid, i.format, p.Path, f.filename, Title, Authors FROM Books b
            LEFT JOIN (SELECT MAX(OID), BookID, PathID, Name AS filename FROM Files GROUP BY BookID) f ON b.OID = f.BookID
            LEFT JOIN (SELECT ItemID, Val AS format FROM Tags WHERE TagID = 17) i ON b.OID = i.ItemID
            LEFT JOIN Paths p ON p.OID = PathID
            WHERE b.OID IN (SELECT DISTINCT ParentID FROM Items WHERE TypeID = 4 ORDER BY ParentID)
            GROUP BY b.OID
            ORDER BY b.OID
            '''
        )

        # For 104 (highlight_txt) either use json_extract(text), or import JSON using python
        # as notes edited in the PB notes app loose their Begin/End JSON fields.
        annotation_data_query = (
            '''
            SELECT i.OID AS item_oid, i.TimeAlt, t.TagID, t.Val FROM Items i
            LEFT JOIN Tags t ON i.OID=t.ItemID
            WHERE ParentID = ? AND State = 0
            ORDER BY i.OID, t.TagID
            '''
        )

        def get_device_path_from_id(id_):
            paths = []
            for x in ('memory', 'card_a', 'card_b'):
                x = getattr(self.opts.gui, x+'_view').model()
                paths += x.paths_for_db_ids(set([id_]), as_map=True)[id_]
            return paths[0].path if paths else None

        # Modified.
        def generate_annotation_paths(ids, mode="default"):
            path_map = {}
            for id in ids:
                fullpath = get_device_path_from_id(id)
                if not fullpath:
                    continue

                if mode == "default":
                    pbmainroot = "/mnt/ext1/"
                    pbcardroot = "/mnt/ext2/"

                if self.device._main_prefix in fullpath:
                    path_map[os.path.join(pbmainroot, os.path.relpath(fullpath, start=self.device._main_prefix))] = id
                elif self.device._card_a_prefix in fullpath:
                    path_map[os.path.join(pbcardroot, os.path.relpath(fullpath, start=self.device._card_a_prefix))] = id
                elif fullpath.startswith(('/var/', '/tmp/')):
                    continue
                else:
                    self._log("Path not matched: %s" % (fullpath))

            return path_map

        def generate_title_map(ids, db):
            title_map = {}
            for id in ids:
                title = db.get_metadata(id, index_is_id=True).title
                if title:
                    title_map[title] = {}
                    title_map[title]['book_id'] = id
                    title_map[title]['authors'] = db.get_metadata(id, index_is_id=True).format_authors()
                else:
                    continue

            return title_map

        # Get DB location (only stock or default profile)
        self._log("Getting DB location")
        locations = [os.path.join(self.device._main_prefix, 'system/config/books.db'),
                     os.path.join(self.device._main_prefix, 'system/profiles/default/config/books.db')]
        paths = [path for path in locations if os.path.exists(path)]
        if paths:
            db_location = USBMS.normalize_path(paths[0])
        else:
            self._log("No DB found. Currently only supports default profiles, with DB based notes. Stopping")
            return

        # Borrowed from Kobo
        db = self.opts.gui.library_view.model().db
        if not self.onDeviceIds:
            self.onDeviceIds = set(db.search_getting_ids('ondevice:True', None, sort_results=False, use_virtual_library=False))
        
        if len(self.onDeviceIds) == 0:
            return
        self._log("_fetch_annotations - onDeviceIds={0}".format(self.onDeviceIds))

        path_map = generate_annotation_paths(self.onDeviceIds)
        title_map = generate_title_map(self.onDeviceIds, db)

        # Start fetching annotations
        from contextlib import closing
        import apsw
        with closing(apsw.Connection(db_location)) as connection:
            self.opts.pb.set_label(_("Fetch annotations from database"))
            connection.setrowtrace(self.row_factory)

            cursor = connection.cursor()
            cursor.execute(count_bookmark_query)
            try:
                result = next(cursor)
                count_bookmarks = result['num_bookmarks']
            except StopIteration:
                count_bookmarks = 0
            self._log("_fetch_annotations - Total number of bookmarks={0}".format(count_bookmarks))
            self._log("_fetch_annotations - About to get annotations")
            self._read_database_annotations(connection, books_metadata_query,
                                            annotation_data_query, path_map, title_map, fetchbookmarks=False)
            self._log("_fetch_annotations - Finished getting annotations")

        self._log_location("Finish!!!!")

    def _read_database_annotations(self, connection, books_metadata_query, annotation_data_query,
                                   path_map, title_map, fetchbookmarks=False):
        self._log("_read_database_annotations - Starting fetch of bookmarks")

        metadata_cursor = connection.cursor()
        annotation_data_cursor = connection.cursor()

        regex_authorfix = re.compile('[,]? and ')  # revert PB changes to epubs author field
        match_path, match_authtitle, match_title, match_fail, match_failauth = 0, 0, 0, 0, 0

        for book in metadata_cursor.execute(books_metadata_query):
            title = book['Title']
            book_oid = book['book_oid']
            filepath = os.path.join(book['Path'], book['filename'])

            book_id = path_map.get(filepath, None)
            if book_id:
                match_path += 1
            else:
                if title in title_map:
                    book_id = title_map[title]['book_id']
                    authors = book['Authors']
                    if authors:
                        authors_fixed = re.sub(regex_authorfix, ' & ', authors)
                        if title_map.get(title, {}).get('authors', "") in (authors, authors_fixed):
                            match_authtitle += 1
                        else:
                            match_failauth += 1
                            self._log("_read_database_annotation - AUTHOR mismatch: PB oid {0}, {1} by {2}, {3}".format(book_oid, title, authors, filepath))
                            continue
                    else:
                        match_title += 1
                else:
                    match_fail += 1
                    self._log("_read_database_annotation - Title not found in Calibre: PB oid {0}, {1}, {2}".format(book_oid, title, filepath))
                    continue

            for row in annotation_data_cursor.execute(annotation_data_query, (book_oid,)):
                TagID = row['TagID']
                Val = row['Val']

                if TagID == 101:
                    finish = False
                    note_text = None  # for highlight
                    page, offs, cfi1 = self.location_split(json.loads(Val).get('anchor', ""))
                elif TagID == 102:
                    atype = Val
                elif TagID == 104:
                    highlight_text = json.loads(Val).get('text', None)
                    if fetchbookmarks and atype == "bookmark":
                        highlight_color = None
                        finish = True
                elif TagID == 105:
                    note_text = json.loads(Val).get('text', None)
                elif TagID == 106:
                    highlight_color = Val
                    finish = True
                elif TagID == 110:
                    pass
                    # 'draws' SVG data
                else:
                    self._log("_read_database_annotations - Unprocessed Tag ID {0} in ItemID {1} for {2}".format(TagID, row.get('item_oid'), title))

                if finish:
                    finish = False

                    # bookmark and draws lack 106, but add nevertheless
                    if atype not in ('highlight', 'note', 'bookmark'):
                        continue

                    data = {
                        'annotation_id': row['item_oid'],
                        'book_id': book_id,
                        'last_modification': row.get('TimeAlt', 0),
                        #'format': book['mimetype'],
                        #'type': atype,
                        #'title': title,
                        #'book_oid': book_oid,
                        'epubcfi': cfi1,
                        'highlight_text': highlight_text,
                        'note_text': note_text,
                        'highlight_color': highlight_color or 'yellow',
                        'location': page,
                        'page': page,
                        # 'offs': offs,
                        'location_sort': page * 10000 + (offs or 0),
                    }

                    # self._log(self.active_annotations[annotation_id])
                    self.active_annotations[row['item_oid']] = data

        self._log("_fetch_annotations - Matched on path %i, title/author: %i, title: %i, "
                  "Unmatched: author: %i, title: %i" % (match_path, match_authtitle, match_title, match_failauth, match_fail))

    def row_factory(self, cursor, row):
        return {k[0]: row[i] for i, k in enumerate(cursor.getdescription())}
