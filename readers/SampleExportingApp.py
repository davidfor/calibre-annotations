#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import datetime, time

from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)
from calibre_plugins.annotations.reader_app_support import ExportingReader


class SampleExportingApp(ExportingReader):
    """
    Sample implementation
    """

    # app_name should be the same as the class name
    app_name = 'SampleExportingApp'

    if True:
        import_help_text = ('''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <title>Exporting from SampleExportingApp</title>
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
                <h3>Exporting annotations from SampleExportingApp</h3>
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
                <h3>Importing SampleExportingApp annotations to calibre</h3>
                <div class="steps_with_header_indent">
                  <p><i>After receiving the emailed annotations summary on your computer:</i></p>
                  <ol>
                    <li>Copy the contents of the annotations summary email</li>
                    <li>Paste the annotations to the <b>Import SampleExportingApp annotations</b> window</li>
                    <li>Click <b>Import</b></li>
                  </ol>
                </div>
            </body>
            </html>''')

    initial_dialog_text = 'Junk'
    import_fingerprint = False
    import_dialog_title = "Import {0} annotations".format(app_name)

    # Change this to True when developing a new class from this template
    SUPPORTS_EXPORTING = True

    # If this is set to true, a text dialog will be shown prior to calling parse_exported_highlights
    # and the contents of the dialog will be passed in via the raw parameter
    # If set to false, no dialog will be displayed and parse_exported_highlights will be called with raw == "-"
    REQUIRES_TEST_INPUT = True

    # If this is set to true, it means the class needs the user to select a book prior to invoking this action.
    # If a book isn't selected, the user will receive a warning and nothing will happen
    # If this is set to false, the user can call the class with 0 or more books selected, it's up to you to handle all scenarios
    REQUIRES_BOOK_SELECTED = True

    # Change this to True to use a file chooser instead of text input box for import
    SUPPORTS_FILE_CHOOSER = False
    import_file_name_filter = "All files (*)"


    # Sample annotations, indexed by timestamp. Note that annotations may have
    # highlight_text, note_text, or both. 'location' might reference a page number from
    # a PDF.
    highlights = {}
    ts = datetime.datetime(2012, 12, 4, 8, 15, 0)
    highlights[time.mktime(ts.timetuple())] = {'book_id': 1,
        'highlight_color': 'Green',
        'highlight_text': ['The first paragraph of the first highlight.',
                           'The second paragaph of the first highlight.'],
        'location': 17,
        }
    ts = ts.replace(minute=16)
    highlights[time.mktime(ts.timetuple())] = {'book_id': 1,
        'highlight_color': 'Pink',
        'highlight_text': ['The first paragraph of the second highlight.',
                           'The second paragaph of the second highlight.'],
        'location': 23,
        'note_text': ['A note added to the second highlight'],
        }
    ts = ts.replace(minute=17)
    highlights[time.mktime(ts.timetuple())] = {'book_id': 1,
        'location': 47,
        'note_text': ['A note added to the third highlight']
        }

    def parse_exported_highlights(self, raw):
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
        self._log("%s:parse_exported_highlight()" % self.app_name)

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

        # Populate author, title at a minimum
        title = "A Book With Some Exported Annotations"
        author = "John Smith"

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
        book_mi.annotations = len(self.highlights)

        # Add annotations to the database
        for timestamp in sorted(self.highlights.keys()):
            book_mi.last_update = timestamp

            # Populate an AnnotationStruct
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = book_mi['book_id']
            ann_mi.last_modification = timestamp

            # Optional items
            if 'annotation_id' in self.highlights[timestamp]:
                ann_mi.annotation_id = self.highlights[timestamp]['annotation_id']
            if 'highlight_color' in self.highlights[timestamp]:
                ann_mi.highlight_color = self.highlights[timestamp]['highlight_color']
            if 'highlight_text' in self.highlights[timestamp]:
                highlight_text = '\n'.join(self.highlights[timestamp]['highlight_text'])
                ann_mi.highlight_text = highlight_text
            if 'note_text' in self.highlights[timestamp]:
                note_text = '\n'.join(self.highlights[timestamp]['note_text'])
                ann_mi.note_text = note_text

            # Add annotation to annotations_db
            self.add_to_annotations_db(self.annotations_db, ann_mi)

            # Increment the progress bar
            self.opts.pb.increment()

            # Update last_annotation in books_db
            self.update_book_last_annotation(self.books_db, timestamp, ann_mi.book_id)

        # Add book to books_db
        self.add_to_books_db(self.books_db, book_mi)
        self.annotated_book_list.append(book_mi)

        # Update the timestamp
        self.update_timestamp(self.annotations_db)
        self.update_timestamp(self.books_db)
        self.commit()

        # Return True if successful
        return True
