#!/usr/bin/env python
# coding: utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

import operator
from time import localtime, strftime

from calibre.devices.usbms.driver import debug_print
try:
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (Qt, QAbstractItemModel, QAbstractTableModel, QBrush,
                          QCheckBox, QColor, QDialog, QDialogButtonBox, QFont, QFontMetrics,
                          QLabel, QVariant,
                          QTableView, QTableWidgetItem,
                          QVBoxLayout,
                          pyqtSignal)
    from PyQt5.QtWebKitWidgets import QWebView
except ImportError as e:
    debug_print("Error loading QT5: ", e)
    from PyQt4 import QtCore, QtGui
    from PyQt4.Qt import (Qt, QAbstractItemModel, QAbstractTableModel, QBrush,
                          QCheckBox, QColor, QDialog, QDialogButtonBox, QFont, QFontMetrics,
                          QLabel, QVariant,
                          QTableView, QTableWidgetItem,
                          QVBoxLayout,
                          pyqtSignal)
    from PyQt4.QtWebKit import QWebView

from calibre.constants import islinux, isosx, iswindows

from calibre_plugins.annotations.common_utils import (
    BookStruct, HelpView, SizePersistedDialog,
    get_clippings_cid, get_icon)

from calibre_plugins.annotations.config import plugin_prefs
from calibre_plugins.annotations.reader_app_support import ReaderApp


class SortableTableWidgetItem(QTableWidgetItem):
    """
    Subclass widget sortable by sort_key
    """
    def __init__(self, text, sort_key):
        super(SortableTableWidgetItem, self).__init__(text)
        self.sort_key = sort_key

    def __lt__(self, other):
        return self.sort_key < other.sort_key


class MarkupTableModel(QAbstractTableModel):
    #http://www.saltycrane.com/blog/2007/12/pyqt-43-qtableview-qabstracttablemodel/

    def __init__(self, parent=None, columns_to_center=[], *args):
        """
        datain: a list of lists
        headerdata: a list of strings
        """
        QAbstractTableModel.__init__(self, parent, *args)
        self.arraydata = parent.tabledata
        self.centered_columns = columns_to_center
        self.headerdata = parent.annotations_header
        self.show_confidence_colors = parent.show_confidence_colors

        self.AUTHOR_COL = parent.AUTHOR_COL
        self.CONFIDENCE_COL = parent.CONFIDENCE_COL
        self.ENABLED_COL = parent.ENABLED_COL
        self.LAST_ANNOTATION_COL = parent.LAST_ANNOTATION_COL
        self.READER_APP_COL = parent.READER_APP_COL
        self.TITLE_COL = parent.TITLE_COL

    def rowCount(self, parent):
        return len(self.arraydata)

    def columnCount(self, parent):
        return len(self.headerdata)

    def data(self, index, role):
        row, col = index.row(), index.column()
        if not index.isValid():
            return ''
        elif role == Qt.BackgroundRole and self.show_confidence_colors:
            confidence = self.arraydata[row][self.CONFIDENCE_COL]
            saturation = 0.40
            value = 1.0
            red_hue = 0.0
            green_hue = 0.333
            yellow_hue = 0.1665
            if confidence >= 3:
                return QBrush(QColor.fromHsvF(green_hue, saturation, value))
            elif confidence:
                return QBrush(QColor.fromHsvF(yellow_hue, saturation, value))
            else:
                return QBrush(QColor.fromHsvF(red_hue, saturation, value))

        elif role == Qt.CheckStateRole and col == self.ENABLED_COL:
            if self.arraydata[row][self.ENABLED_COL].checkState():
                return Qt.Checked
            else:
                return Qt.Unchecked
        elif role == Qt.DisplayRole and col == self.READER_APP_COL:
            return unicode(self.arraydata[row][self.READER_APP_COL].text())
        elif role == Qt.DisplayRole and col == self.TITLE_COL:
            return unicode(self.arraydata[row][self.TITLE_COL].text())
        elif role == Qt.DisplayRole and col == self.AUTHOR_COL:
            return unicode(self.arraydata[row][self.AUTHOR_COL].text())
        elif role == Qt.DisplayRole and col == self.LAST_ANNOTATION_COL:
            return unicode(self.arraydata[row][self.LAST_ANNOTATION_COL].text())
        elif role == Qt.TextAlignmentRole and (col in self.centered_columns):
            return Qt.AlignHCenter
        elif role != Qt.DisplayRole:
            return None
        return self.arraydata[index.row()][index.column()]

    def flags(self, index):
        if index.column() == self.ENABLED_COL:
            return QAbstractItemModel.flags(self, index) | Qt.ItemIsUserCheckable
        else:
            return QAbstractItemModel.flags(self, index)

    def refresh(self, show_confidence_colors):
        self.show_confidence_colors = show_confidence_colors
        self.dataChanged.emit(self.createIndex(0,0),
                              self.createIndex(self.rowCount(0), self.columnCount(0)))

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return unicode(self.headerdata[col])
        return None

    def setData(self, index, value, role):
        row, col = index.row(), index.column()
        if col == self.ENABLED_COL:
            if self.arraydata[row][self.ENABLED_COL].checkState():
                self.arraydata[row][self.ENABLED_COL].setCheckState(False)
            else:
                self.arraydata[row][self.ENABLED_COL].setCheckState(True)

