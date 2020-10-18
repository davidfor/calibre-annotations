#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import io, os, re, sys
# calibre Python 3 compatibility.
import six
from six import text_type as unicode

from collections import OrderedDict
from datetime import datetime
from lxml import etree

try:
    from PyQt5.Qt import QModelIndex
except ImportError as e:
    from PyQt4.Qt import QModelIndex

from calibre.constants import islinux, isosx, iswindows
from calibre.devices.usbms.driver import debug_print
from calibre.ebooks.metadata import MetaInformation
from calibre.gui2 import error_dialog
from calibre.utils.filenames import shorten_components_to
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.zipfile import ZipFile

from calibre.utils.config import JSONConfig
plugin_prefs = JSONConfig('plugins/annotations')

try:
    debug_print("Annotations::reader_app_support.py - loading translations")
    load_translations()
except NameError:
    debug_print("Annotations::reader_app_support.py - exception when loading translations")
    pass # load_translations() added in calibre 1.9


class ClassNotImplementedException(Exception):
    ''' '''
    pass


class DatabaseNotFoundException(Exception):
    ''' '''
    pass


class NotImplementedException(Exception):
    pass


class UnknownAnnotationTypeException(Exception):
    ''' '''
    pass


class ReaderApp(object):

    BOOKS_DB_TEMPLATE = "{0}_{1}_books"
    ANNOTATIONS_DB_TEMPLATE = "{0}_{1}_annotations"

    reader_app_classes = None
    MAX_ELEMENT_DEPTH = 6
    SUPPORTS_EXPORTING = False
    SUPPORTS_FETCHING = False

    NSTimeIntervalSince1970 = 978307200.0

    LOCATION_TEMPLATE = "{cls}:{func}({arg1}) {arg2}"

    def _log(self, msg=None):
        '''
        Print msg to console
        '''
        if not plugin_prefs.get('cfg_plugin_debug_log_checkbox', False):
            return

        if msg:
            debug_print(" %s" % str(msg))
        else:
            debug_print()

    def _log_location(self, *args):
        '''
        Print location, args to console
        '''
        if not plugin_prefs.get('cfg_plugin_debug_log_checkbox', False):
            return

        arg1 = arg2 = ''

        if len(args) > 0:
            arg1 = str(args[0])
        if len(args) > 1:
            arg2 = str(args[1])

        debug_print(self.LOCATION_TEMPLATE.format(cls=self.__class__.__name__,
                    func=sys._getframe(1).f_code.co_name,
                    arg1=arg1, arg2=arg2))


    def __init__(self, parent):
        """
        Basic initialization
        """
        self.opts = parent.opts
        self.parent = parent

        # News clippings
        #self.collect_news_clippings = JSONConfig('plugins/annotations').get('cfg_news_clippings_checkbox', False)
        self.collect_news_clippings = plugin_prefs.get('cfg_news_clippings_checkbox', False)
        #self.news_clippings_destination = JSONConfig('plugins/annotations').get('cfg_news_clippings_lineEdit', None)
        self.news_clippings_destination = plugin_prefs.get('cfg_news_clippings_lineEdit', None)
        self.news_clippings_cid = None
        if self.collect_news_clippings and self.news_clippings_destination:
            self.news_clippings_cid = self.get_clippings_cid(self.news_clippings_destination)

    def close(self):
        """
        Perform device-specific shutdown
        """
        pass

    def commit(self):
        self.opts.db.commit()

    def open(self):
        """
        Perform device-specific initialization required for file system access
        """
        pass

    ''' Database operations '''
    def add_to_annotations_db(self, annotations_db, annotation_mi):
        self.opts.db.add_to_annotations_db(annotations_db, annotation_mi)

    def add_to_books_db(self, books_db, book_mi):
        self.opts.db.add_to_books_db(books_db, book_mi)

    def create_annotations_table(self, cached_db):
        self.opts.db.create_annotations_table(cached_db)

    def create_books_table(self, cached_db):
        """
        The <app>_books_<device> table contains a list of books installed on the device.
        book_id is the unique id that the app uses to reference the book in its
        associated annotations table.
        """
        self.opts.db.create_books_table(cached_db)

    @staticmethod
    def generate_annotations_db_name(reader_app, device_name):
        return ReaderApp.ANNOTATIONS_DB_TEMPLATE.format(re.sub('\W', '_', reader_app), re.sub('\W', '_', device_name))

    @staticmethod
    def generate_books_db_name(reader_app, device_name):
        return ReaderApp.BOOKS_DB_TEMPLATE.format(re.sub('\W', '_', reader_app), re.sub('\W', '_', device_name))

    def get_books(self, books_db):
        return self.opts.db.get_books(books_db)

    def get_clippings_cid(self, title):
        '''
        Find or create cid for title
        '''
        cid = None
        try:
            cid = list(self.parent.opts.gui.current_db.data.parse('title:"%s" and tag:Clippings' % title))[0]
        except:
            mi = MetaInformation(title, authors = ['Various'])
            mi.tags = ['Clippings']
            cid = self.parent.opts.gui.current_db.create_book_entry(mi, cover=None,
                add_duplicates=False, force_id=None)
        return cid

    @staticmethod
    def get_exporting_app_classes():
        """
        Utility method to find all subclasses supporting exported annotations
        having a parse_exported_highlights() method
        {app_class_name: app_name}
        """
        exporting_apps = OrderedDict()
        racs = ReaderApp.get_reader_app_classes()
        sorted_racs = sorted(racs, key=unicode.lower)
        for app_name in sorted_racs:
            kls = racs[app_name]
            if getattr(kls, 'SUPPORTS_EXPORTING', False):
                exporting_apps[kls] = app_name
        return exporting_apps

    def get_genres(self, books_db, book_id):
        return self.opts.db.get_genres(books_db, book_id)

    @staticmethod
    def get_reader_app_classes():
        """
        Utility method to find all subclasses of ourselves
        {app_name:cls}
        """
        if ReaderApp.reader_app_classes is None:
            known_reader_app_classes = {}
            for c in ReaderApp._iter_subclasses(ReaderApp):
                # Skip the abstract classes
                if c.app_name == '<placeholder>':
                    continue
                known_reader_app_classes[c.app_name] = c
            ReaderApp.reader_app_classes = known_reader_app_classes
        return ReaderApp.reader_app_classes

    def get_title(self, books_db, book_id):
        return self.opts.db.get_title(books_db, book_id)

    def update_book_last_annotation(self, books_db, timestamp, book_id):
        self.opts.db.update_book_last_annotation(books_db, timestamp, book_id)

    def update_timestamp(self, cached_db):
        self.opts.db.update_timestamp(cached_db)

    ''' Helpers '''
    def _cache_is_current(self, dependent_file, cached_db):
        """
        cached_db: an entry in the timestamps table
        Return True if:
            dependent_file is newer than cached content in db
        Return False if:
            dependent_file is older than cached content in db
            cached_db does not exist
        """
        cached_timestamp = self.opts.db.get('''SELECT timestamp
                                               FROM timestamps
                                               WHERE db="{0}"'''.format(cached_db), all=False)
        current_timestamp = unicode(datetime.fromtimestamp(os.path.getmtime(dependent_file)))

        if False and self.opts.verbose:
            self._log_location(cached_timestamp > current_timestamp)
            if False:
                if os.path.exists(dependent_file):
                    self._log(" current_timestamp: %s" % repr(current_timestamp))
                else:
                    self._log(" '%s' does not exist" % dependent_file)
                self._log("  cached_timestamp: %s" % repr(cached_timestamp))

        return cached_timestamp > current_timestamp

    def _get_epub_toc(self, cid=None, path=None, prepend_title=None):
        '''
        Given a calibre id, return the epub TOC indexed by section
        If cid, use copy in library, else use path to copy on device
        '''
        toc = None
        if cid is not None:
            mi = self.opts.gui.current_db.get_metadata(cid, index_is_id=True)
            toc = None
            if 'EPUB' in mi.formats:
                fpath = self.opts.gui.current_db.format(cid, 'EPUB', index_is_id=True, as_path=True)
            else:
                return toc
        elif path is not None:
            fpath = os.path.join(self.mount_point, path)
        else:
            return toc

        # iBooks stores books unzipped
        # Marvin stores books zipped
        # Need spine, ncx_tree to construct toc

        if os.path.isdir(fpath):
            # Find the OPF in the unzipped ePub
            with open(os.path.join(fpath, 'META-INF', 'container.xml')) as cf:
                container = etree.parse(cf)
                opf_file = container.xpath('.//*[local-name()="rootfile"]')[0].get('full-path')
                oebps = opf_file.rpartition('/')[0]
            with open(os.path.join(fpath, opf_file)) as opf:
                opf_tree = etree.parse(opf)
                spine = opf_tree.xpath('.//*[local-name()="spine"]')[0]
                ncx_fs = spine.get('toc')
                manifest = opf_tree.xpath('.//*[local-name()="manifest"]')[0]
                ncx_file = manifest.find('.//*[@id="%s"]' % ncx_fs).get('href')
            with open(os.path.join(fpath, oebps, ncx_file)) as ncxf:
                ncx_tree = etree.parse(ncxf)
            #self._log(etree.tostring(ncx_tree, pretty_print=True))

        else:
            # Find the OPF file in the zipped ePub
            try:
                with open(fpath, 'rb') as zfo:
                    zf = ZipFile(fpath, 'r')
                    container = etree.fromstring(zf.read('META-INF/container.xml'))
                    opf_tree = etree.fromstring(zf.read(container.xpath('.//*[local-name()="rootfile"]')[0].get('full-path')))

                    spine = opf_tree.xpath('.//*[local-name()="spine"]')[0]
                    ncx_fs = spine.get('toc')
                    manifest = opf_tree.xpath('.//*[local-name()="manifest"]')[0]
                    ncx = manifest.find('.//*[@id="%s"]' % ncx_fs).get('href')

                    # Find the ncx file
                    fnames = zf.namelist()
                    _ncx = [x for x in fnames if ncx in x][0]
                    ncx_tree = etree.fromstring(zf.read(_ncx))
            except:
                import traceback
                self._log_location()
                self._log(" unable to unzip '%s'" % fpath)
                self._log(traceback.format_exc())
                return toc

        # fpath points to epub (zipped or unzipped dir)
        # spine, ncx_tree populated
        try:
            toc = OrderedDict()
            # 1. capture idrefs from spine
            for i, el in enumerate(spine):
                toc[str(i)] = el.get('idref')

            # 2. Resolve <spine> idrefs to <manifest> hrefs
            for el in toc:
                toc[el] = manifest.find('.//*[@id="%s"]' % toc[el]).get('href')

            # 3. Build a dict of src:toc_entry
            src_map = OrderedDict()
            navMap = ncx_tree.xpath('.//*[local-name()="navMap"]')[0]
            for navPoint in navMap:
                # Get the first-level entry
                src = re.sub(r'#.*$', '', navPoint.xpath('.//*[local-name()="content"]')[0].get('src'))
                toc_entry = navPoint.xpath('.//*[local-name()="text"]')[0].text
                src_map[src] = toc_entry

                # Get any nested navPoints
                nested_navPts = navPoint.xpath('.//*[local-name()="navPoint"]')
                for nnp in nested_navPts:
                    src = re.sub(r'#.*$', '', nnp.xpath('.//*[local-name()="content"]')[0].get('src'))
                    toc_entry = nnp.xpath('.//*[local-name()="text"]')[0].text
                    src_map[src] = toc_entry

            # Resolve src paths to toc_entry
            for section in toc:
                if toc[section] in src_map:
                    if prepend_title:
                        toc[section] = "%s &middot; %s" % (prepend_title,  src_map[toc[section]])
                    else:
                        toc[section] = src_map[toc[section]]
                else:
                    toc[section] = None

            # 5. Fill in the gaps
            current_toc_entry = None
            for section in toc:
                if toc[section] is None:
                    toc[section] = current_toc_entry
                else:
                    current_toc_entry = toc[section]
        except:
            import traceback
            self._log_location()
            self._log("{:~^80}".format(" error parsing '%s' " % fpath))
            self._log(traceback.format_exc())
            self._log("{:~^80}".format(" end traceback "))

        return toc

    @staticmethod
    def _iter_subclasses(cls, _seen=None):
        if not isinstance(cls, type):
            raise TypeError('itersubclasses must be called with '
                            'new-style classes, not %.100r' % cls)
        if _seen is None:
            _seen = set()
        try:
            subs = cls.__subclasses__()
        except TypeError:  # fails only when cls is type
            subs = cls.__subclasses__(cls)
        for sub in subs:
            if sub not in _seen:
                _seen.add(sub)
                yield sub
                for sub in ReaderApp._iter_subclasses(sub, _seen):
                    yield sub


