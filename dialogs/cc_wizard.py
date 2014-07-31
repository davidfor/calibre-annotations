#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'

import sys

from calibre.devices.usbms.driver import debug_print
from calibre.gui2 import warning_dialog

from calibre_plugins.annotations.common_utils import Logger
from calibre_plugins.annotations.config import dialog_resources_path

try:
    from PyQt5.Qt import (QDialog, QDialogButtonBox, QIcon, QPixmap,
                          QSize)
except ImportError:
    from PyQt4.Qt import (QDialog, QDialogButtonBox, QIcon, QPixmap,
                          QSize)

# Import Ui_Form from form generated dynamically during initialization
if True:
    sys.path.insert(0, dialog_resources_path)
    from cc_wizard_ui import Ui_Dialog
    sys.path.remove(dialog_resources_path)


class CustomColumnWizard(QDialog, Ui_Dialog, Logger):

    STEP_ONE = "Name your '{0}' column:"

    YELLOW_BG = '<font style="background:#FDFF99">{0}</font>'

    def __init__(self, parent, column_type, profile, verbose=True):
        QDialog.__init__(self, parent.gui)
        self.column_type = column_type
        self.db = parent.gui.current_db
        self.gui = parent.gui
        self.modified_column = None
        self.previous_name = None
        self.profile = profile

        self.setupUi(self)
        self.verbose = verbose
        self._log_location()

        # Populate the icon
        self.icon.setText('')
        self.icon.setMaximumSize(QSize(40, 40))
        self.icon.setScaledContents(True)
        self.icon.setPixmap(QPixmap(I('wizard.png')))

        # Add the Accept button
        self.accept_button = self.bb.addButton('Button', QDialogButtonBox.AcceptRole)
        self.accept_button.setDefault(True)

        # Hook the QLineEdit box
        self.calibre_destination_le.textChanged.connect(self.validate_destination)

        self.populate_editor()

        self.highlight_step(1)

        # Hook the button events
        self.bb.clicked.connect(self.dispatch_button_click)

    def accept(self):
        self._log_location()
        super(CustomColumnWizard, self).accept()

    def close(self):
        self._log_location()
        super(CustomColumnWizard, self).close()

    def custom_column_add(self, requested_name, profile):
        '''
        Add the requested custom column with profile
        '''
        self._log_location(requested_name)
        self._log(profile)
        self.db.create_custom_column(profile['label'],
                                     requested_name,
                                     profile['datatype'],
                                     profile['is_multiple'],
                                     display=profile['display'])
        self.modified_column = {
            'destination': requested_name,
            'label': "#%s" % profile['label'],
            'previous': self.previous_name,
            'source': profile['source']
        }

    def custom_column_rename(self, requested_name, profile):
        '''
        The name already exists for label, update it
        '''
        self._log_location(requested_name)
        self._log(profile)

        # Find the existing
        for cf in self.db.custom_field_keys():
            #self._log(self.db.metadata_for_field(cf))
            mi = self.db.metadata_for_field(cf)
            if mi['label'] == profile['label']:
                self.db.set_custom_column_metadata(mi['colnum'],
                                                   name=requested_name,
                                                   label=mi['label'],
                                                   display=mi['display'])
                self.modified_column = {
                    'destination': requested_name,
                    'label': "#%s" % profile['label'],
                    'previous': self.previous_name,
                    'source': profile['source']
                }
                break

    def dispatch_button_click(self, button):
        '''
        BUTTON_ROLES = ['AcceptRole', 'RejectRole', 'DestructiveRole', 'ActionRole',
                        'HelpRole', 'YesRole', 'NoRole', 'ApplyRole', 'ResetRole']
        '''
        self._log_location()
        if self.bb.buttonRole(button) == QDialogButtonBox.AcceptRole:
            requested_name = str(self.calibre_destination_le.text())

            if requested_name in self.get_custom_column_names():
                self._log("'%s' already in use" % requested_name)
                warning_dialog(self.gui,
                               "Already in use",
                               "<p>'%s' is an existing custom column.</p><p>Pick a different name.</p>" % requested_name,
                               show=True, show_copy_button=False)

                self.calibre_destination_le.selectAll()
                self.calibre_destination_le.setFocus()

            else:
                source = self.column_type
                #profile = self.FIELDS[source]
                self.profile['source'] = source
                if button.objectName() == 'add_button':
                    self.custom_column_add(requested_name, self.profile)

                elif button.objectName() == 'rename_button':
                    self.custom_column_rename(requested_name, self.profile)
                self.accept()

        elif self.bb.buttonRole(button) == QDialogButtonBox.RejectRole:
            self.close()

    def esc(self, *args):
        self.close()

    def highlight_step(self, step):
        '''
        '''
        self._log_location(step)
        if step == 1:
            #self.step_1.setText(self.YELLOW_BG.format(self.STEP_ONE.format(self.column_type)))
            self.step_1.setText(self.STEP_ONE.format(self.column_type))

    def get_custom_column_names(self):
        '''
        '''
        self._log_location()
        existing_custom_names = []
        for cf in self.db.custom_field_keys():
            #self._log(self.db.metadata_for_field(cf))
            existing_custom_names.append(self.db.metadata_for_field(cf)['name'])
        return existing_custom_names

    def reset_accept_button(self, action="add_button", enabled=False):
        '''
        '''
        self.accept_button.setObjectName(action)
        if action == "add_button":
            self.accept_button.setText('Add custom column')
            self.accept_button.setIcon(QIcon(I('plus.png')))
        elif action == "rename_button":
            self.accept_button.setText("Rename custom column")
            self.accept_button.setIcon(QIcon(I('edit_input.png')))
        self.accept_button.setEnabled(enabled)

    def populate_editor(self):
        '''
        '''
        self._log_location()

        selected = self.column_type
        existing = None
        #label = self.FIELDS[selected]['label']
        label = self.profile['label']
        for cf in self.db.custom_field_keys():
            #self._log(self.db.metadata_for_field(cf))
            cfd = self.db.metadata_for_field(cf)
            if cfd['label'] == label:
                existing = cfd['name']
                break

        # Does label already exist?
        if existing:
            self.previous_name = existing
            self.calibre_destination_le.setText(existing)
            self.reset_accept_button(action="rename_button", enabled=True)
        else:
            # Populate the edit box with the default Column name
            self.calibre_destination_le.setText(selected)
            self.reset_accept_button(action="add_button", enabled=True)

        # Select the text
        self.calibre_destination_le.selectAll()
        self.calibre_destination_le.setFocus()

    def validate_destination(self, destination):
        '''
        Confirm length of column name > 0
        '''
        enabled = len(str(destination))
        self.accept_button.setEnabled(enabled)
