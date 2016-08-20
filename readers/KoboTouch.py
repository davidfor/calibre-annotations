#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014-2016, David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import datetime, re, time, os
from time import mktime

from calibre_plugins.annotations.reader_app_support import USBReader
from calibre_plugins.annotations.common_utils import (AnnotationStruct, BookStruct)


# Change the class name to <app_name>ReaderApp, e.g. 'KindleReaderApp'
class KoboFetchingApp(USBReader):
    """
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
    app_name = 'Kobo'
#    MERGE_INDEX = "timestamp"

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
        self._log("%s:get_active_annotations() - annotations_db=%s, books_db=%s" % (self.app_name, annotations_db, self.books_db))

        # Create the annotations table
        self.create_annotations_table(annotations_db)

        self._fetch_annotations()
        # Initialize the progress bar
        self.opts.pb.set_label("Getting highlights from %s" % self.app_name)
        self.opts.pb.set_value(0)
        self.opts.pb.set_maximum(len(self.active_annotations))

        # Add annotations to the database
        for annotation in sorted(self.active_annotations.itervalues(), key=lambda k: (k['book_id'], k['last_modification'])):
            # Populate an AnnotationStruct with available data
            ann_mi = AnnotationStruct()

            # Required items
            ann_mi.book_id = annotation['book_id']
            ann_mi.last_modification = annotation['last_modification']

            # Optional items
            if 'annotation_id' in annotation:
                ann_mi.annotation_id = annotation['annotation_id']
            if 'highlight_color' in annotation:
                ann_mi.highlight_color = annotation['highlight_color']
            if 'highlight_text' in annotation:
#                 self._log("get_active_annotations() - annotation['highlight_text']={0}".format(annotation['highlight_text']))
                highlight_text = annotation['highlight_text']
                ann_mi.highlight_text = highlight_text
            if 'note_text' in annotation:
                note_text = annotation['note_text']
                ann_mi.note_text = note_text
            if 'location' in annotation:
                ann_mi.location = annotation['location']
            if 'location_sort' in annotation:
                ann_mi.location_sort = annotation['location_sort']
#            self._log(ann_mi)

            # Add annotation to annotations_db
            self.add_to_annotations_db(annotations_db, ann_mi)

            # Increment the progress bar
            self.opts.pb.increment()

#             self._log("%s:get_active_annotations() - books_db=%s" % (self.app_name, self.books_db))
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
        self._log("%s:get_installed_books() - about to call self.get_path_map" % self.app_name)
        path_map = self.get_path_map()
#        self._log(path_map)

        # Get books added to Kindle by calibre
        self._log("%s:get_installed_books() - about to call self._get_installed_books" % self.app_name)
#        resolved_path_map = self._get_installed_books(path_map)

        # Calibre already knows what books are on the device, so use it.
        db = self.opts.gui.library_view.model().db
        self.onDeviceIds = set(db.search_getting_ids('ondevice:True', None, sort_results=False, use_virtual_library=False))

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
#            self._log_location("book: {0} - {1}".format(mi.authors, mi.title))
#            self._log("mi={0}".format(mi))
            installed_books.add(book_id)

            #self._log(mi.standard_field_keys())
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
            self.installed_books_by_title[mi.title] = {'book_id': book_id, 'author_sort': mi.author_sort}

            # Increment the progress bar
            self.opts.pb.increment()

        # Update the timestamp
        self.update_timestamp(self.books_db)
        self.commit()

        self.installed_books = list(installed_books)
        self._log_location("Finish!!!!")

    def _get_installed_books(self, path_map):
        self._log_location("Start!!!!")
        EPUB_FORMATS = [u'epub']
        epub_formats = set(EPUB_FORMATS)

        def resolve_paths(storage, path_map):
            pop_list = []
            resolved_path_map = {}
            for _id in path_map:
#                self._log("resolve_paths path=%s" % path_map[id]['path'])
                extension =  os.path.splitext(path_map[_id]['path'])[1][1:]
#                self._log("resolve_paths extension=%s" % extension)
                if extension in EPUB_FORMATS:
                    self._log("resolve_paths path=%s" % path_map[_id]['path'])

                    for vol in storage:
                        bkmk_path = path_map[_id]['path']
                        if os.path.exists(bkmk_path):
                            resolved_path_map[_id] = bkmk_path
                            break
                        else:
                            pop_list.append(_id)
                else:
                    pop_list.append(_id)

            # Remove non-existent bookmark templates
            for _id in pop_list:
                path_map.pop(_id)
            return resolved_path_map

        storage = self.get_storage()
        self._log_location("Finish!!!!")
        return resolve_paths(storage, path_map)

    def _get_metadata(self, path):
        from calibre.ebooks.metadata.epub import get_metadata
        self._log_location("_get_metadata: path=%s" % path)
        with open(path, 'rb') as f:
            mi = get_metadata(f)
        self._log_location("Finish!!!!")
        return mi


    def _fetch_annotations(self):
        self._log_location("Start!!!!")
        
        count_bookmark_query = ('SELECT COUNT(*) AS num_bookmarks '
                                'FROM Bookmark bm LEFT OUTER JOIN Content c ON '
                                    'bm.ContentID = c.ContentID '
                                'WHERE bm.Hidden = "false" ')
        bookmark_query = (
                        'SELECT bm.bookmarkid, bm.ContentID, bm.volumeid, bm.text, bm.annotation, bm.ChapterProgress, ' 
                                'bm.StartContainerChildIndex, bm.StartOffset, c.BookTitle, c.TITLE, c.volumeIndex, '
                                'c.___NumPages, IFNULL(bm.DateModified, bm.DateCreated) as DateModified, '
                                'c.MimeType, c.VolumeIndex, bm.DateCreated '
                        'FROM Bookmark bm LEFT OUTER JOIN Content c ON bm.ContentID = c.ContentID ' 
                        'WHERE bm.Hidden = "false" '
                        'AND MimeType NOT IN ("application/xhtml+xml", "application/x-kobo-epub+zip") '
                        'ORDER BY bm.volumeid, bm.DateCreated, c.VolumeIndex, bm.chapterprogress'
                        )
        kepub_bookmark_query = (
                               'SELECT bm.bookmarkid, bm.ContentID, bm.volumeid, bm.text, bm.annotation, bm.ChapterProgress, '
                                    'bm.StartContainerChildIndex, bm.StartOffset, c.BookTitle, c.TITLE, c.volumeIndex, ' 
                                    'c.___NumPages, IFNULL(bm.DateModified, bm.DateCreated) as DateModified, ' 
                                    'c.MimeType, c.VolumeIndex, bm.DateCreated ' 
                                'FROM Bookmark bm LEFT OUTER JOIN Content c '
                                'WHERE bm.Hidden = "false" '
                                'AND MimeType IN ("application/xhtml+xml", "application/x-kobo-epub+zip") '
                                'AND ContentType = 899 '
                                'AND c.ContentID LIKE bm.ContentID || "-%" '
                                'AND bm.VolumeID = c.BookID '
                                'ORDER BY bm.volumeid, bm.DateCreated, c.VolumeIndex, bm.chapterprogress'
                               )
        def _convert_calibre_ids_to_books(db, ids):
            books = []
            for book_id in ids:
                book = self._convert_calibre_id_to_book(db, book_id)
                books.append(book)
            return books
    
        def _convert_calibre_id_to_book(db, book_id):
            mi = db.get_metadata(book_id, index_is_id=True, get_cover=True)
            book = Book('', 'lpath', title=mi.title, other=mi)
            book.calibre_id  = mi.id
            return book


        # Generate a path_map from selected ids
        def get_ids_from_selected_rows():
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 1:
                rows = xrange(self.gui.library_view.model().rowCount(QModelIndex()))
            ids = map(self.gui.library_view.model().id, rows)
            return ids

        def get_formats(_id):
            formats = db.formats(_id, index_is_id=True)
            fmts = []
            if formats:
                for format in formats.split(','):
                    fmts.append(format.lower())
            return fmts

        def get_device_path_from_id(id_):
            paths = []
            for x in ('memory', 'card_a', 'card_b'):
                x = getattr(self.gui, x+'_view').model()
                paths += x.paths_for_db_ids(set([id_]), as_map=True)[id_]
            return paths[0].path if paths else None

        def generate_annotation_paths(ids, db, device):
            # Generate path templates
            # Individual storage mount points scanned/resolved in driver.get_annotations()
            path_map = {}
            for _id in ids:
                paths = self.get_device_paths_from_id(_id)
#                self._log("generate_annotation_paths - paths={0}".format(paths))
                if len(paths) > 0:
                    the_path = paths[0]
                    if len(paths) > 1:
                        if os.path.splitext(paths[0]) > 1: # No extension - is kepub
                            the_path = paths[1]
                    contentId = self.device.contentid_from_path(the_path, 6)
#                     path_map[_id] = dict(path=the_path, fmts=get_formats(_id))
                    path_map[contentId] = dict(path=the_path, fmts=get_formats(_id), book_id=_id)
            return path_map

        db = self.opts.gui.library_view.model().db
        if not self.onDeviceIds:
            self.onDeviceIds = set(db.search_getting_ids('ondevice:True', None, sort_results=False, use_virtual_library=False))
        
        if len(self.onDeviceIds) == 0:
            return
#        self._log("_fetch_annotations - onDeviceIds={0}".format(onDeviceIds))
        # Map ids to paths
        path_map = generate_annotation_paths(self.onDeviceIds, db, self.device)
#         self._log("_fetch_annotations - path_map={0}".format(path_map))

        from contextlib import closing
        import apsw
        with closing(apsw.Connection(self.device.device_database_path())) as connection:

            cursor = connection.cursor()
            cursor.execute(count_bookmark_query)
            try:
                result = cursor.next()
                count_bookmarks = result[0]
            except StopIteration:
                count_bookmarks = 0
            self._log("_fetch_annotations - Total number of bookmarks={0}".format(count_bookmarks))
            
            self._log("_fetch_annotations - About to get non-kepub annotations")
            self._read_database_annotations(cursor, bookmark_query, path_map)
            self._log("_fetch_annotations - Finished getting non-kepub annotations")
            self._log("_fetch_annotations - About to get kepub annotations")
            self._read_database_annotations(cursor, kepub_bookmark_query, path_map)
            self._log("_fetch_annotations - Finished getting kepub annotations")
        
        self._log_location("Finished!!!!")

    def _read_database_annotations(self, cursor, bookmark_query, path_map):
            self._log("_read_database_annotations - Starting fetch of bookmarks")
            cursor.execute(bookmark_query)

            last_contentId = None
            for row in cursor:
                self._log("_read_database_annotations - row={0}".format(row))
                contentId = row[2]
                if not last_contentId == contentId:
                    try: 
                        book_id = path_map[contentId]['book_id']
                    except:
                        continue
                bookmark_timestamp = convert_kobo_date(row[12])
                if row[12]:
                    bookmark_timestamp = mktime(bookmark_timestamp.timetuple())
                annotation_id   = row[0]
                chapter_title   = row[9]
                current_chapter = row[14]
                if current_chapter is None:
                    current_chapter = 0

                self.active_annotations[annotation_id] = {
                    'annotation_id': annotation_id,
                    'book_id': int(book_id),
                    'highlight_color': 'Gray',
                    'location': chapter_title,
                    'location_sort': "%06d" % (current_chapter  * 1000 + row[5] * 100),
                    'last_modification': bookmark_timestamp
                    }
                self.active_annotations[annotation_id]['highlight_text'] = row[3]
                self.active_annotations[annotation_id]['note_text'] = row[4]
#                    self._log(self.active_annotations[annotation_id])
                last_contentId = contentId

    def get_device_paths_from_id(self, book_id):
        paths = []
        for x in ('memory', 'card_a', 'card_b'):
            x = getattr(self.opts.gui, x+'_view').model()
            paths += x.paths_for_db_ids(set([book_id]), as_map=True)[book_id]
#        self._log("get_device_paths_from_id - paths=", paths)
        return [r.path for r in paths]



class KoboTouchFetchingApp(KoboFetchingApp):
    """
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
    app_name = 'KoboTouch'

