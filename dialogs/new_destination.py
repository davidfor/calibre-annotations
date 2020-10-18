#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Gregory Riker, 2014-2020 additions by David Forrester <davidfor@internode.on.net>'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial

from calibre.gui2 import warning_dialog

from calibre_plugins.annotations.common_utils import Logger
from calibre_plugins.annotations.config import dialog_resources_path

try:
    from PyQt5.Qt import (Qt, QDialog, QDialogButtonBox, QIcon, QPixmap, QGridLayout, QVBoxLayout,
                      QSize, QLabel, QPushButton, QFrame, QRect, QSizePolicy, QFont, QGroupBox)
except ImportError:
    from PyQt4.Qt import (Qt, QDialog, QDialogButtonBox, QIcon, QPixmap, QGridLayout, QVBoxLayout,
                      QSize, QLabel, QPushButton, QFrame, QRect, QSizePolicy, QFont, QGroupBox)

# Import Ui_Form from form generated dynamically during initialization
if True:
    sys.path.insert(0, dialog_resources_path)
#     from new_destination_ui import Ui_Dialog
    sys.path.remove(dialog_resources_path)


class NewDestinationDialog(QDialog, Logger):

    def __init__(self, parent, old, new):
        super(QDialog, self).__init__(parent.gui)
        self.db = parent.gui.current_db
        self.gui = parent.gui

        self._log_location()

        layout = QVBoxLayout()
        self.setLayout(layout)
        header = QLabel(_("Move annotations or change destination?"))
        header.setAlignment(Qt.AlignCenter)
        header_font = QFont()
        header_font.setPointSize(16)
        header.setFont(header_font)
        layout.addWidget(header)
        change_group = QGroupBox("", self)
        layout.addWidget(change_group)
        self.gl = QGridLayout()
        change_group.setLayout(self.gl)

        horizontal_line = QFrame(self)
        horizontal_line.setGeometry(QRect(0, 0, 1, 3))
        horizontal_line.setFrameShape(QFrame.HLine)
        horizontal_line.setFrameShadow(QFrame.Raised)
        self.gl.addWidget(horizontal_line, 1, 0, 1, 2)

        self.move_button = QPushButton(_("Move"))
        self.gl.addWidget(self.move_button, 3, 0, 1, 1)
        self.move_label = QLabel(_('<html><head/><body><p>&bull; Move existing annotations from <span style=" font-weight:600;">{old}</span> to <span style=" font-weight:600;">{new}</span>.<br/>&bull; Existing annotations will be removed from <span style=" font-weight:600;">{old}</span>.<br/>&bull; Newly imported annotations will be added to <span style=" font-weight:600;">{new}</span>.</p></body></html>'))
        self.move_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.gl.addWidget(self.move_label, 3, 1)
        self.gl.addWidget(horizontal_line, 4, 1)

        self.change_button = QPushButton(_("Change"))
        self.gl.addWidget(self.change_button, 5, 0, 1, 1)
        self.change_label = QLabel(_('<html><head/><body><p>&bull; Change annotations storage from <span style=" font-weight:600;">{old}</span> to <span style=" font-weight:600;">{new}</span>.<br/>&bull; Existing annotations will remain in <span style=" font-weight:600;">{old}</span>.<br/>&bull; Newly imported annotations will be added to <span style=" font-weight:600;">{new}</span>.</p></body></html>'))
        self.change_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.gl.addWidget(self.change_label, 5, 1, 1, 1)

        self.bb = QDialogButtonBox(QDialogButtonBox.Cancel)
        layout.addWidget(self.bb)
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
