#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2018-2019, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import glob, os, re

from time import localtime, mktime

from calibre.utils.date import parse_date

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)

TOLINO_FORMATS = [u'epub', u'pdf', u'txt']
TOLINO_TEMPLATES = ['*.epub', '*.pdf', '*.txt']
NOTES_FILENAMES = ['notes.txt']

class TolinoReaderApp(USBReader):
    """
    Tolino USB implementation
    Fetching annotations takes place in two stages:
    1) get_installed_books():
        add the installed books' metadata to the database
    2) get_active_annotations():
        add the annotations for installed books to the database
    """
    # The app name should be the primary name of the device from the
    # device's name property, e.g., 'Kindle' or 'SONY'
    app_name = 'Tolino'

    # Fetch the active annotations, construct an AnnotationStruct, add them to
    # the self.annotations_db
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

        self.active_annotations = {}

        self.opts.pb.set_label("Getting active annotations for %s" % self.app_name)
        self.opts.pb.set_value(0)

        # Don't change the template of the _db strings
        #self.books_db = "%s_books_%s" % (re.sub(' ', '_', self.app_name), re.sub(' ', '_', self.opts.device_name))
        #self.annotations_db = "%s_annotations_%s" % (re.sub(' ', '_', self.app_name), re.sub(' ', '_', self.opts.device_name))
        self.annotations_db = self.generate_annotations_db_name(self.app_name_, self.opts.device_name)
        self.books_db = self.generate_books_db_name(self.app_name_, self.opts.device_name)

        # Create the annotations table
        self.create_annotations_table(self.annotations_db)

        # Parse MyClippings.txt for entries matching installed_books
        self._parse_tolino_notes()

        # Initialize the progress bar
        self.opts.pb.set_label("Getting highlights from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.show()
        self.opts.pb.set_maximum(len(self.active_annotations))

        # Add annotations to the database
        for timestamp in sorted(self.active_annotations.iterkeys()):
            # Populate an AnnotationStruct with available data
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = self.active_annotations[timestamp]['book_id']
            ann_mi.last_modification = timestamp

            this_is_news = self.collect_news_clippings and 'News' in self.get_genres(self.books_db, ann_mi.book_id)

            # Optional items
            if 'annotation_id' in self.active_annotations[timestamp]:
                ann_mi.annotation_id = self.active_annotations[timestamp]['annotation_id']
            if 'highlight_color' in self.active_annotations[timestamp]:
                ann_mi.highlight_color = self.active_annotations[timestamp]['highlight_color']
            if 'highlight_text' in self.active_annotations[timestamp]:
                highlight_text = '\n'.join(self.active_annotations[timestamp]['highlight_text'])
                ann_mi.highlight_text = highlight_text
            if this_is_news:
                ann_mi.location = self.get_title(self.books_db, ann_mi.book_id)
                ann_mi.location_sort = timestamp
            else:
                if 'location' in self.active_annotations[timestamp]:
                    ann_mi.location = self.active_annotations[timestamp]['location']
                if 'location_sort' in self.active_annotations[timestamp]:
                    ann_mi.location_sort = self.active_annotations[timestamp]['location_sort']
            if 'note_text' in self.active_annotations[timestamp]:
                note_text = '\n'.join(self.active_annotations[timestamp]['note_text'])
                ann_mi.note_text = note_text

            # Add annotation to self.annotations_db
            self.add_to_annotations_db(self.annotations_db, ann_mi)

            # Increment the progress bar
            self.opts.pb.increment()

            # Update last_annotation in self.books_db
            self.update_book_last_annotation(self.books_db, timestamp, ann_mi.book_id)

        self.opts.pb.hide()

        # Update the timestamp
        self.update_timestamp(self.annotations_db)
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
        self._log("%s:get_installed_books()" % self.app_name)
        self.installed_books = []

        self.device = self.opts.gui.device_manager.device
        path_map = self.get_path_map()

        # Calibre already knows what books are on the device, so use it.
        db = self.opts.gui.library_view.model().db
        self.onDeviceIds = set(db.search_getting_ids('ondevice:True', None, sort_results=False, use_virtual_library=False))

        # Add books added to Tolino by WhisperNet or download
#         resolved_path_map = self._get_imported_books(resolved_path_map)

        self.books_db = self.generate_books_db_name(self.app_name_, self.opts.device_name)

        installed_books = set([])

        # Used by get_active_annotations() to look up metadata based on title
        self.installed_books_by_title = {}

        # Create the books table
        self.create_books_table(self.books_db)

        # Initialize the progress bar
        self.opts.pb.set_label("Getting installed books from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.show()
        self.opts.pb.set_maximum(len(self.onDeviceIds))

        #  Add installed books to the database
        for book_id in self.onDeviceIds:
            try:
                library_mi = mi = db.get_metadata(book_id, index_is_id=True)
            except Exception as e:
                self._log("Unable to get metadata from book. book_id='%s'" % (book_id))
                self._log(" Exception thrown was=%s" % (str(e)))
                continue

            self._log("Book on device title: '%s'" % (mi.title))
            for model in (self.opts.gui.memory_view.model(),
                               self.opts.gui.card_a_view.model(),
                               self.opts.gui.card_b_view.model()):
                model_paths = model.paths_for_db_ids(set([book_id]), as_map=True)[book_id]
                if model_paths:
                    device_path = model_paths[0].path
                    self._log(" Book on device path: '%s'" % (device_path,))
                    mi = self._get_metadata(device_path)
#                     self._log(" Book on device path: '%s'" % (mi,))
                    break
                    

            if 'News' in mi.tags:
                if not self.collect_news_clippings:
                    continue
                installed_books.add(self.news_clippings_cid)
            else:
                installed_books.add(book_id)

            #self._log(mi.standard_field_keys())
            # Populate a BookStruct with available metadata
            book_mi = BookStruct()
#             book_mi.path = resolved_path_map[book_id]

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
            book_mi.title = mi.title.strip()
            # Add book to indexed_books
            self.installed_books_by_title[mi.title] = {'book_id': book_id, 'author_sort': mi.author_sort}

            # Optional items
            if mi.tags:
                book_mi.genre = ', '.join([tag for tag in mi.tags])
            if 'News' in mi.tags:
                book_mi.book_id = self.news_clippings_cid

            if hasattr(mi, 'author_sort'):
                book_mi.author_sort = mi.author_sort
            self.installed_books_by_title[mi.title]['author_sort'] = mi.author_sort

            if hasattr(mi, 'title_sort'):
                book_mi.title_sort = mi.title_sort
            else:
                book_mi.title_sort = re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', mi.title).rstrip()

            if hasattr(library_mi, 'uuid'):
                self._log(" Book on has uuid: '%s'" % (library_mi.uuid,))
                book_mi.uuid = library_mi.uuid
                self.installed_books_by_title[mi.title]['uuid'] = book_mi.uuid

            # Add book to self.books_db
            self.add_to_books_db(self.books_db, book_mi)


            # Increment the progress bar
            self.opts.pb.increment()

        self.opts.pb.hide()
        # Update the timestamp
        self.update_timestamp(self.books_db)
        self.commit()

        self.installed_books = list(installed_books)


    def _get_metadata(self, path):
        mi = self.device.metadata_from_path(path)
        return mi

    def _get_notes(self):
        self._log("TolinoReaderApp::_get_notes - start")
        storage = self.get_storage()
        self._log("TolinoReaderApp::_get_notes - storage='%s'" % (storage,))
        for vol in storage:
            self._log("TolinoReaderApp::_get_notes - vol='%s'" % (vol,))
            book_path = self.device.ebook_dir_for_upload
            vol = vol[:-len(book_path)] if vol.endswith(book_path) else vol
            for filename in NOTES_FILENAMES:
                notes_filepath = os.path.join(vol, filename)
                self._log("TolinoReaderApp::_get_notes - filename='%s', notes_filepath='%s'" % (filename,notes_filepath))
                if os.path.exists(notes_filepath):
                    self._log("TolinoReaderApp::_get_notes - found!!! filename='%s', notes_filepath='%s'" % (filename,notes_filepath))
                    return notes_filepath
        return None

    def _get_imported_books(self, resolved_path_map):
        '''
        Add books in top-level documents folder to path_map, possibly added by whispernet
        '''
        if self.parent.library_scanner.isRunning():
            self.parent.library_scanner.wait()

        unrecognized_index = -1
        storage = self.get_storage()
        for vol in storage:
            templates = TOLINO_TEMPLATES
            for template in templates:
                self._log("    Searching for books on vol=%s using template=%s" % (vol,template))
                imported_books = glob.iglob(os.path.join(vol, template))
                for path in imported_books:
                    self._log("    Have possible book with path=%s" % (path))
                    try:
                        book_mi = self._get_metadata(path)
                    except Exception as e:
                        self._log("    Unable to get metadata from book. path=%s" % (path))
                        self._log("    Exception thrown was=%s" % (str(e)))
                        continue

                    if 'News' in book_mi.tags:
                        if self.collect_news_clippings:
                            resolved_path_map[self.news_clippings_cid] = path
                            continue

                    if book_mi.uuid in self.parent.library_scanner.uuid_map:
                        matched_id = self.parent.library_scanner.uuid_map[book_mi.uuid]['id']
                        if not matched_id in resolved_path_map:
                            resolved_path_map[matched_id] = path
                    else:
                        resolved_path_map[unrecognized_index] = path
                        unrecognized_index -= 1

        return resolved_path_map

    def _parse_tolino_notes(self):
        import ParseTolinoNotesTxt
        def log(level, msg, self=self):
            self._log('ParseTolinoNotesTxt '+level+': '+msg)
        ParseTolinoNotesTxt.log = log
        annos = ParseTolinoNotesTxt.FromFileName(self._get_notes())
        self._log(" Number of entries retrieved from 'notes.txt'=%d" % (len(annos)))
        for anno in annos:
            title = anno.title.decode('utf-8')
            self._log("  Annotation for Title=='%s'" % (title))
            # If title/author_sort match book in library,
            # consider this an active annotation
            book_id = None
            title = title.strip()
            if title in self.installed_books_by_title.keys():
                book_id = self.installed_books_by_title[title]['book_id']
                self._log("    Found book_id=%d" % (book_id))
                self._log("    Found book=%s" % (self.installed_books_by_title[title],))
            if not book_id:
                self._log("    Title not found in books on device")
                continue
            if anno.time:
                timestamp = mktime(anno.time)
            else:
                self._log("    Unable to parse entries from 'notes.txt'")
                timestamp = mktime(localtime())
            while timestamp in self.active_annotations:
                timestamp += 1
            self.active_annotations[timestamp] = {
                'annotation_id': timestamp,
                'book_id': book_id,
                'highlight_color': 'Gray',
                'location': _("Page: {0}").format(anno.page_str) if anno.page_str is not None else 'Unknown',
                'location_sort': "%06d" % anno.page if anno.page is not None else "000000",
                'confidence': 5,
                }
            if hasattr(self.installed_books_by_title[title], 'uuid'):
                self._log(" _parse_tolino_notes - Book on has uuid: '%s'" % (self.installed_books_by_title[title]['uuid'],))
                self.active_annotations[timestamp]['uuid'] = self.installed_books_by_title[title]['uuid']
#             if anno.kind == 'highlight':
            if anno.highlight_text:
                self.active_annotations[timestamp]['highlight_text'] = anno.highlight_text.decode('utf-8').split(u'\n')
#             elif anno.kind == 'note':
            if anno.note_text:
                self.active_annotations[timestamp]['note_text'] = anno.note_text.decode('utf-8').split(u'\n')
#             else:
#                 self._log("    Notes.txt entry is not a highlight or note")
                