class KoboTouchExtendedFetchingApp(KoboTouchFetchingApp):
    """
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
    app_name = 'KoboTouchExtended'


def convert_kobo_date(kobo_date):
    """
    KoBo stores dates as a timestamp string. The exact format has changed with firmware
    and what part of the firmware writes it. The following is overkill, but it handles all 
    the formats I have seen.
    """
    from calibre.utils.date import utc_tz, local_tz
    from calibre.devices.usbms.driver import debug_print
#     debug_print("convert_kobo_date - start - kobo_date={0}'".format(kobo_date))

    try:
        converted_date = datetime.datetime.strptime(kobo_date, "%Y-%m-%dT%H:%M:%S+00:00")
#         debug_print("convert_kobo_date - '%Y-%m-%dT%H:%M:%S+00:00' - kobo_date=%s' - kobo_date={0}'".format(kobo_date))
    except Exception as e:
#         debug_print("convert_kobo_date - exception={0}'".format(e))
        try:
            converted_date = datetime.datetime.strptime(kobo_date, "%Y-%m-%dT%H:%M:%SZ")
#             debug_print("convert_kobo_date - '%Y-%m-%dT%H:%M:%SZ' - kobo_date={0}'".format(kobo_date))
        except:
            try:
                converted_date = datetime.datetime.strptime(kobo_date[0:19], "%Y-%m-%dT%H:%M:%S")
#                 debug_print("convert_kobo_date - '%Y-%m-%dT%H:%M:%S' - kobo_date={0}'".format(kobo_date))
            except:
                try:
                    converted_date = datetime.datetime.strptime(kobo_date.split('+')[0], "%Y-%m-%dT%H:%M:%S")
#                     debug_print("convert_kobo_date - '%Y-%m-%dT%H:%M:%S' - kobo_date={0}'".format(kobo_date))
                except:
                    try:
                        converted_date = datetime.datetime.strptime(kobo_date.split('+')[0], "%Y-%m-%d")
    #                     converted_date = converted_date.replace(tzinfo=utc_tz)
#                         debug_print("convert_kobo_date - '%Y-%m-%d' - kobo_date={0}'".format(kobo_date))
                    except:
                        try:
                            from calibre.utils.date import parse_date
                            converted_date = parse_date(kobo_date)#, assume_utc=True)
#                             debug_print("convert_kobo_date - parse_date - kobo_date={0}'".format(kobo_date))
                        except:
                            converted_date = time.gmtime()
                            debug_print("convert_kobo_date - could not convert, using current time - kobo_date={0}'".format(kobo_date))
    
    converted_date = converted_date.replace(tzinfo=utc_tz).astimezone(local_tz)
    return converted_date

