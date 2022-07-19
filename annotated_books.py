#!/usr/bin/env python
# coding: utf-8

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import operator
from time import time, localtime, strftime

# calibre Python 3 compatibility.
import six
from six import text_type as unicode

from calibre.devices.usbms.driver import debug_print
try:
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (Qt, QAbstractItemModel, QAbstractTableModel, QBrush,
                          QCheckBox, QColor, QDialogButtonBox, QFont, QFontMetrics,
                          QLabel, QTableView, QTableWidgetItem, QVBoxLayout
                          )
    from PyQt5.Qt import QTextEdit as QWebView # Renaming to keep backwards compatibility.
except ImportError as e:
    debug_print("Error loading QT5: ", e)
    from PyQt4 import QtCore, QtGui
    from PyQt4.Qt import (Qt, QAbstractItemModel, QAbstractTableModel, QBrush,
                          QCheckBox, QColor, QDialogButtonBox, QFont, QFontMetrics,
                          QLabel, QTableView, QTableWidgetItem, QVBoxLayout
                          )
    from PyQt4.QtWebKit import QWebView

# Maintain backwards compatibility with older versions of Qt and calibre.
try:
    qAlignmentFlag_AlignHCenter = Qt.AlignmentFlag.AlignHCenter
    qAlignmentFlag_AlignVCenter = Qt.AlignmentFlag.AlignVCenter
    qCheckState_Checked = Qt.CheckState.Checked
    qCheckState_Unchecked = Qt.CheckState.Unchecked
    qSortOrder_AscendingOrder = Qt.SortOrder.AscendingOrder
    qSortOrder_DescendingOrder = Qt.SortOrder.DescendingOrder
    qItemFlag_ItemIsEnabled = Qt.ItemFlag.ItemIsEnabled
    qItemFlag_ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable
    qStyleHint_TypeWriter = QFont.StyleHint.TypeWriter
except:
    qAlignmentFlag_AlignHCenter = Qt.AlignHCenter
    qAlignmentFlag_AlignVCenter = Qt.AlignVCenter
    qCheckState_Checked = Qt.Checked
    qCheckState_Unchecked = Qt.Unchecked
    qSortOrder_AscendingOrder = Qt.AscendingOrder
    qSortOrder_DescendingOrder = Qt.DescendingOrder
    qItemFlag_ItemIsEnabled = Qt.ItemIsEnabled
    qItemFlag_ItemIsUserCheckable = Qt.ItemIsUserCheckable
    qStyleHint_TypeWriter = QFont.TypeWriter

from calibre.constants import islinux, isosx, iswindows

from calibre_plugins.annotations.common_utils import (
    BookStruct, HelpView, SizePersistedDialog,
    get_clippings_cid, get_icon)

from calibre_plugins.annotations.config import plugin_prefs
from calibre_plugins.annotations.reader_app_support import ReaderApp

from calibre.devices.usbms.driver import debug_print

try:
    debug_print("Annotations::annotated_books.py - loading translations")
    load_translations()
except NameError:
    debug_print("Annotations::annotated_books.py - exception when loading translations")
    pass # load_translations() added in calibre 1.9


