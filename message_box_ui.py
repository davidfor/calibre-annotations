# -*- coding: utf-8 -*-

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

COVER_ICON_SIZE = 153

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName(_fromUtf8("Dialog"))
        Dialog.resize(497, 235)
        self.gridLayout = QtGui.QGridLayout(Dialog)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.icon_label = QtGui.QLabel(Dialog)
        self.icon_label.setMaximumSize(QtCore.QSize(COVER_ICON_SIZE, COVER_ICON_SIZE))
        self.icon_label.setText(_fromUtf8(""))
        self.icon_label.setPixmap(QtGui.QPixmap(_fromUtf8(I("dialog_warning.png"))))
        self.icon_label.setScaledContents(False)
        self.icon_label.setObjectName(_fromUtf8("icon_label"))
        self.gridLayout.addWidget(self.icon_label, 0, 0, 1, 1)
        self.msg = QtGui.QLabel(Dialog)
        self.msg.setText(_fromUtf8(""))
        self.msg.setWordWrap(True)
        self.msg.setOpenExternalLinks(True)
        self.msg.setObjectName(_fromUtf8("msg"))
        self.gridLayout.addWidget(self.msg, 0, 1, 1, 1)
        self.det_msg = QtGui.QPlainTextEdit(Dialog)
        self.det_msg.setReadOnly(True)
        self.det_msg.setObjectName(_fromUtf8("det_msg"))
        self.gridLayout.addWidget(self.det_msg, 1, 0, 1, 2)
        self.bb = QtGui.QDialogButtonBox(Dialog)
        self.bb.setOrientation(QtCore.Qt.Horizontal)
        self.bb.setStandardButtons(QtGui.QDialogButtonBox.Ok)
        self.bb.setObjectName(_fromUtf8("bb"))
        self.gridLayout.addWidget(self.bb, 3, 0, 1, 2)
        self.toggle_checkbox = QtGui.QCheckBox(Dialog)
        self.toggle_checkbox.setText(_fromUtf8(""))
        self.toggle_checkbox.setObjectName(_fromUtf8("toggle_checkbox"))
        self.gridLayout.addWidget(self.toggle_checkbox, 2, 0, 1, 2)

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(self.bb, QtCore.SIGNAL(_fromUtf8("accepted()")), Dialog.accept)
        QtCore.QObject.connect(self.bb, QtCore.SIGNAL(_fromUtf8("rejected()")), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(_("Dialog"))
