#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import datetime, re, time

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)


# Change the class name to <app_name>ReaderApp, e.g. 'KindleReaderApp'
class SampleFetchingApp(USBReader):
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
    app_name = 'Sample'

    # Change this to True when developing a new class from this template
    SUPPORTS_FETCHING = False

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
        # Sample annotations, indexed by timestamp. Note that annotations may have
        # highlight_text, note_text, or both.
        dict_of_anns = {}
        ts = datetime.datetime(2012, 12, 4, 8, 15, 0)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 1,
                                'highlight_color': 'Gray',
                                'highlight_text': ['The first paragraph of the first highlight.',
                                                   'The second paragaph of the first highlight.'],
                               }
        ts = ts.replace(minute=16)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 1,
                                'highlight_color': 'Gray',
                                'highlight_text': ['The first paragraph of the second highlight.',
                                                   'The second paragaph of the second highlight.'],
                                'note_text': ['A note added to the second highlight']
                               }
        ts = ts.replace(minute=17)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 1,
                                'highlight_color': 'Gray',
                                'note_text': ['A note added to the third highlight']
                               }

        ts = datetime.datetime(2012, 12, 10, 9, 0, 0)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 2,
                                'highlight_color': 'Gray',
                                'highlight_text': ['The first paragraph of the first highlight.',
                                                   'The second paragaph of the first highlight.']
                               }
        ts = ts.replace(minute=1)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 2,
                                'highlight_color': 'Gray',
                                'highlight_text': ['The first paragraph of the second highlight.',
                                                   'The second paragaph of the second highlight.'],
                                'note_text': ['A note added to the second highlight']
                               }
        ts = ts.replace(minute=2)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 2,
                                'highlight_color': 'Gray',
                                'note_text': ['A note added to the third highlight']
                               }

        ts = datetime.datetime(2012, 12, 31, 23, 59, 0)
        dict_of_anns[time.mktime(ts.timetuple())] = {'book_id': 999,
                                'highlight_color': 'Gray',
                                'highlight_text': ['An orphan annotation (no book)']
                               }

        self.log("%s:get_active_annotations()" % self.app_name)

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
        for timestamp in sorted(dict_of_anns.iterkeys()):
            # Populate an AnnotationStruct with available data
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = dict_of_anns[timestamp]['book_id']
            ann_mi.last_modification = timestamp

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
        # Sample installed books indexed by book_id
        dict_of_books = {}
        dict_of_books[1] = {'author': 'John Smith',
                            'author_sort': 'Smith, John',
                            'title': 'The Book by John Smith',
                            'title_sort': 'Book by John Smith, The'}
        dict_of_books[2] = {'author': 'William Jones',
                            'author_sort': 'Jones, William',
                            'title': 'Learning Programming',
                            'title_sort': 'Learning Programming'}
        dict_of_books[3] = {'author': 'Matthew Williams',
                            'author_sort': 'Williams, Matthew',
                            'title': 'A Book With No Annotations',
                            'title_sort': 'Book With No Annotations, A'}

        self.log("%s:get_installed_books()" % self.app_name)
        self.installed_books = []

        # Don't change the template of books_db string
        books_db = "%s_books_%s" % (re.sub(' ', '_', self.app_name), re.sub(' ', '_', self.opts.device_name))
        installed_books = set([])

        # Create the books table
        self.create_books_table(books_db)

        # Initialize the progress bar
        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.set_maximum(len(dict_of_books))

        #  Add installed books to the database
        for book_id in dict_of_books:
            # Add book_id to list of installed_books (make this a sql function)
            installed_books.add(book_id)

            # Populate a BookStruct with available metadata
            book_mi = BookStruct()

            # Required items
            book_mi.active = True
            book_mi.author = dict_of_books[book_id]['author']
            book_mi.book_id = book_id
            book_mi.reader_app = self.app_name
            book_mi.title = dict_of_books[book_id]['title']

            # Optional items
            if 'author_sort' in dict_of_books[book_id]:
                book_mi.author_sort = dict_of_books[book_id]['author_sort']
            if 'genre' in dict_of_books[book_id]:
                book_mi.genre = dict_of_books[book_id]['genre']
            if 'title_sort' in dict_of_books[book_id]:
                book_mi.title_sort = dict_of_books[book_id]['title_sort']
            if 'uuid' in dict_of_books[book_id]:
                book_mi.uuid = dict_of_books[book_id]['uuid']

            # Add book to books_db
            self.add_to_books_db(books_db, book_mi)

            # Increment the progress bar
            self.opts.pb.increment()

        # Update the timestamp
        self.update_timestamp(books_db)
        self.commit()

        self.installed_books = list(installed_books)