class SortableTableWidgetItem(QTableWidgetItem):
    """
    Subclass widget sortable by sort_key
    """
    def __init__(self, text, sort_key):
        super(SortableTableWidgetItem, self).__init__(text)
        self.sort_key = sort_key

    def __lt__(self, other):
        return self.sort_key is not None and other.sort_key is not None and self.sort_key < other.sort_key \
            or (self.sort_key is not None and other.sort_key is None)

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
        elif role == Qt.ItemDataRole.BackgroundRole and self.show_confidence_colors:
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

        elif role == Qt.ItemDataRole.CheckStateRole and col == self.ENABLED_COL:
            if self.arraydata[row][self.ENABLED_COL] == qCheckState_Checked:
                return qCheckState_Checked
            else:
                return qCheckState_Unchecked
        elif role == Qt.ItemDataRole.DisplayRole and col == self.ENABLED_COL:
            return ''
        elif role == Qt.ItemDataRole.DisplayRole and col == self.READER_APP_COL:
            return unicode(self.arraydata[row][self.READER_APP_COL].text())
        elif role == Qt.ItemDataRole.DisplayRole and col == self.TITLE_COL:
            return unicode(self.arraydata[row][self.TITLE_COL].text())
        elif role == Qt.ItemDataRole.DisplayRole and col == self.AUTHOR_COL:
            return unicode(self.arraydata[row][self.AUTHOR_COL].text())
        elif role == Qt.ItemDataRole.DisplayRole and col == self.LAST_ANNOTATION_COL:
            return unicode(self.arraydata[row][self.LAST_ANNOTATION_COL].text())
        elif role == Qt.ItemDataRole.TextAlignmentRole and (col in self.centered_columns):
            return int(qAlignmentFlag_AlignHCenter | qAlignmentFlag_AlignVCenter) # https://bugreports.qt.io/browse/PYSIDE-1974
        elif role != Qt.ItemDataRole.DisplayRole:
            return None
        return self.arraydata[index.row()][index.column()]

    def flags(self, index):
        if index.column() == self.ENABLED_COL:
            return QAbstractItemModel.flags(self, index) | qItemFlag_ItemIsUserCheckable | qItemFlag_ItemIsEnabled
        else:
            return QAbstractItemModel.flags(self, index)

    def refresh(self, show_confidence_colors):
        self.show_confidence_colors = show_confidence_colors
        self.beginResetModel()
        self.endResetModel()
        # self.dataChanged.emit(self.createIndex(0,0),
        #                       self.createIndex(self.rowCount(0), self.columnCount(0)))

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return unicode(self.headerdata[col])
        return None

    def setData(self, index, value, role):
        row, col = index.row(), index.column()
        if col == self.ENABLED_COL:
            if self.arraydata[row][self.ENABLED_COL] == qCheckState_Checked:
                self.arraydata[row][self.ENABLED_COL] = qCheckState_Unchecked
            else:
                self.arraydata[row][self.ENABLED_COL]= qCheckState_Checked

        self.dataChanged.emit(index, index)
        return True

    def sort(self, col, order=qSortOrder_AscendingOrder):
        """
        Sort table by given column number.
        """
        self.layoutAboutToBeChanged.emit()
        if col == self.ENABLED_COL: # Don't sort on the checkbox column.
            self.arraydata = sorted(self.arraydata, key=lambda row: row[col] == qCheckState_Checked, reverse=(order == qSortOrder_DescendingOrder))
        else:
            self.arraydata = sorted(self.arraydata, key=operator.itemgetter(col), reverse=(order == qSortOrder_DescendingOrder))
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
        FONT.setStyleHint(qStyleHint_TypeWriter)

    def __init__(self, parent, book_list, get_annotations_as_HTML, source):
        self.opts = parent.opts
        self.parent = parent
        self.get_annotations_as_HTML = get_annotations_as_HTML
        self.show_confidence_colors = self.opts.prefs.get('annotated_books_dialog_show_confidence_as_bg_color', True)
        self.source = source

        SizePersistedDialog.__init__(self, self.opts.gui, 'Annotations plugin:import annotations dialog')
        self.setWindowTitle(_('Import Annotations'))
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
            debug_print("AnnotatedBooksDialog::__init__ book_data=%s" % (book_data))
            enabled = QCheckBox()
            enabled.setChecked(True)
            enabled = qCheckState_Checked

            # The UUID might not be present. And it is hidden so shouldn't need to be sorted, but...
            book_uuid = SortableTableWidgetItem(
                book_data['uuid'],
                book_data['uuid'])

            # last_annotation sorts by timestamp
            last_annotation_timestamp = time() if book_data['last_update'] is None else book_data['last_update']
