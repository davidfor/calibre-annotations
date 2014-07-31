#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Gregory Riker'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial

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
    from new_destination_ui import Ui_Dialog
    sys.path.remove(dialog_resources_path)


class NewDestinationDialog(QDialog, Ui_Dialog, Logger):

    def __init__(self, parent, old, new):
        QDialog.__init__(self, parent.gui)
        self.db = parent.gui.current_db
        self.gui = parent.gui

        self.setupUi(self)
        self._log_location()

        # Hook the button events
        self.bb.clicked.connect(partial(self.button_clicked, 'cancel'))
        self.move_button.clicked.connect(partial(self.button_clicked, 'move'))
        self.change_button.clicked.connect(partial(self.button_clicked, 'change'))

        # Customize the dialog text
        self.move_label.setText(str(self.move_label.text()).format(old=old, new=new))
        self.change_label.setText(str(self.change_label.text()).format(old=old, new=new))

        self.command = 'cancel'
        self.do_resize()

    def button_clicked(self, button):
        '''
        '''
        self._log_location(button)
        self.command = button
        self.close()

    def close(self):
        super(NewDestinationDialog, self).close()

    def do_resize(self):
        sz = self.sizeHint() + QSize(100, 0)
        sz.setWidth(min(450, sz.width()))
        sz.setHeight(min(280, sz.height()))
        self.resize(sz)

    def esc(self, *args):
        self.close()