class ExportingReader(ReaderApp):
    annotations_subpath = None
    app_folder = None
    app_name = '<placeholder>'
    books_subpath = None
    SUPPORTS_EXPORTING = True
    exporting_reader_classes = None

    def __init__(self, parent):
        ReaderApp.__init__(self, parent)
        self.active_annotations = {}
        self.annotations_db = None
        self.app_name_ = re.sub(' ', '_', self.app_name)
        self.books_db = None
        self.installed_books = []
        self.mount_point = None
        if hasattr(self.opts, 'mount_point'):
            self.mount_point = self.opts.mount_point


class iOSReaderApp(ReaderApp):
    """
    Generic class for iOS reader apps using libiMobileDevice for file access
    """
    # Reader-specific characteristics defined in subclass
    app_folder = None
    app_id = None               # Populated by action:get_annotated_books_in_ios_reader()
    app_aliases = []            # All supported bundle identifiers
    app_name = '<placeholder>'
    books_subpath = None
    HIGHLIGHT_COLORS = []
    metadata_subpath = None
    reader_app_aliases = None
    reader_app_classes = None
    temp_dir = None

    def __init__(self, parent):
        ReaderApp.__init__(self, parent)
        self.active_annotations = {}
        self.annotations_db = None
        self.app_name_ = re.sub(' ', '_', self.app_name)
        self.books_db = None
        self.installed_books = []
        self.ios = None
        if hasattr(parent.opts, 'ios'):
            self.ios = parent.opts.ios
        if getattr(self, 'temp_dir') is None:
            iOSReaderApp._create_temp_dir('_ios_local_db')

    ''' Utilities '''

    @staticmethod
    def get_reader_app_classes():
        """
        Utility method to find all subclasses of ourselves
        {app_name:cls}
        """
        if iOSReaderApp.reader_app_classes is None:
            known_reader_app_classes = {}
            for c in iOSReaderApp._iter_subclasses(iOSReaderApp):
                known_reader_app_classes[c.app_name] = c
            iOSReaderApp.reader_app_classes = known_reader_app_classes
        return iOSReaderApp.reader_app_classes

    @staticmethod
    def get_reader_app_aliases(parent):
        """
        Utility method to return installed app_ids of subclasses.
        The first installed bundle identifier is used.
        {app_name: bundle identifer}
        """
        if iOSReaderApp.reader_app_aliases is None:
            reader_app_aliases = {}
            for c in iOSReaderApp._iter_subclasses(iOSReaderApp):
                for app_id in c.app_aliases:
                    if parent.ios.mount_ios_app(app_id=app_id):
                        reader_app_aliases[c.app_name] = app_id
                        parent.ios.disconnect_idevice()
                        break

            iOSReaderApp.reader_app_aliases = reader_app_aliases
        return iOSReaderApp.reader_app_aliases

    @staticmethod
    def get_sqlite_app_classes(by_name=False):
        '''
        Utility method to find all subclasses supporting fetching annotations from
        sqlite databases managed by app. These subclasses have a get_installed_books()
        method.
        {app_class_name: app_name}
        '''
        sqlite_apps = OrderedDict()
        racs = iOSReaderApp.get_reader_app_classes()
        sorted_racs = sorted(racs, key=unicode.lower)
        for app_name in sorted_racs:
            kls = racs[app_name]
            if getattr(kls, 'SUPPORTS_FETCHING', False):
                sqlite_apps[kls] = app_name
        if by_name:
            sqlite_apps = OrderedDict(zip(list(sqlite_apps.values()), list(sqlite_apps.keys())))
        return sqlite_apps

    ''' Helpers '''
    def _cache_is_current(self, dependent_file_stats, cached_db):
        """
        cached_db: an entry in the timestamps table
        Return True if:
            dependent_file is newer than cached content in db
        Return False if:
            dependent_file is older than cached content in db
            cached_db does not exist
        """
        cached_timestamp = self.opts.db.get('''SELECT timestamp
                                               FROM timestamps
                                               WHERE db="{0}"'''.format(cached_db), all=False)

        unix_timestamp = dependent_file_stats['st_mtime']
        current_timestamp = unicode(datetime.fromtimestamp(unix_timestamp))

        if False:
            self._log_location(cached_timestamp > current_timestamp)
            if True:
                if self.ios.exists(dependent_file):
                    self._log(" current_timestamp: %s" % repr(current_timestamp))
                else:
                    self._log(" '%s' does not exist" % dependent_file)
                self._log("  cached_timestamp: %s" % repr(cached_timestamp))

        return cached_timestamp > current_timestamp

    @staticmethod
    def _create_temp_dir(suffix):
        '''
        Create a PersistentTemporaryDirectory for local copies of remote dbs
        '''
        iOSReaderApp.temp_dir = PersistentTemporaryDirectory(suffix)

    def _get_cached_books(self, cached_db):
        """
        Return a list of installed book_ids for cached_db
        """
        cached_books = []
        columns = self.opts.db.get('''PRAGMA table_info({0})'''.format(cached_db))
        cols = {}
        for column in columns:
            cols[column[1]] = column[0]

        rows = self.opts.db.get('''SELECT book_id FROM {0}'''.format(cached_db))
        for row in rows:
            cached_books.append(row[cols['book_id']])
        return cached_books

    def _get_epub_toc(self, cid=None, path=None, prepend_title=None):
        '''
        Given a calibre id, return the epub TOC indexed by section
        If cid, use copy in library, else use path to copy on device
        '''
        toc = None
