#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

# Windows: calibre-customize -a $plugin".zip"
# calibre-debug -e __init__.py

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

from datetime import datetime
from functools import partial
import hashlib, importlib, os, re, sys
from time import mktime

from PyQt4 import QtGui
from PyQt4.Qt import (Qt, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QGroupBox, QIcon, QLabel, QLineEdit, QPushButton, QRadioButton,
    QRect, QString, QThread, QTimer, QToolButton, QVBoxLayout, QWidget,
    SIGNAL)

from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.constants import islinux, iswindows
from calibre.devices.usbms.driver import debug_print
from calibre.utils.config import JSONConfig, config_dir
from calibre.utils.logging import Log

from calibre_plugins.annotations.appearance import AnnotationsAppearance
from calibre_plugins.annotations.common_utils import (Struct,
    existing_annotations, get_icon, inventory_controls, move_annotations, restore_state,
    save_state)

plugin_prefs = JSONConfig('plugins/annotations')

dialog_resources_path = os.path.join(config_dir, 'plugins', 'annotations_resources', 'dialogs')

class ConfigWidget(QWidget):
    LOCATION_TEMPLATE = "{cls}:{func}({arg1}) {arg2}"

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
        self.cfg_runtime_options_gb.setTitle('Runtime options')
        self.l.addWidget(self.cfg_runtime_options_gb)
        self.cfg_runtime_options_qvl = QVBoxLayout(self.cfg_runtime_options_gb)

        # ~~~~~~~~ Disable caching checkbox ~~~~~~~~
        self.cfg_disable_caching_checkbox = QCheckBox('Disable caching')
        self.cfg_disable_caching_checkbox.setObjectName('cfg_disable_caching_checkbox')
        self.cfg_disable_caching_checkbox.setToolTip('Force reload of reader database')
        self.cfg_disable_caching_checkbox.setChecked(False)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_disable_caching_checkbox)

        # ~~~~~~~~ plugin logging checkbox ~~~~~~~~
        self.cfg_plugin_debug_log_checkbox = QCheckBox('Enable debug logging for Annotations plugin')
        self.cfg_plugin_debug_log_checkbox.setObjectName('cfg_plugin_debug_log_checkbox')
        self.cfg_plugin_debug_log_checkbox.setToolTip('Print plugin diagnostic messages to console')
        self.cfg_plugin_debug_log_checkbox.setChecked(False)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_plugin_debug_log_checkbox)

        # ~~~~~~~~ libiMobileDevice logging checkbox ~~~~~~~~
        self.cfg_libimobiledevice_debug_log_checkbox = QCheckBox('Enable debug logging for libiMobileDevice')
        self.cfg_libimobiledevice_debug_log_checkbox.setObjectName('cfg_libimobiledevice_debug_log_checkbox')
        self.cfg_libimobiledevice_debug_log_checkbox.setToolTip('Print libiMobileDevice debug messages to console')
        self.cfg_libimobiledevice_debug_log_checkbox.setChecked(False)
        self.cfg_runtime_options_qvl.addWidget(self.cfg_libimobiledevice_debug_log_checkbox)

        # iExplorer stuff to remove
        '''
        # ~~~~~~~~ Create the iExplorer group box ~~~~~~~~
        if not islinux:
            self.cfg_ie_gb = QGroupBox(self)
            self.cfg_ie_gb.setTitle('iExplorer')
            self.cfg_runtime_options_qvl.addWidget(self.cfg_ie_gb)
            self.cfg_ie_gb_qgl = QGridLayout(self.cfg_ie_gb)
            current_row = 0

            ie_installed = iOSMounter(self.opts).app_path is not None
            # Path to iExplorer (Windows only)
            if iswindows:
                self.cfg_path_to_ie_lineEdit = QLineEdit(self)
                self.cfg_path_to_ie_lineEdit.setObjectName('cfg_path_to_ie_lineEdit')
                self.cfg_path_to_ie_lineEdit.setToolTip('Path to iExplorer')
                self.cfg_path_to_ie_lineEdit.setPlaceholderText('Select path to iExplorer')
                self.cfg_ie_gb_qgl.addWidget(self.cfg_path_to_ie_lineEdit, current_row, 0)

                self.cfg_choose_path_toolButton = QToolButton(self)
                self.cfg_choose_path_toolButton.setToolTip('Select location of iExplorer')
                self.cfg_choose_path_toolButton.setIcon(QIcon(I('mimetypes/dir')))
                self.cfg_choose_path_toolButton.clicked.connect(self.choose_win_iexplorer_path)
                self.cfg_ie_gb_qgl.addWidget(self.cfg_choose_path_toolButton, current_row, 1)
                current_row += 1

            self.cfg_disable_iexplorer_radioButton = QRadioButton('Disable', self)
            self.cfg_disable_iexplorer_radioButton.setObjectName('cfg_disable_iexplorer_radioButton')
            self.cfg_disable_iexplorer_radioButton.setChecked(True)
            self.cfg_disable_iexplorer_radioButton.setEnabled(ie_installed)
            self.cfg_ie_gb_qgl.addWidget(self.cfg_disable_iexplorer_radioButton, current_row, 0)
            current_row += 1

            self.cfg_launch_with_calibre_radioButton = QRadioButton('Launch with calibre', self)
            self.cfg_launch_with_calibre_radioButton.setObjectName('cfg_launch_with_calibre_radioButton')
            self.cfg_ie_gb_qgl.addWidget(self.cfg_launch_with_calibre_radioButton, current_row, 0)
            self.cfg_launch_with_calibre_radioButton.setEnabled(ie_installed)
            current_row += 1

            self.cfg_launch_on_demand_radioButton = QRadioButton('Launch with plugin', self)
            self.cfg_launch_on_demand_radioButton.setObjectName('cfg_launch_on_demand_radioButton')
            self.cfg_launch_on_demand_radioButton.setEnabled(ie_installed)
            self.cfg_ie_gb_qgl.addWidget(self.cfg_launch_on_demand_radioButton, current_row, 0)
            current_row += 1

            self.ie_spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
            self.cfg_ie_gb_qgl.addItem(self.ie_spacerItem, current_row, 0)
        '''

        # ~~~~~~~~ Create the Annotations options group box ~~~~~~~~
        self.cfg_annotation_options_gb = QGroupBox(self)
        self.cfg_annotation_options_gb.setTitle('Annotation options')
        self.l.addWidget(self.cfg_annotation_options_gb)

        self.cfg_annotation_options_qgl = QGridLayout(self.cfg_annotation_options_gb)
        current_row = 0

        # Add the label/combobox for annotations destination
        self.cfg_annotations_destination_label = QLabel('<b>Add fetched annotations to<b>')
        self.cfg_annotations_destination_label.setAlignment(Qt.AlignLeft)
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_destination_label, current_row, 0)
        current_row += 1

        self.cfg_annotations_destination_comboBox = QComboBox(self.cfg_annotation_options_gb)
        self.cfg_annotations_destination_comboBox.setObjectName('cfg_annotations_destination_comboBox')
        self.cfg_annotations_destination_comboBox.setToolTip('custom field to store annotations')
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

        all_fields = self.custom_fields.keys() + ['Comments']
        for cf in sorted(all_fields):
            self.cfg_annotations_destination_comboBox.addItem(cf)

        # Add CC Wizard
        self.cfg_annotations_wizard = QToolButton()
        self.cfg_annotations_wizard.setIcon(QIcon(I('wizard.png')))
        self.cfg_annotations_wizard.setToolTip("Create a custom column to store annotations")
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
        self.cfg_annotations_appearance_pushbutton = QPushButton("Modify appearance…")
        self.cfg_annotations_appearance_pushbutton.clicked.connect(self.configure_appearance)
        self.cfg_annotation_options_qgl.addWidget(self.cfg_annotations_appearance_pushbutton, current_row, 0)
        current_row += 1

        self.spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.cfg_annotation_options_qgl.addItem(self.spacerItem, current_row, 0, 1, 1)

        # ~~~~~~~~ Compilations group box ~~~~~~~~
        self.cfg_compilation_options_gb = QGroupBox(self)
        self.cfg_compilation_options_gb.setTitle('Compilations')
        self.l.addWidget(self.cfg_compilation_options_gb)
        self.cfg_compilation_options_qgl = QGridLayout(self.cfg_compilation_options_gb)
        current_row = 0

        #   News clippings
        self.cfg_news_clippings_checkbox = QCheckBox('Collect News clippings')
        self.cfg_news_clippings_checkbox.setObjectName('cfg_news_clippings_checkbox')
        self.cfg_compilation_options_qgl.addWidget(self.cfg_news_clippings_checkbox,
            current_row, 0)

        self.cfg_news_clippings_lineEdit = QLineEdit()
        self.cfg_news_clippings_lineEdit.setObjectName('cfg_news_clippings_lineEdit')
        self.cfg_news_clippings_lineEdit.setToolTip('Title for collected news clippings')
        self.cfg_compilation_options_qgl.addWidget(self.cfg_news_clippings_lineEdit,
            current_row, 1)

        # ~~~~~~~~ End of construction zone ~~~~~~~~

        self.resize(self.sizeHint())

        # Restore state of controls
        self.controls = inventory_controls(self)
        restore_state(self, plugin_prefs)

        # Hook changes to annotations_destination_combobox
        #self.cfg_annotations_destination_comboBox.currentIndexChanged.connect(self.annotations_destination_changed)
        self.connect(self.cfg_annotations_destination_comboBox,
                     SIGNAL('currentIndexChanged(const QString &)'),
                     self.annotations_destination_changed)

        # Hook changes to diagnostic checkboxes
        self.cfg_disable_caching_checkbox.stateChanged.connect(self.restart_required)
        self.cfg_libimobiledevice_debug_log_checkbox.stateChanged.connect(self.restart_required)
        self.cfg_plugin_debug_log_checkbox.stateChanged.connect(self.restart_required)

        # First run: if no destination field selected, default to 'Comments'
        if self.cfg_annotations_destination_comboBox.currentText() == QString(u''):
            ci = self.cfg_annotations_destination_comboBox.findText('Comments')
            self.cfg_annotations_destination_comboBox.setCurrentIndex(ci)

        # Hook changes to News clippings, initialize
        self.cfg_news_clippings_checkbox.stateChanged.connect(self.news_clippings_toggled)
        self.news_clippings_toggled(self.cfg_news_clippings_checkbox.checkState())
        self.cfg_news_clippings_lineEdit.editingFinished.connect(self.news_clippings_destination_changed)

        # Launch the annotated_books_scanner
        field = plugin_prefs.get('cfg_annotations_destination_field', None)
        self.annotated_books_scanner = InventoryAnnotatedBooks(self.gui, field)
        self.connect(self.annotated_books_scanner, self.annotated_books_scanner.signal,
            self.inventory_complete)
        QTimer.singleShot(1, self.start_inventory)

    def annotations_destination_changed(self, qs_new_destination_name):
        '''
        If the destination field changes, move all existing annotations from old to new
        '''
        old_destination_field = plugin_prefs.get("cfg_annotations_destination_field", None)
        old_destination_name = plugin_prefs.get("cfg_annotations_destination_comboBox", None)

        # Catch initial change from None to Comments - first run only
        if old_destination_field == None:
            return

        new_destination_name = str(qs_new_destination_name)
        if old_destination_name == new_destination_name:
            self._log_location("old_destination_name = new_destination_name, no changes")
            return

        new_destination_field = None
        if new_destination_name == 'Comments':
            new_destination_field = 'Comments'
        else:
            new_destination_field = self.custom_fields[new_destination_name]['field']

        if existing_annotations(self.opts.parent, old_destination_field):
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
                plugin_prefs.set('cfg_annotations_destination_field', new_destination_field)
                plugin_prefs.set('cfg_annotations_destination_comboBox', new_destination_name)

                if self.annotated_books_scanner.isRunning():
                    self.annotated_books_scanner.wait()
                move_annotations(self, self.annotated_books_scanner.annotation_map,
                    old_destination_field, new_destination_field)

            else:
                self.cfg_annotations_destination_comboBox.blockSignals(True)
                old_index = self.cfg_annotations_destination_comboBox.findText(old_destination_name)
                self.cfg_annotations_destination_comboBox.setCurrentIndex(old_index)
                self.cfg_annotations_destination_comboBox.blockSignals(False)
        else:
            # No existing annotations, just update prefs
            plugin_prefs.set('cfg_annotations_destination_field', new_destination_field)
            plugin_prefs.set('cfg_annotations_destination_comboBox', new_destination_name)

    def configure_appearance(self):
        '''
        '''
        from calibre_plugins.annotations.appearance import default_elements
        from calibre_plugins.annotations.appearance import default_timestamp
        appearance_settings = {
                                'appearance_css': default_elements,
                                'appearance_hr_checkbox': False,
                                'appearance_timestamp_format': default_timestamp
                              }

        # Save, hash the original settings
        original_settings = {}
        osh = hashlib.md5()
        for setting in appearance_settings:
            original_settings[setting] = plugin_prefs.get(setting, appearance_settings[setting])
            osh.update(repr(plugin_prefs.get(setting, appearance_settings[setting])))

        # Display the appearance dialog
        aa = AnnotationsAppearance(self, get_icon('images/annotations.png'), plugin_prefs)
        cancelled = False
        if aa.exec_():
            # appearance_hr_checkbox and appearance_timestamp_format changed live to prefs during previews
            plugin_prefs.set('appearance_css', aa.elements_table.get_data())
            # Generate a new hash
            nsh = hashlib.md5()
            for setting in appearance_settings:
                nsh.update(repr(plugin_prefs.get(setting, appearance_settings[setting])))
        else:
            for setting in appearance_settings:
                plugin_prefs.set(setting, original_settings[setting])
            nsh = osh

        # If there were changes, and there are existing annotations, offer to re-render
        field = plugin_prefs.get("cfg_annotations_destination_field", None)
        if osh.digest() != nsh.digest() and existing_annotations(self.opts.parent,field):
            title = 'Update annotations?'
            msg = '<p>Update existing annotations to new appearance settings?</p>'
            d = MessageBox(MessageBox.QUESTION,
                           title, msg,
                           show_copy_button=False)
            self._log_location("QUESTION: %s" % msg)
            if d.exec_():
                self.opts.log_location("Updating existing annotations to modified appearance")
                if self.annotated_books_scanner.isRunning():
                    self.annotated_books_scanner.wait()
                move_annotations(self, self.annotated_books_scanner.annotation_map,
                    field, field, window_title="Updating appearance")

    def inventory_complete(self, msg):
        self._log_location(msg)

    def launch_cc_wizard(self, column_type):
        '''
        '''
        def _update_combo_box(comboBox, destination, previous):
            '''
            '''
            cb = getattr(self, comboBox)

            all_items = [str(cb.itemText(i))
                         for i in range(cb.count())]
            if previous and previous in all_items:
                all_items.remove(previous)
            all_items.append(destination)

            cb.clear()
            cb.addItems(sorted(all_items, key=lambda s: s.lower()))
            idx = cb.findText(destination)
            if idx > -1:
                cb.setCurrentIndex(idx)

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

                if source == "Annotations":
                    # Add/update the new destination so save_settings() can find it
                    self.custom_fields[destination]['field'] = label

                    _update_combo_box("cfg_annotations_destination_comboBox", destination, previous)

                    # Save field manually in case user cancels
                    self.prefs.set('cfg_annotations_destination_comboBox', destination)
                    self.prefs.set('cfg_annotations_destination_field', label)

                    # Inform user to restart
                    self.restart_required('custom_column')

        else:
            self._log("ERROR: Can't import from '%s'" % klass)

    def news_clippings_destination_changed(self):
        qs_new_destination_name = self.cfg_news_clippings_lineEdit.text()
        if not re.match(r'^\S+[A-Za-z0-9 ]+$', qs_new_destination_name):
            # Complain about News clippings title
            title = 'Invalid title for News clippings'
            msg = "Supply a valid title for News clippings, for example 'My News Clippings'."
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

    def restart_required(self, state):
        title = 'Restart required'
        msg = 'To apply changes, restart calibre.'
        d = MessageBox(MessageBox.WARNING,
                       title, msg,
                       show_copy_button=False)
        self._log_location("WARNING: %s" % (msg))
        d.exec_()

    def save_settings(self):
        save_state(self, plugin_prefs)

        # Save the annotation destination field
        ann_dest = str(self.cfg_annotations_destination_comboBox.currentText())
        if ann_dest == 'Comments':
            plugin_prefs.set('cfg_annotations_destination_field', 'Comments')
        else:
            plugin_prefs.set('cfg_annotations_destination_field', self.custom_fields[ann_dest]['field'])

    def start_inventory(self):
        self.annotated_books_scanner.start()

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

class InventoryAnnotatedBooks(QThread):

    def __init__(self, gui, field, get_date_range=False):
        QThread.__init__(self, gui)
        self.annotation_map = []
        self.cdb = gui.current_db
        self.get_date_range = get_date_range
        self.newest_annotation = 0
        self.oldest_annotation = mktime(datetime.today().timetuple())
        self.field = field
        self.signal = SIGNAL("inventory_complete")

    def run(self):
        self.find_all_annotated_books()
        if self.get_date_range:
            self.get_annotations_date_range()
        self.emit(self.signal, "inventory complete: %d annotated books" % len(self.annotation_map))

    def find_all_annotated_books(self):
        '''
        Find all annotated books in library
        '''
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
                annotations_found = True
                timestamp = float(ua.find('td', 'timestamp')['uts'])
                if timestamp < self.oldest_annotation:
                    self.oldest_annotation = timestamp
                if timestamp > self.newest_annotation:
                    self.newest_annotation = timestamp

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
