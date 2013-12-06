#!/usr/bin/env python
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Greg Riker <griker@hotmail.com>'
__docformat__ = 'restructuredtext en'

from calibre.customize import InterfaceActionBase

class AnnotationsPlugin(InterfaceActionBase):
    name                = 'Annotations'
    description         = 'Import annotations'
    supported_platforms = ['linux', 'osx', 'windows']
    author              = 'Greg Riker'
    version             = (1, 2, 904)
    minimum_calibre_version = (1, 0, 0)

    actual_plugin       = 'calibre_plugins.annotations.action:AnnotationsAction'

    def is_customizable(self):
        return True

    def config_widget(self):
        self.cw = None
        if self.actual_plugin_:
            from calibre_plugins.annotations.config import ConfigWidget
            self.cw = ConfigWidget(self.actual_plugin_)
        return self.cw

    def save_settings(self, config_widget):
        config_widget.save_settings()
        if self.actual_plugin_:
            self.actual_plugin_.rebuild_menus()

# For testing ConfigWidget, run from command line:
# calibre-debug __init__.py
if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    from calibre.gui2.preferences import test_widget
    app = QApplication([])
    test_widget('Advanced', 'Plugins')