#         if cid is not None:
#             mi = self.opts.gui.current_db.get_metadata(cid, index_is_id=True)
#             toc = None
#             if 'EPUB' in mi.formats:
#                 fpath = self.opts.gui.current_db.format(cid, 'EPUB', index_is_id=True, as_path=True)
#             else:
#                 return toc
#         elif path is not None:
#             fpath = path
#         else:
#             return toc
        fpath = path

        # iBooks stores books unzipped
        # Marvin stores books zipped
        # Need spine, ncx_tree to construct toc

        if self.ios.stat(fpath) and self.ios.stat(fpath)['st_ifmt'] == 'S_IFDIR':
            # Find the OPF in the unzipped ePub
            fp = '/'.join([fpath, 'META-INF', 'container.xml'])
            cf = io.BytesIO(self.ios.read(fp))
            container = etree.parse(cf)
            opf_file = container.xpath('.//*[local-name()="rootfile"]')[0].get('full-path')
            oebps = opf_file.rpartition('/')[0]

            fp = '/'.join([fpath, opf_file])
            opf = io.BytesIO(self.ios.read(fp))
            opf_tree = etree.parse(opf)
            spine = opf_tree.xpath('.//*[local-name()="spine"]')[0]
            ncx_fs = spine.get('toc')
            manifest = opf_tree.xpath('.//*[local-name()="manifest"]')[0]
            ncx_file = manifest.find('.//*[@id="%s"]' % ncx_fs).get('href')

            fp = '/'.join([fpath, oebps, ncx_file])
            ncxf = io.BytesIO(self.ios.read(fp))
            ncx_tree = etree.parse(ncxf)
            #self._log(etree.tostring(ncx_tree, pretty_print=True))

        else:
            # Find the OPF file in the zipped ePub
            zfo = io.BytesIO(self.ios.read(fpath, mode='rb'))
            try:
                zf = ZipFile(zfo, 'r')
                container = etree.fromstring(zf.read('META-INF/container.xml'))
                opf_tree = etree.fromstring(zf.read(container.xpath('.//*[local-name()="rootfile"]')[0].get('full-path')))

                spine = opf_tree.xpath('.//*[local-name()="spine"]')[0]
                ncx_fs = spine.get('toc')
                manifest = opf_tree.xpath('.//*[local-name()="manifest"]')[0]
                ncx = manifest.find('.//*[@id="%s"]' % ncx_fs).get('href')

                # Find the ncx file
                fnames = zf.namelist()
                _ncx = [x for x in fnames if ncx in x][0]
                ncx_tree = etree.fromstring(zf.read(_ncx))
            except:
                import traceback
                self._log_location()
                self._log(" unable to unzip '%s'" % fpath)
                self._log(traceback.format_exc())
                return toc

        # fpath points to epub (zipped or unzipped dir)
        # spine, ncx_tree populated
        try:
            toc = OrderedDict()
            # 1. capture idrefs from spine
            for i, el in enumerate(spine):
                toc[str(i)] = el.get('idref')

            # 2. Resolve <spine> idrefs to <manifest> hrefs
            for el in toc:
                toc[el] = manifest.find('.//*[@id="%s"]' % toc[el]).get('href')

            # 3. Build a dict of src:toc_entry
            src_map = OrderedDict()
            navMap = ncx_tree.xpath('.//*[local-name()="navMap"]')[0]
            for navPoint in navMap:
                # Get the first-level entry
                src = re.sub(r'#.*$', '', navPoint.xpath('.//*[local-name()="content"]')[0].get('src'))
                toc_entry = navPoint.xpath('.//*[local-name()="text"]')[0].text
                src_map[src] = toc_entry

                # Get any nested navPoints
                nested_navPts = navPoint.xpath('.//*[local-name()="navPoint"]')
                for nnp in nested_navPts:
                    src = re.sub(r'#.*$', '', nnp.xpath('.//*[local-name()="content"]')[0].get('src'))
                    toc_entry = nnp.xpath('.//*[local-name()="text"]')[0].text
                    src_map[src] = toc_entry

            # Resolve src paths to toc_entry
            for section in toc:
                if toc[section] in src_map:
                    if prepend_title:
                        toc[section] = "%s &middot; %s" % (prepend_title,  src_map[toc[section]])
                    else:
                        toc[section] = src_map[toc[section]]
                else:
                    toc[section] = None

            # 5. Fill in the gaps
            current_toc_entry = None
            for section in toc:
                if toc[section] is None:
                    toc[section] = current_toc_entry
                else:
                    current_toc_entry = toc[section]
        except:
            import traceback
            self._log_location()
            self._log("{:~^80}".format(" error parsing '%s' " % fpath))
            self._log(traceback.format_exc())
            self._log("{:~^80}".format(" end traceback "))

        return toc

    @staticmethod
    def _iter_subclasses(cls, _seen=None):
        if not isinstance(cls, type):
            raise TypeError('itersubclasses must be called with '
                            'new-style classes, not %.100r' % cls)
        if _seen is None:
            _seen = set()
        try:
            subs = cls.__subclasses__()
        except TypeError:  # fails only when cls is type
            subs = cls.__subclasses__(cls)
        for sub in subs:
            if sub not in _seen:
                _seen.add(sub)
                yield sub
                for sub in iOSReaderApp._iter_subclasses(sub, _seen):
                    yield sub

    def _localize_database_path(self, app_id, remote_db_path):
        '''
        Copy remote_db_path from iOS to local storage as needed
        '''
        self._log_location("app_id: '%s' remote_db_path: '%s'" % (app_id, remote_db_path))

        # Mount app_id
        self.ios.mount_ios_app(app_id=app_id)

        local_db_path = None
        db_stats = {}

        if '*' in remote_db_path:
            # Find matching file based on wildcard
            f_els = os.path.basename(remote_db_path).split('*')
            prefix = f_els[0]
            suffix = f_els[1]
            files = self.ios.listdir(os.path.dirname(remote_db_path))
            for f in files:
                if f.startswith(prefix) and f.endswith(suffix):
                    remote_db_path = '/'.join([os.path.dirname(remote_db_path),f])
                    break

        db_stats = self.ios.stat(remote_db_path)
        if db_stats:
            path = remote_db_path.split('/')[-1]
            if iswindows:
                plen = len(self.temp_dir)
                path = ''.join(shorten_components_to(245-plen, [path]))

            full_path = os.path.join(self.temp_dir, path)
            if os.path.exists(full_path):
                lfs = os.stat(full_path)
                if (int(db_stats['st_mtime']) == lfs.st_mtime and
                    int(db_stats['st_size']) == lfs.st_size):
                    local_db_path = full_path

            if not local_db_path:
                with open(full_path, 'wb') as out:
                    self.ios.copy_from_idevice(remote_db_path, out)
                local_db_path = out.name
        else:
            self._log_location("'%s' not found" % remote_db_path)
            raise DatabaseNotFoundException

        # Dismount ios
        self.ios.disconnect_idevice()
        return {'path': local_db_path, 'stats': db_stats}


