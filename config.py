#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

# Windows: calibre-customize -a $plugin".zip"
# calibre-debug -e __init__.py

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

from datetime import datetime
from functools import partial
import hashlib, importlib, os, re, sys
from time import mktime

# calibre Python 3 compatibility.
import six
from six import text_type as unicode

try:
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (Qt, QCheckBox, QComboBox, QFrame, QGridLayout,
        QGroupBox, QIcon, QLabel, QLineEdit, QPushButton,
        QRect, QThread, QTimer, QToolButton, QVBoxLayout, QWidget,
        pyqtSignal)
    from PyQt5.QtWidgets import QSizePolicy
except ImportError as e:
    from PyQt4 import QtGui
    from PyQt4.Qt import (Qt, QCheckBox, QComboBox, QFrame, QGridLayout,
        QGroupBox, QIcon, QLabel, QLineEdit, QPushButton,
        QRect, QThread, QTimer, QToolButton, QVBoxLayout, QWidget,
        pyqtSignal)
    from PyQt4.QtGui import QSizePolicy

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.constants import islinux, iswindows
from calibre.devices.usbms.driver import debug_print
from calibre.utils.config import JSONConfig, config_dir
from calibre.utils.logging import Log

from calibre_plugins.annotations.action import LIBIMOBILEDEVICE_AVAILABLE
from calibre_plugins.annotations.appearance import AnnotationsAppearance
from calibre_plugins.annotations.common_utils import (Logger, Struct,
    existing_annotations, get_cc_mapping, get_icon, inventory_controls,
    move_annotations, restore_state, save_state, set_cc_mapping)

try:
    debug_print("Annotations::config.py - loading translations")
    load_translations()
except NameError:
    debug_print("Annotations::config.py - exception when loading translations")
    pass # load_translations() added in calibre 1.9

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

plugin_prefs = JSONConfig('plugins/annotations')

dialog_resources_path = os.path.join(config_dir, 'plugins', 'annotations_resources', 'dialogs')

