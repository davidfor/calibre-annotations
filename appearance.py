#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import re, time

# calibre Python 3 compatibility.
import six
from six import text_type as unicode

from functools import partial

from calibre.devices.usbms.driver import debug_print

try:
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (Qt, QAbstractItemView, QCheckBox, QColorDialog, QComboBox,
                          QDialogButtonBox,
                          QFont, QGridLayout, QGroupBox,
                          QHBoxLayout, QIcon, QLabel, QLineEdit,
                          QPlainTextEdit, QSizePolicy,
                          QTableWidget, QTableWidgetItem, QToolButton,
                          QVBoxLayout)
    from PyQt5.Qt import QTextEdit as QWebView # Renaming to keep backwards compatibility.
except ImportError:
    from PyQt4 import QtCore, QtGui
    from PyQt4.Qt import (Qt, QAbstractItemView, QCheckBox, QColorDialog, QComboBox,
                          QDialogButtonBox,
                          QFont, QGridLayout, QGroupBox,
                          QHBoxLayout, QIcon, QLabel, QLineEdit,
                          QPlainTextEdit, QSizePolicy,
                          QTableWidget, QTableWidgetItem, QToolButton,
                          QVBoxLayout)
    from PyQt4.QtWebKit import QWebView

from calibre.constants import islinux, isosx, iswindows
from calibre.utils.config import JSONConfig

from calibre_plugins.annotations.common_utils import (HelpView, SizePersistedDialog)

try:
    debug_print("Annotations::appearance.py - loading translations")
    load_translations()
except NameError:
    debug_print("Annotations::appearance.py - exception when loading translations")
    pass # load_translations() added in calibre 1.9


# Default timestamp format: National representation of time and date
default_timestamp = '%c'

default_elements = [
                   {
                    'ordinal':0,
                    'name':'Timestamp',
                    'css':"font-size:80%;\n" +
                              "font-weight:bold;\n" +
                              "margin:0;"
                   },
                   {
                    'ordinal':1,
                    'name':'Text',
                    'css':"margin:0;\n" +
                              "text-indent:0.5em;"
                   },
                   {
                    'ordinal':2,
                    'name':'Note',
                    'css':"font-size:90%;\n" +
                              "font-style:italic;\n" +
                              "margin:0;"
                   }]
translatable_element_names = {
                              'Timestamp':_('Timestamp'),
                              'Text':_('Text'),
                              'Note':_('Note')
                              }

class CheckableTableWidgetItem(QTableWidgetItem):
    '''
    Borrowed from kiwidude
    '''

    def __init__(self, checked=False, is_tristate=False):
        QTableWidgetItem.__init__(self, '')
        self.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled))
        if is_tristate:
            self.setFlags(self.flags() | Qt.ItemIsTristate)
        if checked:
            self.setCheckState(Qt.Checked)
        else:
            if is_tristate and checked is None:
                self.setCheckState(Qt.PartiallyChecked)
            else:
                self.setCheckState(Qt.Unchecked)

    def get_boolean_value(self):
        '''
        Return a boolean value indicating whether checkbox is checked
        If this is a tristate checkbox, a partially checked value is returned as None
        '''
        if self.checkState() == Qt.PartiallyChecked:
            return None
        else:
            return self.checkState() == Qt.Checked


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        # Disable the mouse wheel on top of the combo box changing selection as plays havoc in a grid
        event.ignore()


class DateTimeComboBox(NoWheelComboBox):
    # Caller is responsible for providing the list in the preferred order
    def __init__(self, parent, items, selected_text, insert_blank=True):
        NoWheelComboBox.__init__(self, parent)
        self.populate_combo(items, selected_text, insert_blank)

    def populate_combo(self, items, selected_text, insert_blank):
        if insert_blank:
            self.addItems([''])
        for id, text in items:
            self.addItem(text, id)

        if selected_text:
            idx = self.findData(selected_text)
            self.setCurrentIndex(idx)
        else:
            self.setCurrentIndex(0)


