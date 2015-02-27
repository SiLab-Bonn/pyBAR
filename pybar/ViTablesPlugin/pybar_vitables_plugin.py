# -*- coding: utf-8 -*-
#!/usr/bin/env python
#       Author:  David-Leon Pohl - david-leon.pohl@rub.de

"""Plugin that provides plotting of data from the Python Bonn Atlas Readout System (pyBAR).
"""

__docformat__ = 'restructuredtext'
__version__ = '1.0'
plugin_class = 'PyBAR'

import numpy as np

import os
from PyQt4 import QtCore
from PyQt4 import QtGui
import vitables.utils
from vitables.vtSite import PLUGINSDIR

from host.analysis.plotting import plotting

translate = QtGui.QApplication.translate


class PyBar(QtCore.QObject):
    """Plots the selected pyBAR data with pyBAR functions via Matplotlib
    """
    def __init__(self):
        """The class constructor.
        """
        super(PyBar, self).__init__()

        # Get a reference to the application instance
        self.vtapp = vitables.utils.getVTApp()
        if self.vtapp is None:
            return

        self.vtgui = self.vtapp.gui

        # Add an entry under the Dataset menu
        self.addEntry()

        # Connect signals to slots
        self.vtgui.dataset_menu.aboutToShow.connect(self.updateDatasetMenu)

    def addEntry(self):
        """Add the `Plot pyBAR data`. entry to `Dataset` menu.
        """
        export_icon = QtGui.QIcon()
        pixmap = QtGui.QPixmap(os.path.join(PLUGINSDIR, \
            'csv/icons/document-export.png'))
        export_icon.addPixmap(pixmap, QtGui.QIcon.Normal, QtGui.QIcon.On)

        self.plot_action = QtGui.QAction(
            translate('PlotpyBARdata',
                "Plot data with pyBAR...",
                "Plot data with pyBAR..."),
            self,
            shortcut=QtGui.QKeySequence.UnknownKey, triggered=self.plot,
            icon=export_icon,
            statusTip=translate('PlotpyBARdata',
                "Plotting of selected data with pyBAR",
                "Status bar text for the Dataset -> Plot pyBAR data... action"))

        # Add the action to the Dataset menu
        menu = self.vtgui.dataset_menu
        menu.addSeparator()
        menu.addAction(self.plot_action)

        # Add the action to the leaf context menu
        cmenu = self.vtgui.leaf_node_cm
        cmenu.addSeparator()
        cmenu.addAction(self.plot_action)

    def updateDatasetMenu(self):
        """Update the `export` QAction when the Dataset menu is pulled down.

        This method is a slot. See class ctor for details.
        """
        enabled = True
        current = self.vtgui.dbs_tree_view.currentIndex()
        if current:
            leaf = self.vtgui.dbs_tree_model.nodeFromIndex(current)
            if leaf.node_kind in (u'group', u'root group'):
                enabled = False

        self.plot_action.setEnabled(enabled)

    def plot(self):
        """Export a given dataset to a `CSV` file.

        This method is a slot connected to the `export` QAction. See the
        :meth:`addEntry` method for details.
        """
        # The PyTables node tied to the current leaf of the databases tree
        current = self.vtgui.dbs_tree_view.currentIndex()
        leaf = self.vtgui.dbs_tree_model.nodeFromIndex(current).node

        data_name = leaf.name

        if data_name == 'HistErrorCounter':
            plotting.plot_event_errors(leaf)
        elif data_name == 'HistTot':
            plotting.plot_tot(leaf)
        elif data_name == 'HistRelBcid':
            plotting.plot_relative_bcid(leaf)
        elif data_name == 'HistOcc':
            plotting.plot_fancy_occupancy(hist=leaf)
        elif data_name == 'HistThreshold':
            plotting.plotThreeWay(hist=leaf[:, :], title='Threshold', filename=None, label="threshold [PlsrDAC]", minimum=0, bins=100)
        elif data_name == 'HistNoise':
            plotting.plotThreeWay(hist=leaf[:, :], title='Noise', filename=None, label="noise [PlsrDAC]", minimum=0, maximum=int(np.median(leaf) * 2), bins=100)
        elif data_name == 'HistTriggerErrorCounter':
            plotting.plot_trigger_errors(leaf)
        elif data_name == 'HistServiceRecord':
            plotting.plot_service_records(leaf)
        elif data_name == 'HistClusterTot':
            plotting.plot_cluster_tot(hist=leaf)
        elif data_name == 'HistClusterSize':
            plotting.plot_cluster_size(hist=leaf)
        else:
            print 'unknown data - %s: do not plot' % data_name

    def helpAbout(self):
        """Brief description of the plugin.
        """

        # Text to be displayed
        about_text = translate('pyBAR',
            """<qt>
            <p>Data plotting plug-in for pyBAR.
            </qt>""",
            'About')

        descr = dict(module_name='pyBAR',
            folder=PLUGINSDIR,
            version=__version__,
            plugin_name='pyBAR',
            author='David-Leon Pohl <david-leon.pohl@rub.de>, Jens Janssen <janssen@physik.uni-bonn.de>',
            descr=about_text)

        return descr
