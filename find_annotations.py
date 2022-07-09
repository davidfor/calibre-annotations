#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import re

from datetime import datetime, time
from dateutil.tz import tzlocal, tzutc
from functools import partial
from time import mktime

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.gui2.metadata.basic_widgets import DateEdit

try:
    from PyQt5 import QtWidgets as QtGui
    from PyQt5 import QtCore
    from PyQt5.Qt import (Qt, QComboBox, QDateTime, QDialogButtonBox,
        QEvent, QFrame, QGridLayout, QGroupBox, QIcon, QLabel, QLineEdit, QPushButton,
        QRect, QTimer,
        QToolButton, QVBoxLayout, QSpacerItem,
        pyqtSignal)
    from PyQt5.QtWidgets import QSizePolicy
except ImportError as e:
    from PyQt4 import QtCore, QtGui
    from PyQt4.Qt import (Qt, QComboBox, QDateTime, QDialogButtonBox,
        QEvent, QFrame, QGridLayout, QGroupBox, QIcon, QLabel, QLineEdit, QPushButton,
        QRect, QTimer,
        QToolButton, QVBoxLayout, QSpacerItem,
        pyqtSignal)
    from PyQt4.QtGui import QSizePolicy

# Maintain backwards compatibility with older versions of Qt and calibre.
try:
    qSizePolicy_Expanding = QSizePolicy.Policy.Expanding
    qSizePolicy_Maximum   = QSizePolicy.Policy.Maximum
    qSizePolicy_Minimum   = QSizePolicy.Policy.Minimum
    qSizePolicy_Preferred = QSizePolicy.Policy.Preferred
except:
    qSizePolicy_Expanding = QSizePolicy.Expanding
    qSizePolicy_Maximum   = QSizePolicy.Maximum
    qSizePolicy_Minimum   = QSizePolicy.Minimum
    qSizePolicy_Preferred = QSizePolicy.Preferred

from calibre_plugins.annotations.annotations import COLOR_MAP
from calibre_plugins.annotations.common_utils import (Logger, SizePersistedDialog,
    get_cc_mapping)
from calibre_plugins.annotations.config import InventoryAnnotatedBooks, plugin_prefs

from calibre_plugins.annotations.reader_app_support import ReaderApp

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

utc_tz = tzutc()
EPOCH = datetime(1969,12,31, tzinfo=tzlocal())

class MyDateEdit(DateEdit):
    TOOLTIP = ''
    LABEL = '&Date:'
    FMT = 'dd MMM yyyy hh:mm:ss'
    ATTR = 'timestamp'
    TWEAK = 'gui_timestamp_display_format'

    def __init__(self, parent, default_date):
        DateEdit.__init__(self, parent)
        self.default_date = default_date
        self.setMinimumDateTime(QDateTime(EPOCH))
        self.setMaximumDateTime(QDateTime(datetime.today()))

    def reset_from_date(self, *args):
        self.current_val = self.minimumDateTime().addSecs(1)

    def reset_to_date(self, *args):
        self.current_val = self.maximumDateTime()


class MyLineEdit(QLineEdit):
    '''
    Capture enter/return events so dialog doesn't close
    '''
    return_pressed = pyqtSignal(object)
    def __init__(self, *args):
        QLineEdit.__init__(self, *args)

    def event(self, event):
        if (event.type() == QEvent.KeyPress) and (event.key() == Qt.Key_Return):
            self.return_pressed.emit("return_pressed")
            return True
        return QLineEdit.event(self, event)