class AnnotationElementsTable(QTableWidget):
    '''
    QTableWidget managing CSS rules
    '''
    DEBUG = True
    #MAXIMUM_TABLE_HEIGHT = 113
    ELEMENT_FIELD_WIDTH = 250
    if isosx:
        FONT = QFont('Monaco', 11)
    elif iswindows:
        FONT = QFont('Lucida Console', 9)
    elif islinux:
        FONT = QFont('Monospace', 9)
        FONT.setStyleHint(QFont.TypeWriter)

    COLUMNS = {
                'ELEMENT_NAME': {'ordinal': 0, 'name': 'Element Name'},
                'ELEMENT':      {'ordinal': 1, 'name': _('Element')},
                'CSS':          {'ordinal': 2, 'name': _('CSS')},
                }

    sample_ann_1 = {
        'text': ['Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean placerat condimentum semper. Aliquam hendrerit nisl mauris, nec laoreet orci. Donec rutrum consequat ultricies.',
                 'Curabitur sollicitudin euismod felis, vitae mollis magna vestibulum id.'],
        'note': [_('This is a note appended to the highlight. This highlight is using the default background/foreground.'),
                 _('And additional comments after a linebreak.')],
        'timestamp': time.mktime(time.localtime()),
        'location': 'Chapter 4',
        'location_sort': 0
        }
    sample_ann_2 = {
        'text': ['Phasellus sit amet ipsum id velit commodo convallis. In dictum felis non tellus volutpat in tincidunt neque varius. Sed at mauris augue. Vestibulum ligula nunc, ullamcorper id suscipit sed, auctor quis erat. In hac habitasse platea dictumst. Aliquam sit amet nulla dolor, ut tempus libero. In hac habitasse platea dictumst. Etiam consectetur orci vel massa eleifend in vestibulum odio auctor. Praesent orci turpis, aliquet non eleifend sit amet, sollicitudin sit amet augue.'],
        'highlightcolor': 'Green',
        'timestamp': time.mktime(time.localtime()),
        'location': 'Chapter 12',
        'location_sort': 1
        }
    sample_ann_3 = {
        'text': ['Morbi massa tellus, laoreet id pretium sed, volutpat in felis.',
                 'Donec massa nulla, malesuada vitae volutpat quis, accumsan ut tellus.'],
        'note': [_('This is a note appended to the highlight.'),
                 _('And additional comments after a linebreak.')],
        'highlightcolor': 'Purple',
        'timestamp': time.mktime(time.localtime()),
        'location': 'Chapter 53',
        'location_sort': 2
        }


    def __init__(self, parent, object_name):
        self.parent = parent
        self.prefs = parent.prefs
        self.elements = self.prefs.get('appearance_css', None)
        debug_print("AnnotationElementsTable::__init__ - self.elements", self.elements)
        if not self.elements:
            self.elements = default_elements
            debug_print("AnnotationElementsTable::__init__ - self.elements", self.elements)

        QTableWidget.__init__(self)
        self.setObjectName(object_name)
        self.layout = parent.elements_hl.layout()

        # Add ourselves to the layout
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        #sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        #self.setMaximumSize(QSize(16777215, self.MAXIMUM_TABLE_HEIGHT))

        self.setColumnCount(0)
        self.setRowCount(0)
        self.layout.addWidget(self)

    def _init_controls(self):
        # Add the control set
        vbl = QVBoxLayout()
        self.move_element_up_tb = QToolButton()
        self.move_element_up_tb.setObjectName("move_element_up_tb")
        self.move_element_up_tb.setToolTip(_('Move element up'))
        self.move_element_up_tb.setIcon(QIcon(I('arrow-up.png')))
        self.move_element_up_tb.clicked.connect(self.move_row_up)
        vbl.addWidget(self.move_element_up_tb)

        self.undo_css_tb = QToolButton()
        self.undo_css_tb.setObjectName("undo_css_tb")
        self.undo_css_tb.setToolTip(_('Restore CSS to last saved'))
        self.undo_css_tb.setIcon(QIcon(I('edit-undo.png')))
        self.undo_css_tb.clicked.connect(partial(self.undo_reset_button_clicked, 'undo'))
        vbl.addWidget(self.undo_css_tb)

        self.reset_css_tb = QToolButton()
        self.reset_css_tb.setObjectName("reset_css_tb")
        self.reset_css_tb.setToolTip(_('Reset CSS to default'))
        self.reset_css_tb.setIcon(QIcon(I('trash.png')))
        self.reset_css_tb.clicked.connect(partial(self.undo_reset_button_clicked, 'reset'))
        vbl.addWidget(self.reset_css_tb)

        self.move_element_down_tb = QToolButton()
        self.move_element_down_tb.setObjectName("move_element_down_tb")
        self.move_element_down_tb.setToolTip(_('Move element down'))
        self.move_element_down_tb.setIcon(QIcon(I('arrow-down.png')))
        self.move_element_down_tb.clicked.connect(self.move_row_down)
        vbl.addWidget(self.move_element_down_tb)

        self.layout.addLayout(vbl)

    def _init_table_widget(self):
        header_labels = [self.COLUMNS[index]['name'] \
            for index in sorted(self.COLUMNS.keys(), key=lambda c: self.COLUMNS[c]['ordinal'])]
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.verticalHeader().setVisible(False)

        self.setSortingEnabled(False)

        # Select single rows
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def convert_row_to_data(self, row):
        data = {}
        data['ordinal'] = row
