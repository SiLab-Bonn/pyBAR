# -*- coding: utf-8 -*-
#!/usr/bin/env python
#       Author:  David-Leon Pohl - david-leon.pohl@cern.ch

"""Plugin that provides plotting of data from the Python Bonn Atlas Readout System (pyBAR).
"""

__docformat__ = 'restructuredtext'
__version__ = '0.1'
plugin_class = 'PyBar'

import os
import re

#from plotting import plotting
import matplotlib.pyplot as plt
from matplotlib import colors, cm, legend
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy.optimize import curve_fit
from math import sqrt

import tables
import numpy as np

from PyQt4 import QtCore
from PyQt4 import QtGui

import vitables.utils
from vitables.vtSite import PLUGINSDIR

translate = QtGui.QApplication.translate

def ceil_mod(number, mod):
    number = int(number)
    mod = int(mod)
    while True:
        if number%mod == 0:
            break
        number+=1
    #print number
    return number

def create_2d_pixel_hist(hist2d, title = None, x_axis_title = None, y_axis_title = None, z_max = None):
    H=np.empty(shape=(336,80),dtype=hist2d.dtype)
    H[:]=hist2d[:,:]
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot', 200)
    #ceil_number = np.max(hist2d) if z_max == None else z_max
    ceil_number = ceil_mod(H.max() if z_max == None else z_max, 10)
    #ceil_number = np.max(hist2d)
    bounds = range(0, ceil_number+1, ceil_number/10 if ceil_number > 0 else 1)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)
    ax = plt.subplot(311)
#     ax = plt.plot()
    divider = make_axes_locatable(ax)
#     ax = plt.plot()
    ax = plt.subplot(311)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    try:
        plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm, ticks = bounds, cax = cax)
    except:
        print 'create_2d_pixel_hist: error printing color bar'


def create_1d_hist(hist, title = None, x_axis_title = None, y_axis_title = None, bins = None, x_min = None, x_max = None):
    median = np.median(hist)
    mean = np.mean(a = hist)
    rms = 0
    for i in range(0, len(hist.ravel())):
        rms += (hist.ravel()[i]-mean)**2
    rms = sqrt(rms/len(hist.ravel()))
    
    if(x_min!=None):
        hist = hist[hist>=x_min]
    if(x_max!=None):
        hist = hist[hist<=x_max]
    
    hist,bins,_ = plt.hist(x = hist.ravel(), bins = 100 if bins == None else bins)   #rebin to 1 d hist
   
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)

    bin_centres = (bins[:-1] + bins[1:])/2
    amplitude = np.amax(hist)    

    def gauss(x, *p):
        A, mu, sigma = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2))
    
    p0 = np.array([amplitude, mean, rms])# p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
    ax = plt.subplot(312)
    try:
        coeff, _ = curve_fit(gauss, bin_centres, hist, p0=p0)
        hist_fit = gauss(bin_centres, *coeff)
        plt.plot(bin_centres, hist_fit, "r--", label='Gaus fit')
        chi2 = 0
        for i in range(0, len(hist)):
            chi2 += (hist[i] - gauss(bins[i], *coeff))**2
        textright = '$\mu=%.2f$\n$\sigma=%.2f$\n$\chi2=%.2f$'%(coeff[1], coeff[2], chi2)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.85, 0.9, textright, transform=ax.transAxes, fontsize=8,
        verticalalignment='top', bbox=props)
    except RuntimeError:
        print 'create_1d_hist: Fit failed, do not plot fit'
        
    plt.ylim([0, plt.ylim()[1]*1.05])
#     plt.xlim([np.amin(bins) if x_min == None else x_min, np.amax(bins) if x_max == None else x_max])  
    textleft = '$\mathrm{mean}=%.2f$\n$\mathrm{RMS}=%.2f$\n$\mathrm{median}=%.2f$'%(mean, rms, median)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.1, 0.9, textleft, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)

def create_pixel_scatter_plot(hist, title = None, x_axis_title = None, y_axis_title = None, y_min = None, y_max = None):
    scatter_y = np.empty(shape=(336*80),dtype=hist.dtype)
    scatter_y_mean = np.zeros(shape=(80),dtype=np.float32)
    for col in range(80):
        column_mean = 0
        for row in range(336):
            scatter_y[row + col*336] = hist[row,col]
            column_mean += hist[row,col]
        scatter_y_mean[col] = column_mean/336.
    plt.scatter(range(80*336),  scatter_y, marker='o', s = 0.8)
    p1, = plt.plot(range(336/2,80*336+336/2,336), scatter_y_mean, 'o')
    plt.plot(range(336/2,80*336+336/2,336), scatter_y_mean, linewidth=2.0)
    plt.legend([p1], ["column mean"], prop={'size':6})
    plt.xlim(0,26880)
    plt.ylim(1.1*min(scatter_y) if y_min == None else y_min ,1.1*max(scatter_y) if y_max == None else y_max)
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)