class ConfigWidget(QWidget, Logger):
    # Manually managed controls when saving/restoring
    EXCLUDED_CONTROLS = [
        'cfg_annotations_destination_comboBox'
        ]

    #LOCATION_TEMPLATE = "{cls}:{func}({arg1}) {arg2}"

    WIZARD_PROFILES = {
        'Annotations': {
            'label': 'mm_annotations',
            'datatype': 'comments',
            'display': {},
            'is_multiple': False
            }
        }

    def __init__(self, plugin_action):
        self.gui = plugin_action.gui
        self.opts = plugin_action.opts

        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        # ~~~~~~~~ Create the runtime options group box ~~~~~~~~
        self.cfg_runtime_options_gb = QGroupBox(self)
        self.cfg_runtime_options_gb.setTitle(_('Runtime options'))
        self.l.addWidget(self.cfg_runtime_options_gb)
        self.cfg_runtime_options_qvl = QVBoxLayout(self.cfg_runtime_options_gb)

        # ~~~~~~~~ Disable caching checkbox ~~~~~~~~
        self.cfg_disable_caching_checkbox = QCheckBox(_('Disable caching'))
        self.cfg_disable_caching_checkbox.setObjectName('cfg_disable_caching_checkbox')
        self.cfg_disable_caching_checkbox.setToolTip(_('Force reload of reader database'))
        self.cfg_disable_caching_checkbox.setChecked(False)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_disable_caching_checkbox)

        # ~~~~~~~~ plugin logging checkbox ~~~~~~~~
        self.cfg_plugin_debug_log_checkbox = QCheckBox(_('Enable debug logging for Annotations plugin'))
        self.cfg_plugin_debug_log_checkbox.setObjectName('cfg_plugin_debug_log_checkbox')
        self.cfg_plugin_debug_log_checkbox.setToolTip(_('Print plugin diagnostic messages to console'))
        self.cfg_plugin_debug_log_checkbox.setChecked(False)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_plugin_debug_log_checkbox)

        # ~~~~~~~~ libiMobileDevice logging checkbox ~~~~~~~~
        self.cfg_libimobiledevice_debug_log_checkbox = QCheckBox(_('Enable debug logging for libiMobileDevice'))
        self.cfg_libimobiledevice_debug_log_checkbox.setObjectName('cfg_libimobiledevice_debug_log_checkbox')
        self.cfg_libimobiledevice_debug_log_checkbox.setToolTip(_('Print libiMobileDevice debug messages to console'))
        self.cfg_libimobiledevice_debug_log_checkbox.setChecked(False)
        self.cfg_libimobiledevice_debug_log_checkbox.setEnabled(LIBIMOBILEDEVICE_AVAILABLE)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_libimobiledevice_debug_log_checkbox)

        # ~~~~~~~~ Create the Annotations options group box ~~~~~~~~
        self.cfg_annotation_options_gb = QGroupBox(self)
        self.cfg_annotation_options_gb.setTitle(_('Annotation options'))
        self.l.addWidget(self.cfg_annotation_options_gb)

        self.cfg_annotation_options_qgl = QGridLayout(self.cfg_annotation_options_gb)
        current_row = 0

        # Add the label/combobox for annotations destination
        self.cfg_annotations_destination_label = QLabel(_('<b>Add fetched annotations to<b>'))
        self.cfg_annotations_destination_label.setAlignment(Qt.AlignLeft)
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_destination_label, current_row, 0)
        current_row += 1

        self.cfg_annotations_destination_comboBox = QComboBox(self.cfg_annotation_options_gb)
        self.cfg_annotations_destination_comboBox.setObjectName('cfg_annotations_destination_comboBox')
        self.cfg_annotations_destination_comboBox.setToolTip(_('Custom field to store annotations'))
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_destination_comboBox, current_row, 0)

        # Populate annotations_field combobox
        db = self.gui.current_db
        all_custom_fields = db.custom_field_keys()
        self.custom_fields = {}
        for custom_field in all_custom_fields:
            field_md = db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['comments']:
                self.custom_fields[field_md['name']] = {'field': custom_field,
                                                   'datatype': field_md['datatype']}

        all_fields = list(self.custom_fields.keys()) + ['Comments']
        for cf in sorted(all_fields):
            self.cfg_annotations_destination_comboBox.addItem(cf)

        # Add CC Wizard
        self.cfg_annotations_wizard = QToolButton()
        self.cfg_annotations_wizard.setIcon(QIcon(I('wizard.png')))
        self.cfg_annotations_wizard.setToolTip(_("Create a custom column to store annotations"))
        self.cfg_annotations_wizard.clicked.connect(partial(self.launch_cc_wizard, 'Annotations'))
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_wizard, current_row, 2)

        current_row += 1

        # ~~~~~~~~ Add a horizontal line ~~~~~~~~
        self.cfg_appearance_hl = QFrame(self)
        self.cfg_appearance_hl.setGeometry(QRect(0, 0, 1, 3))
        self.cfg_appearance_hl.setFrameShape(QFrame.HLine)
        self.cfg_appearance_hl.setFrameShadow(QFrame.Raised)
        self.cfg_annotation_options_qgl.addWidget(self.cfg_appearance_hl, current_row, 0)
        current_row += 1

        # ~~~~~~~~ Add the Modify… button ~~~~~~~~
        self.cfg_annotations_appearance_pushbutton = QPushButton(_("Modify appearance…"))
        self.cfg_annotations_appearance_pushbutton.clicked.connect(self.configure_appearance)
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_appearance_pushbutton, current_row, 0)
        current_row += 1

        self.spacerItem = QtGui.QSpacerItem(20, 40, qSizePolicy_Minimum, qSizePolicy_Expanding)
        self.cfg_annotation_options_qgl.addItem(self.spacerItem, current_row, 0, 1, 1)

        # ~~~~~~~~ Compilations group box ~~~~~~~~
        self.cfg_compilation_options_gb = QGroupBox(self)
        self.cfg_compilation_options_gb.setTitle(_('Compilations'))
        self.l.addWidget(self.cfg_compilation_options_gb)
        self.cfg_compilation_options_qgl = QGridLayout(self.cfg_compilation_options_gb)
        current_row = 0

        #   News clippings
        self.cfg_news_clippings_checkbox = QCheckBox(_('Collect News clippings'))
        self.cfg_news_clippings_checkbox.setObjectName('cfg_news_clippings_checkbox')
        self.cfg_compilation_options_qgl.addWidget(self.cfg_news_clippings_checkbox,
            current_row, 0)

        self.cfg_news_clippings_lineEdit = QLineEdit()
        self.cfg_news_clippings_lineEdit.setObjectName('cfg_news_clippings_lineEdit')
        self.cfg_news_clippings_lineEdit.setToolTip(_('Title for collected news clippings'))
        self.cfg_compilation_options_qgl.addWidget(self.cfg_news_clippings_lineEdit,
            current_row, 1)

        # ~~~~~~~~ End of construction zone ~~~~~~~~

        self.resize(self.sizeHint())

        # Restore state of controls, populate annotations combobox
        self.controls = inventory_controls(self, dump_controls=False)
        restore_state(self)
        self.populate_annotations()

        # Hook changes to annotations_destination_combobox
