# -*- coding: utf-8 -*-
#!/usr/bin/env python
#       Author:  David-Leon Pohl - david-leon.pohl@rub.de

"""Plugin that provides plotting of data from the Python Bonn Atlas Readout System (pyBAR).
"""

import numpy as np
import os
from PyQt4 import QtCore
from PyQt4 import QtGui
import vitables.utils
from vitables.vtSite import PLUGINSDIR

try:
    from matplotlib import colors, cm
    import matplotlib.pyplot as plt
    from mpl_toolkits.axes_grid1 import make_axes_locatable
except:
    print 'ERROR: Cannot load additional libraries needed for the pyBAR ViTables plugin!'
    raise

__docformat__ = 'restructuredtext'
__version__ = '1.0'
plugin_class = 'pyBarPlugin'

translate = QtGui.QApplication.translate


def plot_1d_hist(hist, yerr=None, title=None, x_axis_title=None, y_axis_title=None, x_ticks=None, color='r', plot_range=None, log_y=False, filename=None):
    plt.clf()
    hist = np.array(hist)
    if plot_range is None:
        plot_range = range(0, len(hist))
    plot_range = np.array(plot_range)
    plot_range = plot_range[plot_range < len(hist)]
    if yerr is not None:
        plt.bar(x=plot_range, height=hist[plot_range], color=color, align='center', yerr=yerr)
    else:
        plt.bar(x=plot_range, height=hist[plot_range], color=color, align='center')
    plt.xlim((min(plot_range) - 0.5, max(plot_range) + 0.5))
    plt.title(title)
    if x_axis_title is not None:
        plt.xlabel(x_axis_title)
    if y_axis_title is not None:
        plt.ylabel(y_axis_title)
    if x_ticks is not None:
        plt.xticks(plot_range, x_ticks)
        plt.tick_params(which='both', labelsize=8)
    if np.allclose(hist, 0.0):
        plt.ylim((0, 1))
    else:
        if log_y:
            plt.yscale('log')
    plt.grid(True)
    plt.show()


def plot_2d_hist(hist, title, z_max=None):
    if z_max == 'median':
        median = np.ma.median(hist)
        z_max = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif z_max == 'maximum' or z_max is None:
        maximum = np.ma.max(hist)
        z_max = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1

    plt.clf()
    xedges = [1, hist.shape[0]]
    yedges = [1, hist.shape[1]]

    extent = [yedges[0] - 0.5, yedges[-1] + 0.5, xedges[-1] + 0.5, xedges[0] - 0.5]
#     extent = [0.5, 80.5, 336.5, 0.5]
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    colors.BoundaryNorm(bounds, cmap.N)
    norm = colors.LogNorm()

    im = plt.imshow(hist, interpolation='nearest', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    plt.ylim((336.5, 0.5))
    plt.xlim((0.5, 80.5))
    plt.title(title + ' (%d entrie(s))' % (0 if hist.all() is np.ma.masked else np.ma.sum(hist)))
    plt.xlabel('Column')
    plt.ylabel('Row')

    ax = plt.gca()

    divider = make_axes_locatable(ax)

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
    cb.set_label("#")
    plt.show()


def plot_table(data, title):
    plt.clf()
    plt.title(title)
    x_name = data.dtype.names[0]
    if len(data.dtype.names) == 1:  # one column table, plot value against index
        plt.xlabel('Index')
        plt.ylabel(x_name)
        plt.plot(np.arange(data[x_name].shape[0]), data[x_name])
    elif len(data.dtype.names) == 2:  # two column table, plot column two against column 1
        y_name = data.dtype.names[1]
        plt.plot(data[x_name], data[y_name])
        plt.xlabel(x_name)
        plt.ylabel(y_name)
    elif len(data.dtype.names) == 3:  # three column table, plot column two against column 1 with column 3 error bars
        y_name = data.dtype.names[1]
        plt.xlabel(x_name)
        plt.ylabel(y_name)
        plt.errorbar(data[x_name], data[y_name], yerr=data[data.dtype.names[2]])

    plt.grid(True)
    plt.show()


class pyBarPlugin(QtCore.QObject):

    """Plots the selected pyBAR data with pyBAR functions via Matplotlib
    """

    def __init__(self):
        """The class constructor.
        """
        super(pyBarPlugin, self).__init__()

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
        pixmap = QtGui.QPixmap(os.path.join(PLUGINSDIR,
                                            'csv/icons/document-export.png'))
        export_icon.addPixmap(pixmap, QtGui.QIcon.Normal, QtGui.QIcon.On)

        self.plot_action = QtGui.QAction(
            translate('PlotpyBARdata',
                      "Plot data with pyBAR plugin",
                      "Plot data with pyBAR plugin"),
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

        hists_1d = ['HistRelBcid', 'HistErrorCounter', 'HistTriggerErrorCounter', 'HistServiceRecord', 'HistTot', 'HistTdc', 'HistClusterTot', 'HistClusterSize']
        hists_2d = ['HistOcc', 'Enable', 'Imon', 'C_High', 'EnableDigInj', 'C_Low', 'FDAC', 'TDAC', 'HistTdcPixel', 'HistTotPixel', 'HistThreshold', 'HistNoise', 'HistThresholdFitted', 'HistNoiseFitted', 'HistThresholdFittedCalib', 'HistNoiseFittedCalib']

        if data_name in hists_1d:
            plot_1d_hist(hist=leaf[:], title=data_name)
        elif data_name in hists_2d:
            if data_name == 'HistOcc':
                leaf = np.sum(leaf[:], axis=2)
            plot_2d_hist(hist=leaf[:], title=data_name)
        elif 'Table' in str(type(leaf)) and len(leaf[:].dtype.names) <= 3:  # detect tables with less than 4 columns
            plot_table(leaf[:], title=data_name)
        elif data_name == 'HitOrCalibration':
            print 'Comming soon'
        else:
            print 'Plotting', data_name, '(%s) is not supported!' % type(leaf)

    def helpAbout(self):
        """Brief description of the plugin.
        """

        # Text to be displayed
        about_text = translate('pyBarPlugin',
                               """<qt>
            <p>Data plotting plug-in for pyBAR.
            </qt>""",
                               'About')

        descr = dict(module_name='pyBarPlugin',
                     folder=PLUGINSDIR,
                     version=__version__,
                     plugin_name='pyBarPlugin',
                     author='David-Leon Pohl <david-leon.pohl@rub.de>, Jens Janssen <janssen@physik.uni-bonn.de>',
                     descr=about_text)

        return descr