def plotThreeWay(hist, title, filename = None, label = "label not set", minimum = None, maximum = None, bins = None):   #the famous 3 way plot (enhanced)
    mean = np.mean(hist)
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    plt.subplot(311)
    create_2d_pixel_hist(hist, title = title, x_axis_title = "column", y_axis_title = "row", z_max = 2*mean if maximum == None else maximum)
    plt.subplot(312)
    create_1d_hist(hist, bins = bins, x_axis_title = label, y_axis_title = "#", x_min = minimum, x_max = maximum)
    plt.subplot(313)
    create_pixel_scatter_plot(hist, x_axis_title = "channel = row + column*336", y_axis_title = label, y_min = minimum, y_max = maximum)
    plt.tight_layout()

    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_relative_bcid(relative_bcid_hist, filename = None):
    plt.clf()
    plt.bar(range(0,16), relative_bcid_hist[:], color='r', align = 'center') #bug: https://github.com/matplotlib/matplotlib/issues/1882, log = True)
    plt.xlabel('relative BCID [25 ns]')
    plt.ylabel('#')
    plt.yscale('log')
    plt.title('Relative BCID (former LVL1ID)')
    plt.xlim((0, 16))
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_tot(tot_hist, filename = None):
    plt.clf()
    plt.bar(range(0,16), tot_hist[:], color='b', align = 'center')
    plt.xlim((0, 15))
    plt.xlabel('TOT [25 ns]')
    plt.ylabel('#')
    plt.title('Time over threshold distribution (TOT code)')
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_event_errors(error_hist, filename = None):
    plt.clf()
    plt.bar(range(0,len(error_hist[:])), error_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('')
    plt.ylabel('#')
    plt.title('Event errors')
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    plt.xticks(range(0,8), ('SR\noccured', 'No\ntrigger', 'LVL1ID\nnot const.', '#BCID\nwrong', 'unknown\nword', 'BCID\njump', 'trigger\nerror', 'truncated') )
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_trigger_errors(trigger_error_hist, filename = None):
    plt.clf()
    plt.bar(range(0,8), trigger_error_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('')
    plt.ylabel('#')
    plt.title('Trigger errors')
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    plt.xticks(range(0,8), ('increase\nerror', 'more than\none trg.', 'TLU\naccept', 'TLU\ntime out', 'not\nused', 'not\nused', 'not\nused', 'not\nused') )
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_service_records(service_record_hist, filename = None):
    plt.clf()
    plt.bar(range(0,32), service_record_hist[:], color='r', align = 'center', label="Error code")
    plt.xlim((0, 31))
    plt.xlabel('service record code')
    plt.ylabel('#')
    plt.title('Service records ('+str(sum(service_record_hist[:]))+' entries)')
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plotOccupancy(occupancy_hist, median = False, max_occ = None, filename = None):
    plt.clf()
    H = occupancy_hist
    extent = [0.5, 80.5, 336.5, 0.5]
    #     cmap = cm.get_cmap('copper_r')
    cmap = cm.get_cmap('PuBu', 10)
    if median:
        ceil_number = ceil_mod(np.median(H[H>0]*2) if max_occ == None else max_occ, 10)
    else:
        ceil_number = ceil_mod(H.max() if max_occ == None else max_occ, 10)
    #         ceil_number = ceil_mod(int(H.max()) if max_occ == None else max_occ, 255)
    
    if(ceil_number<10):
        ceil_number = 10
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    #     if (ceil_number<255):
    #         ceil_number = 255
    #     bounds = range(0, ceil_number+1, 255/ceil_number)
    #     norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Occupancy ('+str(sum(sum(H)))+' entries)')
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

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
                "Plot pyBAR data", 
                "Plot pyBAR data"), 
            self, 
            shortcut=QtGui.QKeySequence.UnknownKey, triggered=self.plot, 
            icon=export_icon, 
            statusTip=translate('PlotpyBARdata', 
                "Plots the selected data set from pyBAR", 
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
            plot_event_errors(leaf)
        elif data_name == 'HistTot':
            plot_tot(leaf)
        elif data_name=='HistRelBcid':
            plot_relative_bcid(leaf)
        elif data_name=='HistOcc':
            plotThreeWay(hist=leaf[:,:,0], title = 'Occupancy', filename = None, label = "occupancy", minimum = 0, bins = 100)
        elif data_name=='HistThreshold':
            plotThreeWay(hist=leaf[:,:], title = 'Threshold', filename = None, label = "threshold", minimum = 0, bins = 100)
        elif data_name=='HistNoise':
            plotThreeWay(hist=leaf[:,:], title = 'Noise', filename = None, label = "noise", minimum = 0, maximum = 10, bins = 100)
#             plotOccupancy(leaf[:,:,0],max_occ = 100)
        elif data_name=='HistTriggerErrorCounter':
            plot_trigger_errors(leaf)
        elif data_name=='HistServiceRecord':
            plot_service_records(leaf)
        else:
            print 'unknown data - %s: do not plot' % data_name

    def helpAbout(self):
        """Brief description of the plugin.
        """

        # Text to be displayed
        about_text = translate('pyBAR', 
            """<qt>
            <p>Plug-in that plots the data acquired by the Python Bonn ATLAS Readout Framework (pyBAR).
            </qt>""",
            'Text of an About plugin message box')

        descr = dict(module_name='pyBAR', 
            folder=PLUGINSDIR, 
            version=__version__, 
            plugin_name='pyBAR', 
            author='David-Leon Pohl <david-leon.pohl@cern.ch>', 
            descr=about_text)

        return descr