class USBReader(ReaderApp):
    annotations_subpath = None
    app_folder = None
    app_name = '<placeholder>'
    books_subpath = None
    SUPPORTS_FETCHING = True
    usb_reader_classes = None

    def __init__(self, parent):
        ReaderApp.__init__(self, parent)
        self.active_annotations = {}
        self.annotations_db = None
        self.app_name_ = re.sub(' ', '_', self.app_name)
        self.books_db = None
        self.installed_books = []
        self.mount_point = None
        if hasattr(self.opts, 'mount_point'):
            self.mount_point = self.opts.mount_point

    def get_path_map(self):
        '''
        Models gui2.actions.annotate FetchAnnotationsAction():fetch_annotations()
        Generate a path_map from selected ids

        {id:{'path':'<storage>/author/title.bookmark', 'fmts':['epub']} ...}
        {53: {'path': '/<storage>/Townshend, Pete/Who I Am_ A Memoir - Pete Townshend.bookmark',
              'fmts': [u'epub', u'mobi']}}
        '''

        def get_ids_from_selected_rows():
            rows = self.opts.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) < 2:
                rows = range(self.opts.gui.library_view.model().rowCount(QModelIndex()))
            ids = list(map(self.opts.gui.library_view.model().id, rows))
            return ids

        def get_formats(id):
            formats = db.formats(id, index_is_id=True)
            fmts = []
            if formats:
                for format in formats.split(','):
                    fmts.append(format.lower())
            return fmts

        def get_device_path_from_id(id_):
            paths = []
            for x in ('memory', 'card_a', 'card_b'):
                x = getattr(self.opts.gui, x + '_view').model()
                paths += x.paths_for_db_ids(set([id_]), as_map=True)[id_]
            return paths[0].path if paths else None

        def generate_annotation_paths(ids, db):
            # Generate path templates
            # Individual storage mount points scanned/resolved in driver.get_annotations()
            path_map = {}
            for id in ids:
                path = get_device_path_from_id(id)
                mi = db.get_metadata(id, index_is_id=True)
                a_path = self.device.create_annotations_path(mi, device_path=path)
                path_map[id] = dict(path=a_path, fmts=get_formats(id))
            return path_map

        # Entry point
        db = self.opts.gui.library_view.model().db

        # Get the list of ids in the library
        ids = get_ids_from_selected_rows()
        if not ids:
            return error_dialog(self.opts.gui, _('No books selected'),
                                _('No books selected to fetch annotations from'),
                                show=True)

        # Map ids to paths
        path_map = generate_annotation_paths(ids, db)
        return path_map

    def get_storage(self):
        storage = []
        if self.device._main_prefix:
            storage.append(os.path.join(self.device._main_prefix, self.device.EBOOK_DIR_MAIN))
        if self.device._card_a_prefix:
            storage.append(os.path.join(self.device._card_a_prefix, self.device.EBOOK_DIR_CARD_A))
        if self.device._card_b_prefix:
            storage.append(os.path.join(self.device._card_b_prefix, self.device.EBOOK_DIR_CARD_B))
        return storage

    @staticmethod
    def get_usb_reader_classes():
        """
        Utility method to find all subclasses of ourselves supporting fetching
        {app_name:cls}
        """
        if USBReader.usb_reader_classes is None:
            known_usb_reader_classes = {}
            for c in USBReader._iter_subclasses(USBReader):
                if c.SUPPORTS_FETCHING:
                    known_usb_reader_classes[c.app_name] = c
            USBReader.usb_reader_classes = known_usb_reader_classes
        return USBReader.usb_reader_classes

    @staticmethod
    def _iter_subclasses(cls, _seen=None):
        if not isinstance(cls, type):
            raise TypeError('itersubclasses must be called with '
                            'new-style classes, not %.100r' % cls)
        if _seen is None:
            _seen = set()
        try:
            subs = cls.__subclasses__()
        except TypeError:  # fails only when cls is type
            subs = cls.__subclasses__(cls)
        for sub in subs:
            if sub not in _seen:
                _seen.add(sub)
                yield sub
                for sub in USBReader._iter_subclasses(sub, _seen):
                    yield sub