#        self.emit(pyqtSignal("dataChanged(QModelIndex,QModelIndex)"), index, index)
        self.dataChanged.emit(index, index)
        return True

    def sort(self, Ncol, order):
        """
        Sort table by given column number.
        """
        self.layoutAboutToBeChanged.emit()
        self.arraydata = sorted(self.arraydata, key=operator.itemgetter(Ncol))
        if order == Qt.DescendingOrder:
            self.arraydata.reverse()
        self.layoutChanged.emit()


class AnnotatedBooksDialog(SizePersistedDialog):
    '''
    This dialog is shown when the user fetches or imports books
    self.fetch_single_annotations controls checkmark display, behavior of fetch button
    '''
    if isosx:
        FONT = QFont('Monaco', 11)
    elif iswindows:
        FONT = QFont('Lucida Console', 9)
    elif islinux:
        FONT = QFont('Monospace', 9)
        FONT.setStyleHint(QFont.TypeWriter)

    def __init__(self, parent, book_list, get_annotations_as_HTML, source):
        self.opts = parent.opts
        self.parent = parent
        self.get_annotations_as_HTML = get_annotations_as_HTML
        self.show_confidence_colors = self.opts.prefs.get('annotated_books_dialog_show_confidence_as_bg_color', True)
        self.source = source