class FindAnnotationsDialog(SizePersistedDialog, Logger):

    GENERIC_STYLE = 'Any style'
    GENERIC_READER = 'Any reader'

    def __init__(self, opts):
        self.matched_ids = set()
        self.opts = opts
        self.prefs = opts.prefs
        super(FindAnnotationsDialog, self).__init__(self.opts.gui, 'find_annotations_dialog')
        self.setWindowTitle(_('Find Annotations'))
        self.setWindowIcon(self.opts.icon)
        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        self.search_criteria_gb = QGroupBox(self)
        self.search_criteria_gb.setTitle(_("Search criteria"))
        self.scgl = QGridLayout(self.search_criteria_gb)
        self.l.addWidget(self.search_criteria_gb)
        # addWidget(widget, row, col, rowspan, colspan)

        row = 0
        # ~~~~~~~~ Create the Readers comboBox ~~~~~~~~
        self.reader_label = QLabel(_('Reader'))
        self.reader_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.scgl.addWidget(self.reader_label, row, 0, 1, 1)

        self.find_annotations_reader_comboBox = QComboBox()
        self.find_annotations_reader_comboBox.setObjectName('find_annotations_reader_comboBox')
        self.find_annotations_reader_comboBox.setToolTip(_('Reader annotations to search for'))

        self.find_annotations_reader_comboBox.addItem(self.GENERIC_READER)
        racs = ReaderApp.get_reader_app_classes()
        for ra in sorted(list(racs.keys())):
            self.find_annotations_reader_comboBox.addItem(ra)
        self.scgl.addWidget(self.find_annotations_reader_comboBox, row, 1, 1, 4)
        row += 1

        # ~~~~~~~~ Create the Styles comboBox ~~~~~~~~
        self.style_label = QLabel(_('Style'))
        self.style_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.scgl.addWidget(self.style_label, row, 0, 1, 1)

        self.find_annotations_color_comboBox = QComboBox()
        self.find_annotations_color_comboBox.setObjectName('find_annotations_color_comboBox')
        self.find_annotations_color_comboBox.setToolTip(_('Annotation style to search for'))

        self.find_annotations_color_comboBox.addItem(self.GENERIC_STYLE)
        all_colors = list(COLOR_MAP.keys())
        for color in sorted(all_colors):
            self.find_annotations_color_comboBox.addItem(color)
        self.scgl.addWidget(self.find_annotations_color_comboBox, row, 1, 1, 4)
        row += 1

        # ~~~~~~~~ Create the Text LineEdit control ~~~~~~~~
        self.text_label = QLabel(_('Text'))
        self.text_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.scgl.addWidget(self.text_label, row, 0, 1, 1)
        self.find_annotations_text_lineEdit = MyLineEdit()
        self.find_annotations_text_lineEdit.setObjectName('find_annotations_text_lineEdit')
        self.scgl.addWidget(self.find_annotations_text_lineEdit, row, 1, 1, 3)
        self.reset_text_tb = QToolButton()
        self.reset_text_tb.setObjectName('reset_text_tb')
        self.reset_text_tb.setToolTip(_('Clear search criteria'))
        self.reset_text_tb.setIcon(QIcon(I('trash.png')))
        self.reset_text_tb.clicked.connect(self.clear_text_field)
        self.scgl.addWidget(self.reset_text_tb, row, 4, 1, 1)
        row += 1

        # ~~~~~~~~ Create the Note LineEdit control ~~~~~~~~
        self.note_label = QLabel(_('Note'))
        self.note_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.scgl.addWidget(self.note_label, row, 0, 1, 1)
        self.find_annotations_note_lineEdit = MyLineEdit()
        self.find_annotations_note_lineEdit.setObjectName('find_annotations_note_lineEdit')
        self.scgl.addWidget(self.find_annotations_note_lineEdit, row, 1, 1, 3)
        self.reset_note_tb = QToolButton()
        self.reset_note_tb.setObjectName('reset_note_tb')
        self.reset_note_tb.setToolTip(_('Clear search criteria'))
        self.reset_note_tb.setIcon(QIcon(I('trash.png')))
        self.reset_note_tb.clicked.connect(self.clear_note_field)
        self.scgl.addWidget(self.reset_note_tb, row, 4, 1, 1)
        row += 1

        # ~~~~~~~~ Create the Date range controls ~~~~~~~~
        self.date_range_label = QLabel(_('Date range'))
        self.date_range_label.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.scgl.addWidget(self.date_range_label, row, 0, 1, 1)

        # Date 'From'
        self.find_annotations_date_from_dateEdit = MyDateEdit(self, datetime(1970,1,1))
        self.find_annotations_date_from_dateEdit.setObjectName('find_annotations_date_from_dateEdit')
        #self.find_annotations_date_from_dateEdit.current_val = datetime(1970,1,1)
        self.find_annotations_date_from_dateEdit.clear_button.clicked.connect(self.find_annotations_date_from_dateEdit.reset_from_date)
        self.scgl.addWidget(self.find_annotations_date_from_dateEdit, row, 1, 1, 1)
        self.scgl.addWidget(self.find_annotations_date_from_dateEdit.clear_button, row, 2, 1, 1)

        # Date 'To'
        self.find_annotations_date_to_dateEdit = MyDateEdit(self, datetime.today())
        self.find_annotations_date_to_dateEdit.setObjectName('find_annotations_date_to_dateEdit')
        #self.find_annotations_date_to_dateEdit.current_val = datetime.today()
        self.find_annotations_date_to_dateEdit.clear_button.clicked.connect(self.find_annotations_date_to_dateEdit.reset_to_date)
        self.scgl.addWidget(self.find_annotations_date_to_dateEdit, row, 3, 1, 1)
        self.scgl.addWidget(self.find_annotations_date_to_dateEdit.clear_button, row, 4, 1, 1)
        row += 1

        # ~~~~~~~~ Create a horizontal line ~~~~~~~~
        self.hl = QFrame(self)
        self.hl.setGeometry(QRect(0, 0, 1, 3))
        self.hl.setFrameShape(QFrame.HLine)
        self.hl.setFrameShadow(QFrame.Raised)
        self.scgl.addWidget(self.hl, row, 0, 1, 5)
        row += 1

        # ~~~~~~~~ Create the results label field ~~~~~~~~
        self.result_label = QLabel('<p style="color:red">{0}</p>'.format(_('scanning…')))
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(False)

        sizePolicy = QtGui.QSizePolicy(qSizePolicy_Minimum, qSizePolicy_Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.result_label.sizePolicy().hasHeightForWidth())
        self.result_label.setSizePolicy(sizePolicy)
        self.result_label.setMinimumSize(QtCore.QSize(250, 0))
        self.scgl.addWidget(self.result_label, row, 0, 1, 5)
        row += 1

        # ~~~~~~~~ Create the ButtonBox ~~~~~~~~
        self.dialogButtonBox = QDialogButtonBox(self)
        self.dialogButtonBox.setOrientation(Qt.Horizontal)
        if False:
            self.update_button = QPushButton(_('Update results'))
            self.update_button.setDefault(True)
            self.update_button.setVisible(False)
            self.dialogButtonBox.addButton(self.update_button, QDialogButtonBox.ActionRole)

        self.cancel_button = self.dialogButtonBox.addButton(self.dialogButtonBox.Cancel)
        self.find_button = self.dialogButtonBox.addButton(self.dialogButtonBox.Ok)
        self.find_button.setText(_('Find Matching Books'))

        self.l.addWidget(self.dialogButtonBox)
        self.dialogButtonBox.clicked.connect(self.find_annotations_dialog_clicked)

        # ~~~~~~~~ Add a spacer ~~~~~~~~
        self.spacerItem = QSpacerItem(20, 40, qSizePolicy_Minimum, qSizePolicy_Expanding)
        self.l.addItem(self.spacerItem)

        # ~~~~~~~~ Restore previously saved settings ~~~~~~~~
        self.restore_settings()

        # ~~~~~~~~ Declare sizing ~~~~~~~~
        sizePolicy = QSizePolicy(qSizePolicy_Preferred, qSizePolicy_Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.resize_dialog()

        # ~~~~~~~~ Connect all signals ~~~~~~~~
        self.find_annotations_reader_comboBox.currentIndexChanged.connect(partial(self.update_results, 'reader'))
        self.find_annotations_color_comboBox.currentIndexChanged.connect(partial(self.update_results, 'color'))
        self.find_annotations_text_lineEdit.editingFinished.connect(partial(self.update_results, 'text'))
        self.find_annotations_note_lineEdit.editingFinished.connect(partial(self.update_results, 'note'))
#        self.connect(self.find_annotations_text_lineEdit, pyqtSignal("return_pressed"), self.return_pressed)
        self.find_annotations_text_lineEdit.return_pressed.connect(self.return_pressed)
#        self.connect(self.find_annotations_note_lineEdit, pyqtSignal("return_pressed"), self.return_pressed)
        self.find_annotations_note_lineEdit.return_pressed.connect(self.return_pressed)

        # Date range signals connected in inventory_available()

        # ~~~~~~~~ Allow dialog to render before doing inventory ~~~~~~~~
        #field = self.prefs.get('cfg_annotations_destination_field', None)
        field = get_cc_mapping('annotations', 'field', None)
        self.annotated_books_scanner = InventoryAnnotatedBooks(self.opts.gui, field, get_date_range=True)
        self.annotated_books_scanner.signal.connect(self.inventory_available)
        QTimer.singleShot(1, self.start_inventory_scan)

    def clear_note_field(self):
        if str(self.find_annotations_note_lineEdit.text()) > '':
            self.find_annotations_note_lineEdit.setText('')
            self.update_results('clear_note_field')

    def clear_text_field(self):
        if str(self.find_annotations_text_lineEdit.text()) > '':
            self.find_annotations_text_lineEdit.setText('')
            self.update_results('clear_text_field')

    def find_annotations_dialog_clicked(self, button):
        if self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.AcceptRole:
            self.save_settings()
            self.accept()
        elif self.dialogButtonBox.buttonRole(button) == QDialogButtonBox.RejectRole:
            self.close()

    def inventory_available(self):
        '''
        Update the Date range widgets with the rounded oldest, newest dates
        Don't connect date signals until date range available
        '''
        self._log_location()

        # Reset the date range based on available annotations
        oldest = QDateTime(datetime.fromtimestamp(self.annotated_books_scanner.oldest_annotation))
        oldest_day = QDateTime(datetime.fromtimestamp(self.annotated_books_scanner.oldest_annotation).replace(hour=0, minute=0, second=0))
        newest = QDateTime(datetime.fromtimestamp(self.annotated_books_scanner.newest_annotation))
        newest_day = QDateTime(datetime.fromtimestamp(self.annotated_books_scanner.newest_annotation).replace(hour=23, minute=59, second=59))

        # Set 'From' date limits to inventory values
        self.find_annotations_date_from_dateEdit.setMinimumDateTime(oldest_day)
        self.find_annotations_date_from_dateEdit.current_val = oldest
        self.find_annotations_date_from_dateEdit.setMaximumDateTime(newest_day)

        # Set 'To' date limits to inventory values
        self.find_annotations_date_to_dateEdit.setMinimumDateTime(oldest_day)
        self.find_annotations_date_to_dateEdit.current_val = newest_day
        self.find_annotations_date_to_dateEdit.setMaximumDateTime(newest_day)

        # Connect the signals for date range changes
        self.find_annotations_date_from_dateEdit.dateTimeChanged.connect(partial(self.update_results, 'from_date'))
        self.find_annotations_date_to_dateEdit.dateTimeChanged.connect(partial(self.update_results, 'to_date'))

        self.update_results('inventory_available')

    def restore_settings(self):
        self.blockSignals(True)

        ra = self.prefs.get('find_annotations_reader_comboBox', self.GENERIC_READER)
        ra_index = self.find_annotations_reader_comboBox.findText(ra)
        self.find_annotations_reader_comboBox.setCurrentIndex(ra_index)

        color = self.prefs.get('find_annotations_color_comboBox', self.GENERIC_STYLE)
        color_index = self.find_annotations_color_comboBox.findText(color)
        self.find_annotations_color_comboBox.setCurrentIndex(color_index)

        text = self.prefs.get('find_annotations_text_lineEdit', '')
        self.find_annotations_text_lineEdit.setText(text)

        note = self.prefs.get('find_annotations_note_lineEdit', '')
        self.find_annotations_note_lineEdit.setText(note)

        if False:
            from_date = self.prefs.get('find_annotations_date_from_dateEdit', datetime(1970,1,1))
            self.find_annotations_date_from_dateEdit.current_val = from_date
            to_date = self.prefs.get('find_annotations_date_to_dateEdit', datetime.today())
            self.find_annotations_date_to_dateEdit.current_val = to_date

        self.blockSignals(False)

    def return_pressed(self):
        self.update_results("return_pressed")

    def save_settings(self):
        ra = str(self.find_annotations_reader_comboBox.currentText())
        self.prefs.set('find_annotations_reader_comboBox', ra)

        color = str(self.find_annotations_color_comboBox.currentText())
        self.prefs.set('find_annotations_color_comboBox', color)

        text = str(self.find_annotations_text_lineEdit.text())
        self.prefs.set('find_annotations_text_lineEdit', text)

        note = str(self.find_annotations_note_lineEdit.text())
        self.prefs.set('find_annotations_note_lineEdit', note)

        if False:
            from_date = self.find_annotations_date_from_dateEdit.current_val
            self.prefs.set('find_annotations_date_from_dateEdit', from_date)

            to_date = self.find_annotations_date_to_dateEdit.current_val
            self.prefs.set('find_annotations_date_to_dateEdit', to_date)

    def start_inventory_scan(self):
        self._log_location()
        self.annotated_books_scanner.start()

    def update_results(self, trigger):
        #self._log_location(trigger)
        reader_to_match = str(self.find_annotations_reader_comboBox.currentText())
        color_to_match = str(self.find_annotations_color_comboBox.currentText())
        text_to_match = str(self.find_annotations_text_lineEdit.text())
        note_to_match = str(self.find_annotations_note_lineEdit.text())

        try:
            from_date = self.find_annotations_date_from_dateEdit.dateTime().toSecsSinceEpoch()
            to_date = self.find_annotations_date_to_dateEdit.dateTime().toSecsSinceEpoch()
        except: # For Python/Qt backwards compatability
            from_date = self.find_annotations_date_from_dateEdit.dateTime().toTime_t()
            to_date = self.find_annotations_date_to_dateEdit.dateTime().toTime_t()

        annotation_map = self.annotated_books_scanner.annotation_map
        #field = self.prefs.get("cfg_annotations_destination_field", None)
        field = get_cc_mapping('annotations', 'field', None)

        db = self.opts.gui.current_db
        matched_titles = []
        self.matched_ids = set()

        for cid in annotation_map:
            mi = db.get_metadata(cid, index_is_id=True)
            soup = None
            if field == 'Comments':
                if mi.comments:
                    soup = BeautifulSoup(mi.comments)
            else:
                if mi.get_user_metadata(field, False)['#value#'] is not None:
                    soup = BeautifulSoup(mi.get_user_metadata(field, False)['#value#'])
            if soup:
                uas = soup.findAll('div', 'annotation')
                for ua in uas:
                    # Are we already logged?
                    if cid in self.matched_ids:
                        continue

                    # Check reader
                    if reader_to_match != self.GENERIC_READER:
                        this_reader = ua['reader']
                        if this_reader != reader_to_match:
                            continue

                    # Check color
                    if color_to_match != self.GENERIC_STYLE:
                        this_color = ua.find('table')['color']
                        if this_color != color_to_match:
                            continue

                    # Check date range, allow for mangled timestamp
                    try:
                        timestamp = float(ua.find('td', 'timestamp')['uts'])
                        if timestamp < from_date or timestamp > to_date:
                            continue
                    except:
                        continue

                    highlight_text = ''
                    try:
                        pels = ua.findAll('p', 'highlight')
                        highlight_text = '\n'.join([p.string or '' for p in pels])
                    except:
                        pass
                    if text_to_match > '':
                        if not re.search(text_to_match, highlight_text, flags=re.IGNORECASE):
                            continue

                    note_text = ''
                    try:
                        nels = ua.findAll('p', 'note')
                        note_text = '\n'.join([n.string or '' for n in nels])
                    except:
                        pass
                    if note_to_match > '':
                        if not re.search(note_to_match, note_text, flags=re.IGNORECASE):
                            continue

                    # If we made it this far, add the id to matched_ids
                    self.matched_ids.add(cid)
                    matched_titles.append(mi.title)

        # Update the results box
        matched_titles.sort()
        if len(annotation_map):
            if len(matched_titles):
                first_match = ("<i>%s</i>" % matched_titles[0])
                if len(matched_titles) == 1:
                    results = first_match
                else:
                    results = first_match + (_(" and {0} more.").format(len(matched_titles) - 1))
                self.result_label.setText('<p style="color:blue">{0}</p>'.format(results))
            else:
                self.result_label.setText('<p style="color:red">{0}</p>'.format(_('no matches')))
        else:
            self.result_label.setText('<p style="color:red">{0}</p>'.format(_('no annotated books in library')))

        self.resize_dialog()