#        self.connect(self.cfg_annotations_destination_comboBox,
#                     pyqtSignal('currentIndexChanged(const QString &)'),
#                     self.annotations_destination_changed)
        self.cfg_annotations_destination_comboBox.currentIndexChanged.connect(self.annotations_destination_changed)

        # Hook changes to diagnostic checkboxes
        self.cfg_disable_caching_checkbox.stateChanged.connect(self.restart_required)
        self.cfg_libimobiledevice_debug_log_checkbox.stateChanged.connect(self.restart_required)
        self.cfg_plugin_debug_log_checkbox.stateChanged.connect(self.restart_required)

        # Hook changes to News clippings, initialize
        self.cfg_news_clippings_checkbox.stateChanged.connect(self.news_clippings_toggled)
        self.news_clippings_toggled(self.cfg_news_clippings_checkbox.checkState())
        self.cfg_news_clippings_lineEdit.editingFinished.connect(self.news_clippings_destination_changed)

        # Launch the annotated_books_scanner
        field = get_cc_mapping('annotations', 'field', 'Comments')
        self.annotated_books_scanner = InventoryAnnotatedBooks(self.gui, field)
        self.annotated_books_scanner.signal.connect(self.inventory_complete)
#        self.connect(self.annotated_books_scanner, self.annotated_books_scanner.signal,
#            self.inventory_complete)
        QTimer.singleShot(1, self.start_inventory)

    def annotations_destination_changed(self, qs_new_destination_name):
        '''
        If the destination field changes, move all existing annotations from old to new
        '''
        self._log_location(repr(qs_new_destination_name))
        self._log("self.custom_fields: %s" % self.custom_fields)

        old_destination_field = get_cc_mapping('annotations', 'field', None)
        if old_destination_field and not (old_destination_field in self.gui.current_db.custom_field_keys() or old_destination_field == 'Comments'):
            return
        old_destination_name = get_cc_mapping('annotations', 'combobox', None)

        self._log("old_destination_field: %s" % old_destination_field)
        self._log("old_destination_name: %s" % old_destination_name)

        # Catch initial change from None to Comments - first run only
        if old_destination_field is None:
            return