#         QDialog.__init__(self, parent=self.opts.gui)
        SizePersistedDialog.__init__(self, self.opts.gui, 'Annotations plugin:import annotations dialog')
        self.setWindowTitle(u'Import Annotations')
        self.setWindowIcon(self.opts.icon)
        self.l = QVBoxLayout(self)
        self.setLayout(self.l)
        self.perfect_width = 0

        from calibre_plugins.annotations.appearance import default_timestamp
        friendly_timestamp_format = plugin_prefs.get('appearance_timestamp_format', default_timestamp)

        # Are we collecting News clippings?
        collect_news_clippings = self.opts.prefs.get('cfg_news_clippings_checkbox', False)
        news_clippings_destination = self.opts.prefs.get('cfg_news_clippings_lineEdit', None)

        # Populate the table data
        self.tabledata = []
        for book_data in book_list:
            enabled = QCheckBox()
            enabled.setChecked(True)

            # last_annotation sorts by timestamp
            last_annotation = SortableTableWidgetItem(
                strftime(friendly_timestamp_format,
                         localtime(book_data['last_update'])),
                book_data['last_update'])

            # reader_app sorts case-insensitive
            reader_app = SortableTableWidgetItem(
                book_data['reader_app'],
                book_data['reader_app'].upper())

            # title, author sort by title_sort, author_sort
            if not book_data['title_sort']:
                book_data['title_sort'] = book_data['title']
            title = SortableTableWidgetItem(
                book_data['title'],
                book_data['title_sort'].upper())

            if not book_data['author_sort']:
                book_data['author_sort'] = book_data['author']
            author = SortableTableWidgetItem(
                book_data['author'],
                book_data['author_sort'].upper())

            genres = book_data['genre'].split(', ')
            if 'News' in genres and collect_news_clippings:
                cid = get_clippings_cid(self, news_clippings_destination)
                confidence = 5
            else:
                cid, confidence = parent.generate_confidence(book_data)

            # List order matches self.annotations_header
            this_book = [
                book_data['uuid'],
                book_data['book_id'],
                book_data['genre'],
                enabled,
                reader_app,
                title,
                author,
                last_annotation,
                book_data['annotations'],
                confidence]
            self.tabledata.append(this_book)

        self.tv = QTableView(self)
        self.l.addWidget(self.tv)
        self.annotations_header = ['uuid', 'book_id', 'genre', '', 'Reader App', 'Title',
                                   'Author', 'Last Annotation', 'Annotations', 'Confidence']
        self.ENABLED_COL = 3
        self.READER_APP_COL = 4
        self.TITLE_COL = 5
        self.AUTHOR_COL = 6
        self.LAST_ANNOTATION_COL = 7
        self.CONFIDENCE_COL = 9
        columns_to_center = [8]
        self.tm = MarkupTableModel(self, columns_to_center=columns_to_center)
        self.tv.setModel(self.tm)
        self.tv.setShowGrid(False)
        self.tv.setFont(self.FONT)
        self.tvSelectionModel = self.tv.selectionModel()
        self.tv.setAlternatingRowColors(not self.show_confidence_colors)
        self.tv.setShowGrid(False)
        self.tv.setWordWrap(False)
        self.tv.setSelectionBehavior(self.tv.SelectRows)

        # Connect signals
        self.tv.doubleClicked.connect(self.getTableRowDoubleClick)
        self.tv.horizontalHeader().sectionClicked.connect(self.capture_sort_column)

        # Hide the vertical self.header
        self.tv.verticalHeader().setVisible(False)

        # Hide uuid, book_id, genre, confidence
        self.tv.hideColumn(self.annotations_header.index('uuid'))
        self.tv.hideColumn(self.annotations_header.index('book_id'))
        self.tv.hideColumn(self.annotations_header.index('genre'))
        self.tv.hideColumn(self.annotations_header.index('Confidence'))

        # Set horizontal self.header props
        self.tv.horizontalHeader().setStretchLastSection(True)

        narrow_columns = ['Last Annotation', 'Reader App', 'Annotations']
        extra_width = 10
        breathing_space = 20

        # Set column width to fit contents
        self.tv.resizeColumnsToContents()
        perfect_width = 10 + (len(narrow_columns) * extra_width)
        for i in range(3, 8):
            perfect_width += self.tv.columnWidth(i) + breathing_space
        self.tv.setMinimumSize(perfect_width, 100)
        self.perfect_width = perfect_width

        # Add some width to narrow columns
        for nc in narrow_columns:
            cw = self.tv.columnWidth(self.annotations_header.index(nc))
            self.tv.setColumnWidth(self.annotations_header.index(nc), cw + extra_width)

        # Set row height
        fm = QFontMetrics(self.FONT)
        nrows = len(self.tabledata)
        for row in xrange(nrows):
            self.tv.setRowHeight(row, fm.height() + 4)

        self.tv.setSortingEnabled(True)
        sort_column = self.opts.prefs.get('annotated_books_dialog_sort_column',
                                          self.annotations_header.index('Confidence'))
        sort_order = self.opts.prefs.get('annotated_books_dialog_sort_order',
                                         Qt.DescendingOrder)
        self.tv.sortByColumn(sort_column, sort_order)

        # ~~~~~~~~ Create the ButtonBox ~~~~~~~~
        self.dialogButtonBox = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Help)
        self.dialogButtonBox.setOrientation(Qt.Horizontal)
        self.import_button = self.dialogButtonBox.addButton(self.dialogButtonBox.Ok)
        self.import_button.setText('Import Annotations')

        # Action buttons
        self.toggle_checkmarks_button = self.dialogButtonBox.addButton('Clear All', QDialogButtonBox.ActionRole)
        self.toggle_checkmarks_button.setObjectName('toggle_checkmarks_button')

        scb_text = 'Show match status'
        if self.show_confidence_colors:
            scb_text = "Hide match status"
        self.show_confidence_button = self.dialogButtonBox.addButton(scb_text, QDialogButtonBox.ActionRole)
        self.show_confidence_button.setObjectName('confidence_button')
        if self.show_confidence_colors:
            self.show_confidence_button.setIcon(get_icon('images/matches_hide.png'))
        else:
            self.show_confidence_button.setIcon(get_icon('images/matches_show.png'))

        self.preview_button = self.dialogButtonBox.addButton('Preview', QDialogButtonBox.ActionRole)
        self.preview_button.setObjectName('preview_button')

        self.dialogButtonBox.clicked.connect(self.show_annotated_books_dialog_clicked)
        self.l.addWidget(self.dialogButtonBox)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def capture_sort_column(self, sort_column):
        sort_order = self.tv.horizontalHeader().sortIndicatorOrder()
        self.opts.prefs.set('annotated_books_dialog_sort_column', sort_column)
        self.opts.prefs.set('annotated_books_dialog_sort_order', sort_order)

    def fetch_selected_annotations(self):
        '''
        Invoked by 'Import annotations' button in show_annotated_books_dialog()
        Populate a list of books by Reader App:
        { 'iBooks': [{'title':, 'author':, 'uuid'}, ...],
          'Marvin': [{'title':, 'author':, 'uuid'}, ...] }
        '''
        self.selected_books = {}

        for i in range(len(self.tabledata)):
            self.tv.selectRow(i)
            enabled = bool(self.tm.arraydata[i][self.ENABLED_COL].checkState())
            if not enabled:
                continue

            reader_app = str(self.tm.arraydata[i][self.annotations_header.index('Reader App')].text())
            if not reader_app in self.selected_books:
                self.selected_books[reader_app] = []

            author = str(self.tm.arraydata[i][self.annotations_header.index('Author')].text())
            book_id = self.tm.arraydata[i][self.annotations_header.index('book_id')]
            genre = self.tm.arraydata[i][self.annotations_header.index('genre')]
            title = str(self.tm.arraydata[i][self.annotations_header.index('Title')].text())
            uuid = self.tm.arraydata[i][self.annotations_header.index('uuid')]

            book_mi = BookStruct()
            book_mi.author = author
            book_mi.book_id = book_id
            book_mi.genre = genre
            book_mi.reader_app = reader_app
            book_mi.title = title
            book_mi.uuid = uuid
            self.selected_books[reader_app].append(book_mi)

    def getTableRowDoubleClick(self, index):
        self.preview_annotations()

    def preview_annotations(self):
        """
        The listed annotations are in annotations.db.
        AnnotationsDB:annotations_to_HTML() needs title, book_id, reader_app
        """
        i = self.tvSelectionModel.currentIndex().row()
        reader_app = str(self.tm.arraydata[i][self.annotations_header.index('Reader App')].text())
        title = str(self.tm.arraydata[i][self.annotations_header.index('Title')].text())

        book_mi = BookStruct()
        book_mi.book_id = self.tm.arraydata[i][self.annotations_header.index('book_id')]
        book_mi.reader_app = reader_app
        book_mi.title = title

        # Render annotations from db
        annotations_db = ReaderApp.generate_annotations_db_name(reader_app, self.source)
        annotations = self.get_annotations_as_HTML(annotations_db, book_mi)

        PreviewDialog(book_mi, annotations, parent=self.opts.gui).exec_()

    def show_annotated_books_dialog_clicked(self, button):
        '''
        BUTTON_ROLES = ['AcceptRole', 'RejectRole', 'DestructiveRole', 'ActionRole',
                        'HelpRole', 'YesRole', 'NoRole', 'ApplyRole', 'ResetRole']
        '''
        if self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.AcceptRole:
            self.fetch_selected_annotations()
            self.accept()
        elif self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.ActionRole:
            if button.objectName() == 'confidence_button':
                self.toggle_confidence_colors()
            elif button.objectName() == 'preview_button':
                self.preview_annotations()
            elif button.objectName() == 'toggle_checkmarks_button':
                self.toggle_checkmarks()
        elif self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.HelpRole:
            self.show_help()
        elif self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.RejectRole:
            self.close()

    def show_help(self):
        '''
        Display help file
        '''
        hv = HelpView(self, self.opts.icon, self.opts.prefs,
                      html=get_resources('help/import_annotations.html'), title="Import Annotations")
        hv.show()

    def size_hint(self):
        return QtCore.QSize(self.perfect_width, self.height())

    def start_confidence_scan(self):
        self.annotated_books_scanner.start()

    def toggle_checkmarks(self):
        button_text = str(self.toggle_checkmarks_button.text())
        if button_text == 'Clear All':
            for i in range(len(self.tabledata)):
                self.tm.arraydata[i][self.ENABLED_COL].setCheckState(False)
            self.toggle_checkmarks_button.setText(' Set All ')
        else:
            for i in range(len(self.tabledata)):
                self.tm.arraydata[i][self.ENABLED_COL].setCheckState(True)
            self.toggle_checkmarks_button.setText('Clear All')
        self.tm.refresh(self.show_confidence_colors)

    def toggle_confidence_colors(self):
        self.show_confidence_colors = not self.show_confidence_colors
        self.opts.prefs.set('annotated_books_dialog_show_confidence_as_bg_color', self.show_confidence_colors)
        if self.show_confidence_colors:
            self.show_confidence_button.setText("Hide match status")
            self.show_confidence_button.setIcon(get_icon('images/matches_hide.png'))
            self.tv.sortByColumn(self.annotations_header.index('Confidence'), Qt.DescendingOrder)
            self.capture_sort_column(self.annotations_header.index('Confidence'))
        else:
            self.show_confidence_button.setText("Show match status")
            self.show_confidence_button.setIcon(get_icon('images/matches_show.png'))
        self.tv.setAlternatingRowColors(not self.show_confidence_colors)
        self.tm.refresh(self.show_confidence_colors)