#         data['name'] = unicode(self.cellWidget(row, self.COLUMNS['ELEMENT']['ordinal']).text()).strip()
        data['name'] = unicode(self.cellWidget(row, self.COLUMNS['ELEMENT_NAME']['ordinal']).text()).strip()
        data['css'] = unicode(self.cellWidget(row, self.COLUMNS['CSS']['ordinal']).toPlainText()).strip()
        return data

    def css_edited(self, row):
        self.select_and_scroll_to_row(row)
        col = self.COLUMNS['CSS']['ordinal']
        widget = self.cellWidget(row, col)
        css = unicode(widget.toPlainText())
        lines = []
        for line in css.split('\n'):
            lines.append(re.sub('^\s*', '', line))
        self.resize_row_height(lines, row)
#         self.prefs.set('appearance_css', self.get_data())
        widget.setFocus()
        self.preview_css()

    def get_data(self):
        data_items = []
        for row in range(self.rowCount()):
            data = self.convert_row_to_data(row)
            data_items.append(
                               {'ordinal': data['ordinal'],
                                'name': data['name'],
#                                 'translatable_name': translatable_element_names[data['name']],
                                'css': data['css'],
                                })
        return data_items

    def initialize(self):
        self._init_table_widget()
        self._init_controls()
        self.populate_table()
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

        # Update preview window, select first row
        self.css_edited(0)

    def move_row(self, source, dest):

        self.blockSignals(True)
        # Save the contents of the destination row
        saved_data = self.convert_row_to_data(dest)
        debug_print("Annotations::appearance.py::move_row - saved_data", saved_data)

        # Remove the destination row
        self.removeRow(dest)

        # Insert a new row at the original location
        self.insertRow(source)

        # Populate it with the saved data
        self.populate_table_row(source, saved_data)

        self.select_and_scroll_to_row(dest)
        self.blockSignals(False)

        self.css_edited(dest)

    def move_row_down(self):
        src_row = self.currentRow()
        dest_row = src_row + 1
        if dest_row == self.rowCount():
            return
        self.move_row(src_row, dest_row)

    def move_row_up(self):
        src_row = self.currentRow()
        dest_row = src_row - 1
        if dest_row < 0:
            return
        self.move_row(src_row, dest_row)

    def populate_table(self):
        # Format of rules list is different if default values vs retrieved JSON
        # Hack to normalize list style
        elements = self.elements
        if elements and type(elements[0]) is list:
            elements = elements[0]
        self.setFocus()
        elements = sorted(elements, key=lambda k: k['ordinal'])
        for row, element in enumerate(elements):
            self.insertRow(row)
            self.select_and_scroll_to_row(row)
            self.populate_table_row(row, element)
        self.selectRow(0)
        self.setColumnHidden(0, True)

    def populate_table_row(self, row, data):
        self.blockSignals(True)
        self.setCellWidget(row, self.COLUMNS['ELEMENT_NAME']['ordinal'], QLabel(data['name']))
        translatable_name = translatable_element_names[data['name']]
        self.set_element_name_in_row(row, self.COLUMNS['ELEMENT']['ordinal'], translatable_name)
        self.set_css_in_row(row, self.COLUMNS['CSS']['ordinal'], data['css'])
        self.blockSignals(False)

    def preview_css(self):
        '''
        Construct a dummy annotation for preview purposes
        '''
        from calibre_plugins.annotations.annotations import Annotation, Annotations

        pas = Annotations(None, title=_("Preview"))
        pas.annotations.append(Annotation(self.sample_ann_1))
        pas.annotations.append(Annotation(self.sample_ann_2))
        pas.annotations.append(Annotation(self.sample_ann_3))
        self.parent.wv.setHtml(pas.to_HTML())

    def resize_row_height(self, lines, row):
        point_size = self.FONT.pointSize()
        if isosx:
            height = 30 + (len(lines) - 1) * (point_size + 4)
        elif iswindows:
            height = 26 + (len(lines) - 1) * (point_size + 3)
        elif islinux:
            height = 30 + (len(lines) - 1) * (point_size + 6)

        self.verticalHeader().resizeSection(row, height)

    def select_and_scroll_to_row(self, row):
        self.setFocus()
        self.selectRow(row)
        self.scrollToItem(self.currentItem())

    def set_element_name_in_row(self, row, col, name):
        rule_name = QLabel(" %s " % name)
        rule_name.setFont(self.FONT)
        self.setCellWidget(row, col, rule_name)

    def set_css_in_row(self, row, col, css):
        # Clean up multi-line css formatting
        # A single line is 30px tall, subsequent lines add 16px

        lines = []
        for line in css.split('\n'):
            lines.append(re.sub('^\s*', '', line))
        css_content = QPlainTextEdit('\n'.join(lines))
        css_content.setFont(self.FONT)
        css_content.textChanged.connect(partial(self.css_edited, row))
        self.setCellWidget(row, col, css_content)
        self.resize_row_height(lines, row)

    def undo_reset_button_clicked(self, mode):
        """
        Figure out which element is being reset
        Reset to last save or default
        """
        debug_print("undo_reset_button_clicked - mode=", mode)
        row = self.currentRow()
        data = self.convert_row_to_data(row)
        debug_print("undo_reset_button_clicked - data=", data)

        # Get default
        default_css = None
        for de in default_elements:
            if de['name'] == data['name']:
                default_css = de
                break

        # Get last saved
        last_saved_css = None
        saved_elements = self.prefs.get('appearance_css', None)
        last_saved_css = default_css
        debug_print("undo_reset_button_clicked - saved_elements=", saved_elements)
        debug_print("undo_reset_button_clicked - last_saved_css=", last_saved_css)
        if saved_elements:
            for se in saved_elements:
                if se['name'] == data['name']:
                    debug_print("undo_reset_button_clicked - se=", se)
                    last_saved_css = se
                    break
        debug_print("undo_reset_button_clicked - last_saved_css=", last_saved_css)

        # Restore css
        if mode == 'reset':
            self.populate_table_row(row, default_css)
        elif mode == 'undo':
            self.populate_table_row(row, last_saved_css)

        # Refresh the stored data
        #self.prefs.set('appearance_css', self.get_data())
        self.css_edited(row)


