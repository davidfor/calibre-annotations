#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import glob, os, re

from time import localtime, mktime

from calibre.utils.date import parse_date

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)


class KindleReaderApp(USBReader):
    """
    Kindle USB implementation
    Fetching annotations takes place in two stages:
    1) get_installed_books():
        add the installed books' metadata to the database
    2) get_active_annotations():
        add the annotations for installed books to the database
    """
    # The app name should be the primary name of the device from the
    # device's name property, e.g., 'Kindle' or 'SONY'
    app_name = 'Kindle'

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
        self._parse_my_clippings()

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

        # Get books added to Kindle by calibre
        resolved_path_map = self._get_installed_books(path_map)

        # Add books added to Kindle by WhisperNet or download
        resolved_path_map = self._get_imported_books(resolved_path_map)

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
        self.opts.pb.set_maximum(len(resolved_path_map))

        #  Add installed books to the database
        for book_id in resolved_path_map:
            mi = self._get_metadata(resolved_path_map[book_id])
            self._log('Book on device title: %s', (mi.title))
            if 'News' in mi.tags:
                if not self.collect_news_clippings:
                    continue
                installed_books.add(self.news_clippings_cid)
            else:
                installed_books.add(book_id)

            #self._log(mi.standard_field_keys())
            # Populate a BookStruct with available metadata
            book_mi = BookStruct()
            book_mi.path = resolved_path_map[book_id]

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
            if mi.tags:
                book_mi.genre = ', '.join([tag for tag in mi.tags])
            if 'News' in mi.tags:
                book_mi.book_id = self.news_clippings_cid

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
            self.installed_books_by_title[mi.title] = {'book_id': book_id, 'author_sort': mi.author_sort}

            # Increment the progress bar
            self.opts.pb.increment()

        self.opts.pb.hide()
        # Update the timestamp
        self.update_timestamp(self.books_db)
        self.commit()

        self.installed_books = list(installed_books)

    # Helpers
    def _get_installed_books(self, path_map):
        KINDLE_FORMATS = [u'azw', u'azw1', u'azw3', u'mobi']
        kindle_formats = set(KINDLE_FORMATS)

        def resolve_paths(storage, path_map):
            resolved_path_map = {}
            for id in path_map:
                # Generate a set of this book's formats in calibre
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)

                for vol in storage:
                    book_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'), vol)
                    book_extensions = file_fmts.intersection(kindle_formats)
                    found = False
                    for extension in book_extensions:
                        this_fmt = book_path.replace('bookmark', extension)
                        if os.path.exists(this_fmt):
                            resolved_path_map[id] = this_fmt
                            found = True
                            break
                    if found:
                        break
            return resolved_path_map

        storage = self.get_storage()
        return resolve_paths(storage, path_map)

    def _get_metadata(self, path):
        from calibre.ebooks.metadata.mobi import get_metadata
        with open(path, 'rb') as f:
            mi = get_metadata(f)
        return mi

    def _get_my_clippings(self):
        storage = self.get_storage()
        for vol in storage:
            mc_path = os.path.join(vol, 'My Clippings.txt')
            if os.path.exists(mc_path):
                return mc_path
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
            templates = ['*.azw', '*.mobi', '*.pobi']
            for template in templates:
                imported_books = glob.iglob(os.path.join(vol, template))
                for path in imported_books:
                    book_mi = self._get_metadata(path)

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

    def _parse_my_clippings(self):
        import ParseKindleMyClippingsTxt
        def log(level, msg, self=self):
            self._log('ParseKindleMyClippingsTxt '+level+': '+msg)
        ParseKindleMyClippingsTxt.log = log
        annos = ParseKindleMyClippingsTxt.FromFileName(self._get_my_clippings())
        self._log(" Number of entries retreived from 'My Clippings.txt'=%d" % (len(annos)))
        for anno in annos:
            title = anno.title.decode('utf-8')
            self._log("  title==%s" % (title))
            # If title/author_sort match book in library,
            # consider this an active annotation
            book_id = None
            if title in self.installed_books_by_title.keys():
                book_id = self.installed_books_by_title[title]['book_id']
                self._log("   Found book_id=%d" % (book_id))
            if not book_id:
                self._log("  Title not found in books on device")
                continue
            if anno.time:
                timestamp = mktime(anno.time.timetuple())
            else:
                self._log(" Unable to parse entries from 'My Clippings.txt'")
                timestamp = mktime(localtime())
            while timestamp in self.active_annotations:
                timestamp += 1
            self.active_annotations[timestamp] = {
                'annotation_id': timestamp,
                'book_id': book_id,
                'highlight_color': 'Gray',
                'location': anno.begin if anno.begin is not None else 'Unknown',
                'location_sort': "%06d" % anno.begin if anno.begin is not None else "000000"
                }
            if anno.kind == 'highlight':
                self.active_annotations[timestamp]['highlight_text'] = anno.text.decode('utf-8').split(u'\n')
            elif anno.kind == 'note':
                self.active_annotations[timestamp]['note_text'] = anno.text.decode('utf-8').split(u'\n')
            else:
                self._log("  Clipping is not a highlight or note")

    def _parse_my_clippings_original(self):
        '''
        Parse MyClippings.txt for entries matching installed books.
        File should end with SEPARATOR and a newline.
        '''
        SEPARATOR = '=========='
        cp = self._get_my_clippings()
        timestamp_parse_failed = False
        if cp:
            lines = []
            # Apparently new MyClippings.txt files are encoded UTF-8 with BOM
            with open(cp) as clippings:
                for line in clippings:
                    stripped = line.decode('utf-8-sig')
                    lines.append(stripped)

            index = 0
            line = lines[index]
            while True:
                # Get to the first title (author_sort) line
                if re.match(r'(?P<title>.*)\((?P<author_sort>.*)\)', lines[index]):
                    break
                else:
                    while not re.match(r'(?P<title>.*)\((?P<author_sort>.*)\)', lines[index]):
                        index += 1
                    break

            while index < len(lines) - 1:
                try:
                    line = lines[index]
                    book_id = None

                    # 1. Get the title/author_sort pair
                    tas = re.match(r'(?P<title>.*)\((?P<author_sort>.*)\)', line)
                    title = tas.group('title').rstrip()
                    author_sort = tas.group('author_sort')
                    # If title/author_sort match book in library,
                    # consider this an active annotation
                    if title in self.installed_books_by_title.keys():
                        book_id = self.installed_books_by_title[title]['book_id']
                    index += 1

                    # 2. Get [Highlight|Bookmark Location|Note]
                    line = lines[index]
                    ann_type = None
                    if 'Highlight' in line:
                        ann_type = 'Highlight'
                    elif 'Bookmark' in line:
                        ann_type = 'Bookmark'
                    elif 'Note' in line:
                        ann_type = 'Note'
                    # Kindle PW uses 'Location', K3 uses 'Loc.'. German uses 'Position'
                    # K3 does not store location with Bookmarks. Whatever.
                    loc = re.match(r'.* (?P<location>(Location|Loc\.|Position) [0-9,-]+).*', line)
                    location = 'Unknown'
                    location_sort = "000000"
                    if loc:
                        location = loc.group('location')
                        location_sort = "%06d" % int(re.match(r'^(Loc\.|Location|Position) (?P<loc>[0-9]+).*$', location).group('loc'))

                    # Try to read the timestamp, fallback to local time
                    try:
                        tstring = re.match(r'.*Added on (?P<timestamp>.*$)', line)
                        ts = tstring.group('timestamp')
                        isoformat = parse_date(ts, as_utc=False)
                        timestamp = mktime(isoformat.timetuple())
                    except:
                        if not timestamp_parse_failed:
                            self._log(" Unable to parse entries from 'My Clippings.txt'")
                            self._log(" %s driver supports English only." % self.app_name)
                            timestamp_parse_failed = True
                        timestamp = mktime(localtime())
                        while timestamp in self.active_annotations:
                            timestamp += 1
                    index += 1

                    # 3. blank line(s)
                    while lines[index].strip() == '':
                        index += 1

                    # 4. highlight or note
                    item = lines[index]
                    highlight_text = None
                    note_text = None
                    if ann_type == 'Highlight':
                        highlight_text = [unicode(item)]
                        index += 1
                        while lines[index].strip() != SEPARATOR:
                            highlight_text.append(unicode(lines[index]))
                            index += 1
                    elif ann_type == 'Note':
                        note_text = [unicode(item)]
                        index += 1
                        while lines[index].strip() != SEPARATOR:
                            note_text.append(unicode(lines[index]))
                            index += 1
                    # Pass SEPARATOR
                    index += 1

                    # 5. Store the active_annotation
                    if book_id:
                        # Notes and highlights are created simultaneously
                        if timestamp not in self.active_annotations:
                            self.active_annotations[timestamp] = {
                                'annotation_id': timestamp,
                                'book_id': book_id,
                                'highlight_color': 'Gray',
                                'location': location,
                                'location_sort': location_sort
                                }
                        if highlight_text is not None:
                            self.active_annotations[timestamp]['highlight_text'] = highlight_text
                        if note_text is not None:
                            self.active_annotations[timestamp]['note_text'] = note_text
                except:
                    # Unexpected EOF. Return with whatever we have
                    self._log_location("failed with line: %s" % repr(line))
                    import traceback
                    traceback.print_exc()
                    return