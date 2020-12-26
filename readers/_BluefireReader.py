#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import re, time
from time import mktime

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.utils.date import parse_date

from calibre_plugins.annotations.common_utils import (
    AnnotationsException, AnnotationStruct, BookStruct)
from calibre_plugins.annotations.reader_app_support import ExportingReader


class BluefireReader(ExportingReader):
    """
    Sample implementation
    """

    # app_name should be the same as the class name
    app_name = 'Bluefire Reader'
    import_fingerprint = True
    import_dialog_title = "Import {0} annotations".format(app_name)
    if True:
        import_help_text = ('''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>Exporting from Bluefire Reader</title>
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
                <h3>Exporting annotations from Bluefire Reader</h3>
                <div class="steps_with_header_indent">
                  <p><i>From within an open book:</i></p>
                  <ol>
                    <li>Tap the center of the screen so that the overlay controls are shown</li>
                    <li>Tap <b>Bookmarks</b> (page marker icon at bottom center)</li>
                    <li>Tap <b>Bookmarks</b> (top right)</li>
                    <li>Tap <b>Share</b> (arrow icon at top right)</li>
                    <li>Tap <b>Email</b>, then email the annotations file to yourself</li>
                  </ol>
                </div>
                <hr width="80%" />
                <h3>Importing Bluefire Reader annotations to calibre</h3>
                <div class="steps_with_header_indent">
                  <p><i>After receiving the emailed annotations summary on your computer:</i></p>
                  <ol>
                    <li>Copy the contents of the annotations summary email</li>
                    <li>Paste the annotations to the <b>Import Bluefire Reader annotations</b> window</li>
                    <li>Click <b>Import</b></li>
                  </ol>
                </div>
            </body>
            </html>''')

    initial_dialog_text = ''

    SUPPORTS_EXPORTING = True

    def parse_exported_highlights(self, raw, log_failure=True):
        """
        Extract highlights from pasted Annotations summary, add them to selected book
        in calibre library

        Construct a BookStruct object with the book's metadata.
        Starred items are minimally required.
           BookStruct properties:
            *active: [True|False]
            *author: "John Smith"
             author_sort: (if known)
            *book_id: an int uniquely identifying the book.
                     Highlights are associated with books through book_id
             genre: "Fiction" (if known)
            *title: "The Story of John Smith"
             title_sort: "Story of John Smith, The" (if known)
             uuid: Calibre's uuid for this book, if known

        Construct an AnnotationStruct object with the
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

        """
        # Create the annotations, books table as needed
        self.annotations_db = "%s_imported_annotations" % self.app_name_
        self.create_annotations_table(self.annotations_db)
        self.books_db = "%s_imported_books" % self.app_name_
        self.create_books_table(self.books_db)

        self.annotated_book_list = []
        self.selected_books = None

        # Generate the book metadata from the selected book
        row = self.opts.gui.library_view.currentIndex()
        book_id = self.opts.gui.library_view.model().id(row)
        db = self.opts.gui.current_db
        mi = db.get_metadata(book_id, index_is_id=True)

        try:
            lines = raw.split('\n')
            if len(lines) < 5:
                raise AnnotationsException("Invalid annotations summary")
            index = 0
            annotations = {}

            # Get the title, author, publisher from the first three lines
            title = lines[index]
            index += 1
            author = lines[index]
            index += 1
            publisher = lines[index]
            index += 1

            # Next line should be the first timestamp/location
            while index < len(lines):
                tsl = re.match(r'^(?P<timestamp>.*) \((?P<location>Page .*)\)', lines[index])
                if tsl:
                    ts = tsl.group('timestamp')
                    isoformat = parse_date(ts, as_utc=False)
                    isoformat = isoformat.replace(hour=12)
                    timestamp = mktime(isoformat.timetuple())
                    while timestamp in annotations:
                        timestamp += 60

                    location = tsl.group('location')
                    index += 1

                    # Continue with highlight
                    highlight_text = lines[index]
                    index += 1

                    # Next line is either Note: or a new tsl
                    note = re.match(r'^Notes: (?P<note_text>.*)', lines[index])
                    note_text = None
                    if note:
                        note_text = note.group('note_text')
                        index += 1

                    if re.match(r'^(?P<timestamp>.*) \((?P<location>Page .*)\)', lines[index]):
                        # New note - store the old one, continue
                        ann = AnnotationStruct()
                        ann.book_id = mi.id
                        ann.annotation_id = index
                        ann.highlight_color = 'Yellow'
                        ann.highlight_text = highlight_text
                        ann.location = location
                        ann.location_sort = "%05d" % int(re.match(r'^Page (?P<page>\d+).*$', location).group('page'))
                        ann.note_text = note_text
                        ann.last_modification = timestamp

                        # Add annotation to db
                        annotations[timestamp] = ann
                        continue
                else:
                    # Store the last one
                    ann = AnnotationStruct()
                    ann.book_id = mi.id
                    ann.annotation_id = index
                    ann.highlight_color = 'Yellow'
                    ann.highlight_text = highlight_text
                    ann.location = location
                    ann.location_sort = "%05d" % int(re.match(r'^Page (?P<page>\d+).*$', location).group('page'))
                    ann.note_text = note_text
                    ann.last_modification = timestamp
                    annotations[timestamp] = ann
                    break
        except:
            if log_failure:
                self._log(" unable to parse %s Annotations" % self.app_name)
                self._log("{:~^80}".format(" Imported Annotation summary "))
                self._log(raw)
                self._log("{:~^80}".format(" end imported Annotations summary "))
                import traceback
                traceback.print_exc()
                msg = ('Unable to parse Annotation summary from %s. ' % self.app_name +
                    'Paste entire contents of emailed summary.')
                MessageBox(MessageBox.WARNING,
                    'Error importing annotations',
                    msg,
                    show_copy_button=False,
                    parent=self.opts.gui).exec_()
                self._log_location("WARNING: %s" % msg)
            return False

        # Populate a BookStruct
        book_mi = BookStruct()
        book_mi.active = True
        book_mi.author = author
        book_mi.book_id = mi.id
        book_mi.title = title
        book_mi.uuid = None
        book_mi.last_update = time.mktime(time.localtime())
        book_mi.reader_app = self.app_name
        book_mi.cid = mi.id
        book_mi.annotations = len(annotations)

        # Add book to books_db
        self.add_to_books_db(self.books_db, book_mi)
        self.annotated_book_list.append(book_mi)

        # Add the annotations
        for timestamp in sorted(annotations.keys()):
            self.add_to_annotations_db(self.annotations_db, annotations[timestamp])
            self.update_book_last_annotation(self.books_db, timestamp, mi.id)
            self.opts.pb.increment()
            self.update_book_last_annotation(self.books_db, timestamp, mi.id)

        # Update the timestamp
        self.update_timestamp(self.annotations_db)
        self.update_timestamp(self.books_db)
        self.commit()

        # Return True if successful
        return True
