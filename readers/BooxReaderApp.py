#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import datetime, re, time

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)


# Change the class name to <app_name>ReaderApp, e.g. 'KindleReaderApp'
class BooxReaderApp(USBReader):
    """
    Sample USB implementation
    Fetching annotations takes place in two stages:
    1) get_installed_books():
        add the installed books' metadata to the database
    2) get_active_annotations():
        add the annotations for installed books to the database
    """
    # The app name should be the first word from the
    # device's name property, e.g., 'Kindle' or 'SONY'. Drivers are located in
    # calibre.devices.<device>
    # For example, the name declared in the Kindle class
    # is 'Kindle 2/3/4/Touch/PaperWhite Device Interface',
    # so app_name would be the first word, 'Kindle'
    app_name = 'Boox'

    # Change this to True when developing a new class from this template
    SUPPORTS_FETCHING = True

    # Fetch the active annotations, add them to the annotations_db
    def get_active_annotations(self):
        self.device = self.opts.gui.device_manager.device

        # Only check for primary storage without SD Cards
        storage = self.device.filesystem_cache.storage(self.device._main_id)

        # Avoid misconfiguration
        db_file_info = storage.find_path('AlReaderXE-Ink/Backup/alrxread.db'.split('/'))

        if db_file_info is None:
            raise ValueError('Please add "AlReaderXE-Ink" folder to scanned folders'
                             'in "Device > Configure this device" dialog.')

        import os, tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False)

        try:
            self.device.get_file(db_file_info.mtp_id_path, tmp)

            import apsw
            conn = apsw.Connection(tmp.name)
            conn.setrowtrace(self.row_factory)

            cur = conn.cursor()

            bookmarks_query = (
                '''
                SELECT  bmk.id,
                        REPLACE(bmk.filename, bmk.cardpath || '/', '') AS filename,
                        bmk.dateadd,
                        bmk.color,
                        bmk.typebmk,
                        bmk."text",
                        bmk.start,
                        rct.booksize
                FROM bookmarks bmk
                JOIN recent rct ON rct.filename = bmk.filename
                ORDER BY rct.id ASC, bmk.start ASC
                '''
            )

            cur.execute(bookmarks_query)
            rows = cur.fetchall()

            color_map = {
                0: {'color': 'Purple', 'name': 'Without marker'},
                1: {'color': 'Red', 'name': 'Red background'},
                2: {'color': 'Yellow', 'name': 'Yellow background'},
                3: {'color': 'Green', 'name': 'Green background'},
                4: {'color': 'Gray', 'name': 'Underline'},
                5: {'color': 'Red', 'name': 'Red underline'},
                6: {'color': 'Yellow', 'name': 'Yellow underline'},
                7: {'color': 'Green', 'name': 'Green underline'}
            }

            import math

            dict_of_anns = {}

            for row in rows:
                bmk_color = row['color']
                bmk_date = math.floor(row['dateadd'] / 1000)

                bmk_location = str(round((row['start'] / row['booksize']) * 100, 2)) + '%'
                bmk_location += ' ('
                bmk_location += ('BMK' if row['typebmk'] == 0 else 'CITE') + ', ' + color_map[bmk_color]['name']
                bmk_location += ')'

                book_filename = row['filename']

                # Ignore annotations of the books, that are not found in the Calibre
                if book_filename not in self.installed_books_by_path:
                    self._log("%s:get_active_annotations() - annotated book '%s' not found" % (self.app_name, book_filename))
                    continue

                book_id = self.installed_books_by_path[book_filename]

                dict_of_anns[bmk_date] = {
                    'annotation_id': row['id'],
                    'book_id': book_id,
                    'highlight_color': color_map[bmk_color]['color'],
                    'highlight_text': row['text'].replace('\r\n', '\n').split('\n'),
                    'location': bmk_location,
                    'location_sort': row['start'],
                    'timestamp': bmk_date
                }
        finally:
            tmp.close()
            os.unlink(tmp.name)

        self._log("%s:get_active_annotations()" % self.app_name)

        self.opts.pb.set_label("Getting active annotations for %s" % self.app_name)
        self.opts.pb.set_value(0)

        annotations_db = self.generate_annotations_db_name(self.app_name_, self.opts.device_name)
        books_db = self.generate_books_db_name(self.app_name_, self.opts.device_name)

        # Create the annotations table
        self.create_annotations_table(annotations_db)

        # Initialize the progress bar
        self.opts.pb.set_label("Getting highlights from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.set_maximum(len(dict_of_anns))

        # Add annotations to the database
        for timestamp in sorted(dict_of_anns.keys()):
            # Populate an AnnotationStruct with available data
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = dict_of_anns[timestamp]['book_id']
            ann_mi.last_modification = timestamp
            ann_mi.location = dict_of_anns[timestamp]['location']
            ann_mi.location_sort = dict_of_anns[timestamp]['location_sort']

            # Optional items
            if 'annotation_id' in dict_of_anns[timestamp]:
                ann_mi.annotation_id = dict_of_anns[timestamp]['annotation_id']
            if 'highlight_color' in dict_of_anns[timestamp]:
                ann_mi.highlight_color = dict_of_anns[timestamp]['highlight_color']
            if 'highlight_text' in dict_of_anns[timestamp]:
                highlight_text = '\n'.join(dict_of_anns[timestamp]['highlight_text'])
                ann_mi.highlight_text = highlight_text
            if 'note_text' in dict_of_anns[timestamp]:
                note_text = '\n'.join(dict_of_anns[timestamp]['note_text'])
                ann_mi.note_text = note_text

            # Add annotation to annotations_db
            self.add_to_annotations_db(annotations_db, ann_mi)

            # Increment the progress bar
            self.opts.pb.increment()

            # Update last_annotation in books_db
            self.update_book_last_annotation(books_db, timestamp, ann_mi.book_id)

        # Update the timestamp
        self.update_timestamp(annotations_db)
        self.commit()

    def get_installed_books(self):
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
        self.installed_books_by_path = {}

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

            # Required items
            book_mi.active = True
            # Massage last, first authors back to normalcy
            book_mi.author = ''

            for i, author in enumerate(mi.authors):
                # self._log_location("author=%s, author.__class__=%s" % (author, author.__class__))
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

            # Add book to indexed_books without MTP prefix
            for path in self.get_device_paths_from_id(book_id):
                self.installed_books_by_path[path.split('/', maxsplit=1).pop()] = book_id

            # Increment the progress bar
            self.opts.pb.increment()

        # Update the timestamp
        self.update_timestamp(self.books_db)
        self.commit()

        self.installed_books = list(installed_books)
        self._log_location("Finish!!!!")

    def get_device_paths_from_id(self, book_id):
        model = self.opts.gui.memory_view.model()
        paths = model.paths_for_db_ids({book_id}, as_map=True)[book_id]

        return [r.path for r in paths]

    def row_factory(self, cursor, row):
        return {k[0]: row[i] for i, k in enumerate(cursor.getdescription())}