#             debug_print("AnnotatedBooksDialog::__init__ title=%s, i=%d, the_timestamp=%s" % (book_data['title'], i, the_timestamp))
            last_annotation = SortableTableWidgetItem(
                strftime(friendly_timestamp_format,
                         localtime(last_annotation_timestamp)),
                last_annotation_timestamp)

            # reader_app sorts case-insensitive
            reader_app = SortableTableWidgetItem(
                book_data['reader_app'],
                book_data['reader_app'].upper())

            # title, author sort by title_sort, author_sort
            if book_data['title_sort'] is None:
                book_data['title_sort'] = book_data['title']
            title = SortableTableWidgetItem(
                book_data['title'],
                book_data['title_sort'].upper())

            if book_data['author_sort'] is None:
                book_data['author_sort'] = book_data['author']
            author = SortableTableWidgetItem(
                book_data['author'],
                book_data['author_sort'].upper())

            genres = book_data['genre'].split(', ')
            if 'News' in genres and collect_news_clippings:
                # cid = get_clippings_cid(self, news_clippings_destination)
                confidence = 5
            else:
                confidence = book_data.get('confidence', None)
                if confidence is None:
                    cid, confidence = parent.generate_confidence(book_data)

            # List order matches self.annotations_header
            this_book = [
                book_uuid,
                book_data['book_id'],
                book_data['genre'],
                enabled,
                reader_app,
                title,
                author,
                last_annotation,
                book_data['annotations'],
                confidence
                ]
            self.tabledata.append(this_book)

        self.tv = QTableView(self)
        self.l.addWidget(self.tv)
        self.annotations_header = ['uuid', 'book_id', 'genre', '', _('Reader App'), _('Title'),
                                   _('Author'), _('Last Annotation'), _('Annotations'), _('Confidence')]
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
        self.tv.hideColumn(self.CONFIDENCE_COL)

        # Set horizontal self.header props
        self.tv.horizontalHeader().setStretchLastSection(True)

        narrow_columns = [_('Last Annotation'), _('Reader App'), _('Annotations')]
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
        for row in range(nrows):
            self.tv.setRowHeight(row, fm.height() + 4)

        sort_column = self.opts.prefs.get('annotated_books_dialog_sort_column',
                                          self.CONFIDENCE_COL)
        sort_order = qSortOrder_AscendingOrder if self.opts.prefs.get('annotated_books_dialog_sort_order', 0) == 0 else qSortOrder_DescendingOrder
        self.tv.sortByColumn(sort_column, sort_order)
        self.tv.setSortingEnabled(True)

        # ~~~~~~~~ Create the ButtonBox ~~~~~~~~
        self.dialogButtonBox = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Help)
        self.dialogButtonBox.setOrientation(Qt.Horizontal)
        self.import_button = self.dialogButtonBox.addButton(self.dialogButtonBox.Ok)
        self.import_button.setText(_('Import Annotations'))

        # Action buttons
        self.toggle_checkmarks_button = self.dialogButtonBox.addButton(_('Clear All'), QDialogButtonBox.ActionRole)
        self.toggle_checkmarks_button.setObjectName('toggle_checkmarks_button')

        scb_text = _('Show match status')
        if self.show_confidence_colors:
            scb_text = _("Hide match status")
        self.show_confidence_button = self.dialogButtonBox.addButton(scb_text, QDialogButtonBox.ActionRole)
        self.show_confidence_button.setObjectName('confidence_button')
        if self.show_confidence_colors:
            self.show_confidence_button.setIcon(get_icon('images/matches_hide.png'))
        else:
            self.show_confidence_button.setIcon(get_icon('images/matches_show.png'))

        self.preview_button = self.dialogButtonBox.addButton(_('Preview'), QDialogButtonBox.ActionRole)
        self.preview_button.setObjectName('preview_button')

        self.dialogButtonBox.clicked.connect(self.show_annotated_books_dialog_clicked)
        self.l.addWidget(self.dialogButtonBox)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()

    def capture_sort_column(self, sort_column):
        sort_order = 0 if self.tv.horizontalHeader().sortIndicatorOrder() == qSortOrder_AscendingOrder else 1
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
            enabled = self.tm.arraydata[i][self.ENABLED_COL] == qCheckState_Checked
            if not enabled:
                continue

            reader_app = str(self.tm.arraydata[i][self.READER_APP_COL].text())
            if not reader_app in self.selected_books:
                self.selected_books[reader_app] = []

            author = str(self.tm.arraydata[i][self.AUTHOR_COL].text())
            book_id = self.tm.arraydata[i][self.annotations_header.index('book_id')]
            genre = self.tm.arraydata[i][self.annotations_header.index('genre')]
            title = str(self.tm.arraydata[i][self.TITLE_COL].text())
            uuid = str(self.tm.arraydata[i][self.annotations_header.index('uuid')].text())
            confidence = self.tm.arraydata[i][self.CONFIDENCE_COL]

            book_mi = BookStruct()
            book_mi.author = author
            book_mi.book_id = book_id
            book_mi.genre = genre
            book_mi.reader_app = reader_app
            book_mi.title = title
            book_mi.uuid = uuid
            book_mi.confidence = confidence
            self.selected_books[reader_app].append(book_mi)

    def getTableRowDoubleClick(self, index):
        self.preview_annotations()

    def preview_annotations(self):
        """
        The listed annotations are in annotations.db.
        AnnotationsDB:annotations_to_HTML() needs title, book_id, reader_app
        """
        i = self.tvSelectionModel.currentIndex().row()
        reader_app = str(self.tm.arraydata[i][self.READER_APP_COL].text())
        title = str(self.tm.arraydata[i][self.TITLE_COL].text())

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
        help_html = get_resources('help/import_annotations.html')
        help_html = help_html.decode('utf-8')

        hv = HelpView(self, self.opts.icon, self.opts.prefs,
                      html=help_html, title=_("Import Annotations"))
        hv.show()

    def size_hint(self):
        return QtCore.QSize(self.perfect_width, self.height())

    def start_confidence_scan(self):
        self.annotated_books_scanner.start()

    def toggle_checkmarks(self):
        button_text = str(self.toggle_checkmarks_button.text())
        debug_print("toggle_checkmarks - %s" % button_text)
        if button_text == _('Clear All'):
            debug_print("toggle_checkmarks - Clear All")
            for i in range(len(self.tabledata)):
                debug_print("toggle_checkmarks - Clear All - row - %d" % i)
                self.tm.arraydata[i][self.ENABLED_COL]= qCheckState_Unchecked
            self.toggle_checkmarks_button.setText(_('Set All'))
        else:
            debug_print("toggle_checkmarks - Set all")
            for i in range(len(self.tabledata)):
                debug_print("toggle_checkmarks - Set All - row - %d" % i)
                self.tm.arraydata[i][self.ENABLED_COL] = qCheckState_Checked
            self.toggle_checkmarks_button.setText(_('Clear All'))
        self.tm.refresh(self.show_confidence_colors)


    def toggle_confidence_colors(self):
        self.show_confidence_colors = not self.show_confidence_colors
        self.opts.prefs.set('annotated_books_dialog_show_confidence_as_bg_color', self.show_confidence_colors)
        if self.show_confidence_colors:
            self.show_confidence_button.setText(_("Hide match status"))
            self.show_confidence_button.setIcon(get_icon('images/matches_hide.png'))
            self.tv.sortByColumn(self.CONFIDENCE_COL, qSortOrder_DescendingOrder)
            self.capture_sort_column(self.CONFIDENCE_COL)
        else:
            self.show_confidence_button.setText(_("Show match status"))
            self.show_confidence_button.setIcon(get_icon('images/matches_show.png'))
        self.tv.setAlternatingRowColors(not self.show_confidence_colors)
        self.tm.refresh(self.show_confidence_colors)


class PreviewDialog(SizePersistedDialog):
    """
    Render a read-only preview of formatted annotations
    """
    def __init__(self, book_mi, annotations, parent=None):
        self.prefs = plugin_prefs
        super(PreviewDialog, self).__init__(parent, 'annotations_preview_dialog')
        self.pl = QVBoxLayout(self)
        self.setLayout(self.pl)

        self.label = QLabel()
        self.label.setText("<b>" + _("{0} annotations &middot; {1}").format(book_mi.reader_app, book_mi.title) + "</b>")
        self.label.setAlignment(qAlignmentFlag_AlignHCenter)
        self.pl.addWidget(self.label)

        self.wv = QWebView()
        self.wv.setHtml(annotations)
        self.pl.addWidget(self.wv)

        self.buttonbox = QDialogButtonBox(QDialogButtonBox.Close)
#        self.buttonbox.addButton('Close', QDialogButtonBox.AcceptRole)
        self.buttonbox.setOrientation(Qt.Horizontal)
#        self.buttonbox.accepted.connect(self.close)
        self.buttonbox.rejected.connect(self.close)
        self.pl.addWidget(self.buttonbox)

        # Sizing
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.resize_dialog()