class PreviewDialog(SizePersistedDialog):
    """
    Render a read-only preview of formatted annotations
    """
    def __init__(self, book_mi, annotations, parent=None):
        #QDialog.__init__(self, parent)
        self.prefs = plugin_prefs
        super(PreviewDialog, self).__init__(parent, 'annotations_preview_dialog')
        self.pl = QVBoxLayout(self)
        self.setLayout(self.pl)

        self.label = QLabel()
        self.label.setText("<b>%s annotations &middot; %s</b>" % (book_mi.reader_app, book_mi.title))
        self.label.setAlignment(Qt.AlignHCenter)
        self.pl.addWidget(self.label)

        self.wv = QWebView()
        self.wv.setHtml(annotations)
        self.pl.addWidget(self.wv)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Close)
#        self.buttonbox.addButton('Close', QDialogButtonBox.AcceptRole)
        self.buttonbox.setOrientation(Qt.Horizontal)
#        self.buttonbox.accepted.connect(self.close)
        self.buttonbox.rejected.connect(self.close)
#        self.connect(self.buttonbox, pyqtSignal('accepted()'), self.close)
#        self.connect(self.buttonbox, pyqtSignal('rejected()'), self.close)
        self.pl.addWidget(self.buttonbox)

        # Sizing
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.resize_dialog()