#        new_destination_name = unicode(qs_new_destination_name)
        new_destination_name = unicode(self.cfg_annotations_destination_comboBox.currentText())
        self._log("new_destination_name: %s" % new_destination_name)

        if old_destination_name == new_destination_name:
            self._log_location("old_destination_name = new_destination_name, no changes")
            return

        new_destination_field = None
        if new_destination_name == 'Comments':
            new_destination_field = 'Comments'
        else:
            new_destination_field = self.custom_fields[new_destination_name]['field']

        if existing_annotations(self.opts.parent, old_destination_field):
            command = self.launch_new_destination_dialog(old_destination_name, new_destination_name)

            if command == 'move':
                set_cc_mapping('annotations', field=new_destination_field, combobox=new_destination_name)

                if self.annotated_books_scanner.isRunning():
                    self.annotated_books_scanner.wait()
                move_annotations(self, self.annotated_books_scanner.annotation_map,
                    old_destination_field, new_destination_field)

            elif command == 'change':
                # Keep the updated destination field, but don't move annotations
                pass

            elif command == 'cancel':
                # Restore previous destination
                self.cfg_annotations_destination_comboBox.blockSignals(True)
                old_index = self.cfg_annotations_destination_comboBox.findText(old_destination_name)
                self.cfg_annotations_destination_comboBox.setCurrentIndex(old_index)
                self.cfg_annotations_destination_comboBox.blockSignals(False)

            """
            # Warn user that change will move existing annotations to new field
            title = 'Move annotations?'
            msg = ("<p>Existing annotations will be moved from <b>%s</b> to <b>%s</b>.</p>" %
                    (old_destination_name, new_destination_name) +
                   "<p>New annotations will be added to <b>%s</b>.</p>" %
                    new_destination_name +
                   "<p>Proceed?</p>")
            d = MessageBox(MessageBox.QUESTION,
                           title, msg,
                           show_copy_button=False)
            self._log_location("QUESTION: %s" % msg)
            if d.exec_():
                set_cc_mapping('annotations', field=new_destination_field, combobox=new_destination_name)

                if self.annotated_books_scanner.isRunning():
                    self.annotated_books_scanner.wait()
                move_annotations(self, self.annotated_books_scanner.annotation_map,
                    old_destination_field, new_destination_field)

            else:
                self.cfg_annotations_destination_comboBox.blockSignals(True)
                old_index = self.cfg_annotations_destination_comboBox.findText(old_destination_name)
                self.cfg_annotations_destination_comboBox.setCurrentIndex(old_index)
                self.cfg_annotations_destination_comboBox.blockSignals(False)
            """

        else:
            # No existing annotations, just update prefs
            set_cc_mapping('annotations', field=new_destination_field, combobox=new_destination_name)

    def configure_appearance(self):
        '''
        '''
        from calibre_plugins.annotations.appearance import default_elements
        from calibre_plugins.annotations.appearance import default_timestamp
        appearance_settings = {
                                'appearance_css': default_elements,
                                'appearance_hr_checkbox': False,
                                'appearance_timestamp_format': default_timestamp,
                                'appearance_highlight_bg': 'transparent',
                                'appearance_highlight_fg': '#000000'
        }

        # Save, hash the original settings
        original_settings = {}
        osh = hashlib.md5()
        for setting in appearance_settings:
            original_settings[setting] = plugin_prefs.get(setting, appearance_settings[setting])
            osh.update(repr(plugin_prefs.get(setting, appearance_settings[setting])).encode('utf-8'))

        # Display the appearance dialog
        aa = AnnotationsAppearance(self, get_icon('images/annotations.png'), plugin_prefs)
        cancelled = False
        if aa.exec_():
            # appearance_hr_checkbox and appearance_timestamp_format changed live to prefs during previews
            plugin_prefs.set('appearance_css', aa.elements_table.get_data())
            # Generate a new hash
            nsh = hashlib.md5()
            for setting in appearance_settings:
                nsh.update(repr(plugin_prefs.get(setting, appearance_settings[setting])).encode('utf-8'))
        else:
            for setting in appearance_settings:
                plugin_prefs.set(setting, original_settings[setting])
            nsh = osh

        # If there were changes, and there are existing annotations, offer to re-render
        field = get_cc_mapping('annotations', 'field', None)
        if osh.digest() != nsh.digest() and existing_annotations(self.opts.parent,field):
            title = _('Update annotations?')
            msg = _('<p>Update existing annotations to new appearance settings?</p>')
            d = MessageBox(MessageBox.QUESTION,
                           title, msg,
                           show_copy_button=False)
            self._log_location("QUESTION: %s" % msg)
            if d.exec_():
                self._log_location("Updating existing annotations to modified appearance")
                if self.annotated_books_scanner.isRunning():
                    self.annotated_books_scanner.wait()
                move_annotations(self, self.annotated_books_scanner.annotation_map,
                    field, field, window_title=_("Updating appearance"))

    def inventory_complete(self, msg):
        self._log_location(msg)

    def launch_cc_wizard(self, column_type):
        '''
        '''
        def _update_combo_box(comboBox, destination, previous):
            '''
            '''
            self._log_location()

            cb = getattr(self, comboBox)
            cb.blockSignals(True)
            all_items = [str(cb.itemText(i))
                         for i in range(cb.count())]
            if previous and previous in all_items:
                all_items.remove(previous)
            all_items.append(destination)

            cb.clear()
            cb.addItems(sorted(all_items, key=lambda s: s.lower()))

            # Select the new destination in the comboBox
            idx = cb.findText(destination)
            if idx > -1:
                cb.setCurrentIndex(idx)

            # Process the changed destination
            self.annotations_destination_changed(destination)

            cb.blockSignals(False)


        klass = os.path.join(dialog_resources_path, 'cc_wizard.py')
        if os.path.exists(klass):
            #self._log("importing CC Wizard dialog from '%s'" % klass)
            sys.path.insert(0, dialog_resources_path)
            this_dc = importlib.import_module('cc_wizard')
            sys.path.remove(dialog_resources_path)
            dlg = this_dc.CustomColumnWizard(self,
                                             column_type,
                                             self.WIZARD_PROFILES[column_type],
                                             verbose=True)
            dlg.exec_()

            if dlg.modified_column:
                self._log("modified_column: %s" % dlg.modified_column)

                destination = dlg.modified_column['destination']
                label = dlg.modified_column['label']
                previous = dlg.modified_column['previous']
                source = dlg.modified_column['source']

                self._log("destination: %s" % destination)
                self._log("label: %s" % label)
                self._log("previous: %s" % previous)
                self._log("source: %s" % source)

                if source == "Annotations":
                    # Add/update the new destination so save_settings() can find it
                    if destination in self.custom_fields:
                        self.custom_fields[destination]['field'] = label
                    else:
                        self.custom_fields[destination] = {'field': label}

                    _update_combo_box('cfg_annotations_destination_comboBox', destination, previous)

                    # Save field manually in case user cancels
                    #self.prefs.set('cfg_annotations_destination_comboBox', destination)
                    #self.prefs.set('cfg_annotations_destination_field', label)
                    set_cc_mapping('annotations', field=label, combobox=destination)

                    # Inform user to restart
                    self.restart_required('custom_column')

        else:
            self._log("ERROR: Can't import from '%s'" % klass)

    def launch_new_destination_dialog(self, old, new):
        '''
        Return 'move', 'change' or 'cancel'
        '''
        self._log_location()

        klass = os.path.join(dialog_resources_path, 'new_destination.py')
        if os.path.exists(klass):
            self._log("importing new destination dialog from '%s'" % klass)
            sys.path.insert(0, dialog_resources_path)
            this_dc = importlib.import_module('new_destination')
            sys.path.remove(dialog_resources_path)
            dlg = this_dc.NewDestinationDialog(self, old, new)
            dlg.exec_()
            return dlg.command

    def news_clippings_destination_changed(self):
        qs_new_destination_name = self.cfg_news_clippings_lineEdit.text()
        if not re.match(r'^\S+[A-Za-z0-9 ]+$', qs_new_destination_name):
            # Complain about News clippings title
            title = _('Invalid title for News clippings')
            msg = _("Supply a valid title for News clippings, for example 'My News Clippings'.")
            d = MessageBox(MessageBox.WARNING,
                           title, msg,
                           show_copy_button=False)
            self._log_location("WARNING: %s" % msg)
            d.exec_()

    def news_clippings_toggled(self, state):
        if state == Qt.Checked:
            self.cfg_news_clippings_lineEdit.setEnabled(True)
        else:
            self.cfg_news_clippings_lineEdit.setEnabled(False)

    def populate_annotations(self):
        '''
        Restore annotations combobox
        '''
        self._log_location()
        target = 'Comments'
        existing = get_cc_mapping('annotations', 'combobox')
        if existing:
            target = existing
        ci = self.cfg_annotations_destination_comboBox.findText(target)
        self.cfg_annotations_destination_comboBox.setCurrentIndex(ci)

    def restart_required(self, state):
        title = _('Restart required')
        msg = _('To apply changes, restart calibre.')
        d = MessageBox(MessageBox.WARNING,
                       title, msg,
                       show_copy_button=False)
        self._log_location("WARNING: %s" % (msg))
        d.exec_()

    def save_settings(self):
        save_state(self)

        # Save the annotation destination field
        ann_dest = unicode(self.cfg_annotations_destination_comboBox.currentText())
        self._log_location("INFO: ann_dest=%s" % (ann_dest))
        self._log_location("INFO: self.custom_fields=%s" % (self.custom_fields))
        if ann_dest == 'Comments':
            set_cc_mapping('annotations', field='Comments', combobox='Comments')
        elif ann_dest:
            set_cc_mapping('annotations', field=self.custom_fields[ann_dest]['field'], combobox=ann_dest)

    def start_inventory(self):
        self.annotated_books_scanner.start()

