#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import datetime
import os
import sqlite3

app_package = "com.flyersoft.moonreaderp"
db_backup_location = app_package + "/databases/mrbooks.db"

import time
import tempfile
import zipfile

from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)
from calibre_plugins.annotations.reader_app_support import ExportingReader
from calibre.ebooks.metadata.book.base import Metadata

class MoonReaderApp(ExportingReader):
    if True:
        import_help_text = ('''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>Exporting from Moon+ Reader</title>
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
                <h3>Exporting annotations from Moon+ Reader</h3>
                <div class="steps_with_header_indent">
                  <p><i>From within Moon+ Reader, go into options and export your backup to an .mrpro file and copy it
                  to your computer or sync with something like Dropbox.</i></p>
                <hr width="80%" />
                <h3>Importing Moon+ Reader annotations to calibre</h3>
                <div class="steps_with_header_indent">
                  <p><i>After obtaining the backup file from your device:</i></p>
                  <ol>
                    <li>Click Annotations, <b>Import annotations from...</b>, and then MoonReader</li>
                    <li>Use the file chooser to select your .mrpro backup file, and click Open</li>
                    <li>In the <b>Import Annotations</b> window, review the matches. Matches where we have an author
                    and title match are automatically checked. If you would like to import unmatched annotations, ensure
                    the book you're importing to is selected in the library prior to import.</li>
                  </ol>
                </div>
            </body>
            </html>''')

    app_name = 'MoonReader'
    import_fingerprint = False
    import_dialog_title = 'Path to Moon+ Reader backup'
    initial_dialog_text = "/config/%s.mrpro" % datetime.date.today()
    SUPPORTS_EXPORTING = True

    SUPPORTS_FILE_CHOOSER = True
    import_file_name_filter = "Moon+ Reader Backup (*.mrpro)"

    def parse_exported_highlights(self, raw, log_failure=True):
        self._log("%s:parse_exported_highlight()" % self.app_name)

        # Create the annotations, books table as needed
        self.annotations_db = "%s_imported_annotations" % self.app_name_
        self.create_annotations_table(self.annotations_db)
        self.books_db = "%s_imported_books" % self.app_name_
        self.create_books_table(self.books_db)
        #from PyQt5.QtCore import pyqtRemoveInputHook
        #from pdb import set_trace
        #pyqtRemoveInputHook()
        #set_trace()
        self.annotated_book_list = []
        self.selected_books = None

        tmpdir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(raw, 'r') as mrpro:
            mrpro.extractall(tmpdir.name)

        cdb = self.opts.gui.current_db
        db = self._db_location(tmpdir.name)
        con = sqlite3.connect(os.path.join(tmpdir.name, app_package, db))
        bookmap = {}
        annotations = []
        for row in con.execute("""
                SELECT
                    books._id,
                    notes._id,
                    notes.book,
                    books.author,
                    notes.time,
                    notes.lastPosition,
                    notes.highlightColor,
                    notes.highlightLength,
                    notes.original,
                    notes.note
                FROM
                    notes
                INNER JOIN
                    books
                        ON
                            notes.filename = books.filename
                ORDER BY
                    time DESC;"""):

            # Convert ms to seconds
            timestamp = row[4] / 1000.0

            if row[0] not in bookmap:
                book_mi = BookStruct()
                book_mi.active = True
                book_mi.title = row[2]
                book_mi.author = row[3]
                book_mi.uuid = None
                book_mi.last_update = time.mktime(time.localtime())
                book_mi.reader_app = self.app_name
                book_mi.annotations = 0

                # FIXME: The handling of this is so weird, the book matcher later tries to match up
                #   the annotations to books in the Calibre DB, but if I don't set the ID here too
                #   things don't work.  It seems like all the exporting readers expect users to import
                #   annotations one book at a time? What's the point of the import dialog then? This makes
                #   no sense.
                existing = cdb.find_identical_books(Metadata(book_mi.title, [book_mi.author]))
                if len(existing) > 0:
                    book_id = next(iter(existing))
                    book_mi.book_id = book_id
                    book_mi.cid = book_id

                bookmap[row[0]] = book_mi
                book = book_mi
            else:
                book = bookmap[row[0]]

            book.annotations = book.annotations + 1

            # Populate an AnnotationStruct
            ann_mi = AnnotationStruct()
            ann_mi.book_id = book.book_id
            ann_mi.last_modification = timestamp
            ann_mi.timestamp = timestamp
            ann_mi.location = row[5]
            ann_mi.location_sort = row[5]
            ann_mi.annotation_id = row[1]
            # colors in the moon reader db are integer values of ARGB style colors
            ann_mi.highlight_color = f"#{format(row[6], 'x')}"
            ann_mi.highlight_text = row[8]
            ann_mi.note_text = row[9]
            annotations.append(ann_mi)

        for key, book_mi in bookmap.items():
            # Add book to books_db
            self.add_to_books_db(self.books_db, book_mi)
            self.annotated_book_list.append(book_mi)

        for ann_mi in annotations:
            self.add_to_annotations_db(self.annotations_db, ann_mi)
            self.opts.pb.increment()
            self.update_book_last_annotation(self.books_db, ann_mi.last_modification, ann_mi.book_id)

        # Update the timestamp
        self.update_timestamp(self.annotations_db)
        self.update_timestamp(self.books_db)
        self.commit()

        # Return True if successful
        return True

    # Helpers
    def _db_location(self, path):
        with open(os.path.join(path, app_package, "_names.list")) as file:
            for ln, line in enumerate(file, 1):
                if db_backup_location in line:
                    self._log_location(f"found moon reader db at index #{ln}")
                    return os.path.join(path, app_package, str(ln) + ".tag")