class AnnotationsAppearance(SizePersistedDialog):
    '''
    Dialog for managing CSS rules, including Preview window
    '''
    if isosx:
        FONT = QFont('Monaco', 12)
    elif iswindows:
        FONT = QFont('Lucida Console', 9)
    elif islinux:
        FONT = QFont('Monospace', 9)
        FONT.setStyleHint(QFont.TypeWriter)

    def __init__(self, parent, icon, prefs):

        self.parent = parent
        self.prefs = prefs
        self.icon = icon
        super(AnnotationsAppearance, self).__init__(parent, 'appearance_dialog')
        self.setWindowTitle(_('Modify appearance'))
        self.setWindowIcon(icon)
        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        # Add a label for description
        #self.description_label = QLabel(_("Descriptive text here"))
        #self.l.addWidget(self.description_label)

        # Add a group box, vertical layout for preview window
        self.preview_gb = QGroupBox(self)
        self.preview_gb.setTitle(_("Preview"))
        self.preview_vl = QVBoxLayout(self.preview_gb)
        self.l.addWidget(self.preview_gb)

        self.wv = QWebView()
        self.wv.setHtml('<p></p>')
        self.wv.setMinimumHeight(100)
        self.wv.setMaximumHeight(16777215)
        self.wv.setGeometry(0, 0, 200, 100)
        self.wv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_vl.addWidget(self.wv)

        # Create a group box, horizontal layout for the table
        self.css_table_gb = QGroupBox(self)
        self.css_table_gb.setTitle(_("Annotation elements"))
        self.elements_hl = QHBoxLayout(self.css_table_gb)
        self.l.addWidget(self.css_table_gb)

        # Add the group box to the main layout
        self.elements_table = AnnotationElementsTable(self, 'annotation_elements_tw')
        self.elements_hl.addWidget(self.elements_table)
        self.elements_table.initialize()

        # Options

        self.options_gb = QGroupBox(self)
        self.options_gb.setTitle(_("Options"))
        self.options_gl = QGridLayout(self.options_gb)
        self.l.addWidget(self.options_gb)
        current_row = 0

        # default highlight colors
        ## background highlight
        highlight_bg = self.prefs.get("appearance_highlight_bg")
        self.highlight_color_bg_label = QLabel(_("Default highlight background"))
        self.options_gl.addWidget(self.highlight_color_bg_label, current_row, 0)

        self.highlight_color_bg_button = QToolButton(self)
        self.highlight_color_bg_button.setToolTip(_("Pick a color"))
        self.set_color(self.highlight_color_bg_button, highlight_bg)
        self.highlight_color_bg_button.clicked.connect(lambda: self.choose_color("appearance_highlight_bg", self.highlight_color_bg_button))
        self.options_gl.addWidget(self.highlight_color_bg_button, current_row, 1)

        self.highlight_color_bg_reset = QToolButton(self)
        self.highlight_color_bg_reset.setToolTip(_("Reset to default"))
        self.highlight_color_bg_reset.setIcon(QIcon(I('trash.png')))
        self.highlight_color_bg_reset.clicked.connect(lambda: self.reset_color("appearance_highlight_bg", self.highlight_color_bg_button, "transparent"))
        self.options_gl.addWidget(self.highlight_color_bg_reset, current_row, 2)
        current_row += 1

        ## foreground highlight
        highlight_fg = self.prefs.get("appearance_highlight_fg")
        self.highlight_color_fg_label = QLabel(_("Default highlight foreground"))
        self.options_gl.addWidget(self.highlight_color_fg_label, current_row, 0)

        self.highlight_color_fg_button = QToolButton(self)
        self.highlight_color_fg_button.setToolTip(_("Pick a color"))
        self.set_color(self.highlight_color_fg_button, highlight_fg)
        self.highlight_color_fg_button.clicked.connect(lambda: self.choose_color("appearance_highlight_fg", self.highlight_color_fg_button))
        self.options_gl.addWidget(self.highlight_color_fg_button, current_row, 1)

        self.highlight_color_fg_reset = QToolButton(self)
        self.highlight_color_fg_reset.setToolTip(_("Reset to default"))
        self.highlight_color_fg_reset.setIcon(QIcon(I('trash.png')))
        self.highlight_color_fg_reset.clicked.connect(lambda: self.reset_color("appearance_highlight_fg", self.highlight_color_fg_button, "#000000"))
        self.options_gl.addWidget(self.highlight_color_fg_reset, current_row, 2)
        current_row += 1

        # <hr/> separator
        # addWidget(widget, row, col, rowspan, colspan)
        self.hr_checkbox = QCheckBox(_('Add horizontal rule between annotations'))
        self.hr_checkbox.stateChanged.connect(self.hr_checkbox_changed)
        self.hr_checkbox.setCheckState(
            JSONConfig('plugins/annotations').get('appearance_hr_checkbox', False))
        self.options_gl.addWidget(self.hr_checkbox, current_row, 0, 1, 4)
        current_row += 1

        # Timestamp
        self.timestamp_fmt_label = QLabel(_("Timestamp format:"))
        self.options_gl.addWidget(self.timestamp_fmt_label, current_row, 0)

        self.timestamp_fmt_le = QLineEdit(
            JSONConfig('plugins/annotations').get('appearance_timestamp_format', default_timestamp),
            parent=self)
        self.timestamp_fmt_le.textEdited.connect(self.timestamp_fmt_changed)
        self.timestamp_fmt_le.setFont(self.FONT)
        self.timestamp_fmt_le.setObjectName('timestamp_fmt_le')
        self.timestamp_fmt_le.setToolTip(_('Format string for timestamp'))
        self.timestamp_fmt_le.setMaximumWidth(16777215)
        self.timestamp_fmt_le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.options_gl.addWidget(self.timestamp_fmt_le, current_row, 1)

        self.timestamp_fmt_reset_tb = QToolButton(self)
        self.timestamp_fmt_reset_tb.setToolTip(_("Reset to default"))
        self.timestamp_fmt_reset_tb.setIcon(QIcon(I('trash.png')))
        self.timestamp_fmt_reset_tb.clicked.connect(self.reset_timestamp_to_default)
        self.options_gl.addWidget(self.timestamp_fmt_reset_tb, current_row, 2)

        self.timestamp_fmt_help_tb = QToolButton(self)
        self.timestamp_fmt_help_tb.setToolTip(_("Format string reference"))
        self.timestamp_fmt_help_tb.setIcon(QIcon(I('help.png')))
        self.timestamp_fmt_help_tb.clicked.connect(self.show_help)
        self.options_gl.addWidget(self.timestamp_fmt_help_tb, current_row, 3)

        # Button box
        bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.l.addWidget(bb)

        # Spacer
        self.spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.l.addItem(self.spacerItem)

        # Sizing
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.resize_dialog()

    def hr_checkbox_changed(self, state):
        self.prefs.set('appearance_hr_checkbox', state)
        self.elements_table.preview_css()

    def reset_timestamp_to_default(self):
        from calibre_plugins.annotations.appearance import default_timestamp
        self.timestamp_fmt_le.setText(default_timestamp)
        self.timestamp_fmt_changed()

    def show_help(self):
        '''
        Display strftime help file
        '''
        help_html = get_resources('help/timestamp_formats.html')
        print("1 - %s" % help_html)
        help_html = help_html.decode('utf-8')
        print("2 - %s" % help_html)

        hv = HelpView(self, self.icon, self.prefs,
            html=help_html, title=_("Timestamp formats"))
        hv.show()

    def set_color(self, button, color):
        if color == "transparent":
            button.setStyleSheet("")
        else:
            button.setStyleSheet("background-color: %s;" % color)

    def choose_color(self, pref, button):
        color = QColorDialog.getColor()
        self.prefs.set(pref, str(color.name()))
        self.set_color(button, color.name())
        self.elements_table.preview_css()

    def reset_color(self, pref, button, color):
        self.prefs.set(pref, color)
        self.set_color(button, color)
        self.elements_table.preview_css()

    def sizeHint(self):
        return QtCore.QSize(600, 200)

    def timestamp_fmt_changed(self):
        self.prefs.set('appearance_timestamp_format', str(self.timestamp_fmt_le.text()))
        self.elements_table.preview_css()