class InventoryAnnotatedBooks(QThread, Logger):

    signal = pyqtSignal(object)

    def __init__(self, gui, field, get_date_range=False):
        QThread.__init__(self, gui)
        self.annotation_map = []
        self.cdb = gui.current_db
        self.get_date_range = get_date_range
        self.newest_annotation = 0
        self.oldest_annotation = mktime(datetime.today().timetuple())
        self.field = field

    def run(self):
        self.find_all_annotated_books()
        if self.get_date_range:
            self.get_annotations_date_range()
        self.signal.emit("inventory complete: %d annotated books" % len(self.annotation_map))

    def find_all_annotated_books(self):
        '''
        Find all annotated books in library
        '''
        if not self.field:
            self._log_location()
            self._log("No custom column field specified, cannot find annotated books")
            return
        if not (self.field in self.cdb.custom_field_keys() or self.field == 'Comments'):
            self._log_location()
            self._log("No custom column field specified, cannot find annotated books")
            return

        id = self.cdb.FIELD_MAP['id']
        for record in self.cdb.data.iterall():
            mi = self.cdb.get_metadata(record[id], index_is_id=True)
            if self.field == 'Comments':
                if mi.comments:
                    soup = BeautifulSoup(mi.comments)
                else:
                    continue
            else:
                soup = BeautifulSoup(mi.get_user_metadata(self.field, False)['#value#'])

            if soup.find('div', 'user_annotations') is not None:
                self.annotation_map.append(mi.id)

    def get_annotations_date_range(self):
        '''
        Find oldest, newest annotation in annotated books
        initial values of self.oldest, self.newest are reversed to allow update comparisons
        if no annotations, restore to correct values
        '''
        annotations_found = False

        for cid in self.annotation_map:
            mi = self.cdb.get_metadata(cid, index_is_id=True)
            if self.field == 'Comments':
                soup = BeautifulSoup(mi.comments)
            else:
                soup = BeautifulSoup(mi.get_user_metadata(self.field, False)['#value#'])

            uas = soup.findAll('div', 'annotation')
            for ua in uas:
                try:
                    timestamp = float(ua.find('td', 'timestamp')['uts'])
                    if timestamp < self.oldest_annotation:
                        self.oldest_annotation = timestamp
                    if timestamp > self.newest_annotation:
                        self.newest_annotation = timestamp
                    annotations_found = True
                except:
                    continue

        if not annotations_found:
            temp = self.newest_annotation
            self.newest_annotation = self.oldest_annotation
            self.oldest_annotation = temp


# For testing ConfigWidget, run from command line:
# cd ~/Dropbox/calibre/plugins/Fetch_Annotations_2
# calibre-debug config.py
# Search 'Annotations'
if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    from calibre.gui2.preferences import test_widget
    app = QApplication([])
    test_widget('Advanced', 'Plugins')
