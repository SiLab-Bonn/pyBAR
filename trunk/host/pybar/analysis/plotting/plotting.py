﻿# TODO: set color for bad pixels
# set nan to special value
# masked_array = np.ma.array (a, mask=np.isnan(a))
# cmap = matplotlib.cm.jet
# cmap.set_bad('w',1.)
# ax.imshow(masked_array, interpolation='nearest', cmap=cmap)
import logging
import numpy as np
import math
# import matplotlib.pyplot as plt
# pyplot is not thread safe since it rely on global parameters: https://github.com/matplotlib/matplotlib/issues/757
from matplotlib.figure import Figure
from matplotlib.artist import setp
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from scipy.optimize import curve_fit
from mpl_toolkits.axes_grid1 import make_axes_locatable
# from mpl_toolkits.mplot3d import Axes3D
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime
import itertools
# import re
# import operator
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages


def plot_tdc_event(points, filename=None):
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111, projection='3d')
    xs = points[:, 0]
    ys = points[:, 1]
    zs = points[:, 2]
    cs = points[:, 3]

    p = ax.scatter(xs, ys, zs, c=cs, s=points[:, 3] ** (2) / 5., marker='o')

    ax.set_xlabel('x [250 um]')
    ax.set_ylabel('y [50 um]')
    ax.set_zlabel('t [25 ns]')
    # ax.azim = 200
    # ax.elev = -45

    ax.title('Track of one TPC event')

    ax.set_xlim(0, 80)
    ax.set_ylim(0, 336)

    c_bar = fig.colorbar(p)
    c_bar.set_label('charge [TOT]')

    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    elif filename:
        fig.savefig(filename)
    return fig


def plot_linear_relation(x, y, x_err=None, y_err=None, title=None, point_label=None, legend=None, plot_range=None, plot_range_y=None, x_label=None, y_label=None, y_2_label=None, marker_style='-o', log_x=False, log_y=False, size=None, filename=None):
    ''' Takes point data (x,y) with errors(x,y) and fits a straight line. The deviation to this line is also plotted, showing the offset.

     Parameters
    ----------
    x, y, x_err, y_err: iterable

    filename: string, PdfPages object or None
        PdfPages file object: plot is appended to the pdf
        string: new plot file with the given filename is created
        None: the plot is printed to screen
    '''
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    if x_err is not None:
        x_err = [x_err, x_err]
    if y_err is not None:
        y_err = [y_err, y_err]
    ax.set_title(title)
    if y_label is not None:
        ax.set_ylabel(y_label)
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    if plot_range:
        ax.set_xlim((min(plot_range), max(plot_range)))
    if plot_range_y:
        ax.set_ylim((min(plot_range_y), max(plot_range_y)))
    if legend:
        fig.legend(legend, 0)
    ax.grid(True)
    fig.errorbar(x, y, xerr=x_err, yerr=y_err, fmt='o', color='black')  # plot points
    # label points if needed
    if point_label is not None:
        for X, Y, Z in zip(x, y, point_label):
            ax.annotate('{}'.format(Z), xy=(X, Y), xytext=(-5, 5), ha='right', textcoords='offset points')
    # line fit
    line_fit, pcov = np.polyfit(x, y, 1, full=False, cov=True)
#     print pcov
#     chi_squared = np.sum((np.polyval(line_fit, x) - y) ** 2)
    fit_fn = np.poly1d(line_fit)
    fig.plot(x, fit_fn(x), '-', lw=2, color='gray')
    line_fit_legend_entry = 'line fit: ax + b\na=$%.2f\pm%.2f$\nb=$%.2f\pm%.2f$' % (line_fit[0], np.absolute(pcov[0][0]) ** 0.5, abs(line_fit[1]), np.absolute(pcov[1][1]) ** 0.5)

    fig.legend(["data", line_fit_legend_entry], 0)
    setp(ax.get_xticklabels(), visible=False)  # remove ticks at common border of both plots

    divider = make_axes_locatable(ax)
    ax_bottom_plot = divider.append_axes("bottom", 2.0, pad=0.0, sharex=ax)

    ax_bottom_plot.bar(x, y - fit_fn(x), align='center', width=np.amin(np.diff(x)) / 2, color='gray')
#     plot(x, y - fit_fn(x))
    ax_bottom_plot.grid(True)
    if x_label is not None:
        ax.set_xlabel(x_label)
    if y_2_label is not None:
        ax.set_ylabel(y_2_label)

    ax.set_ylim((-np.amax(np.abs(y - fit_fn(x)))), (np.amax(np.abs(y - fit_fn(x)))))

    fig.plot(ax.set_xlim(), [0, 0], '-', color='black')
    setp(ax_bottom_plot.get_yticklabels()[-2:-1], visible=False)
#     print ax_bottom_plot.get_yticklabels()[1]

#     ax.set_aspect(2)
#     ax_bottom_plot.set_aspect(2)

    if size is not None:
        fig.set_size_inches(size)

    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    elif filename:
        fig.savefig(filename, bbox_inches='tight')

    return fig


def plot_fancy_occupancy(hist, z_max=None, filename=None):
    if z_max == 'median':
        median = np.ma.median(hist)
        z_max = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif z_max == 'maximum' or z_max is None:
        maximum = np.ma.max(hist)
        z_max = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1

#     ax.set_title('Occupancy (%d entries)' % np.sum(hist))
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    extent = [0.5, 80.5, 336.5, 0.5]
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
#     norm = colors.LogNorm()

    im = ax.imshow(hist, interpolation='nearest', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    ax.set_ylim((336.5, 0.5))
    ax.set_xlim((0.5, 80.5))
#     ax.set_title('Occupancy (%d entries)' % np.sum(hist))
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')

    # create new axes on the right and on the top of the current axes
    # The first argument of the new_vertical(new_horizontal) method is
    # the height (width) of the axes to be created in inches.
    divider = make_axes_locatable(ax)
    axHistx = divider.append_axes("top", 1.2, pad=0.2, sharex=ax)
    axHisty = divider.append_axes("right", 1.2, pad=0.2, sharey=ax)

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = fig.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
    cb.set_label("#")
    # make some labels invisible
    setp(axHistx.get_xticklabels() + axHisty.get_yticklabels(), visible=False)
    hight = np.ma.sum(hist, axis=0)
    # hight[hight.mask] = 0
    axHistx.bar(left=range(1, 81), height=hight, align='center', linewidth=0)
    axHistx.set_xlim((0.5, 80.5))
    if hist.all() is np.ma.masked:
        axHistx.set_ylim((0, 1))
    axHistx.locator_params(axis='y', nbins=3)
    axHistx.ticklabel_format(style='sci', scilimits=(0, 4), axis='y')
    axHistx.set_ylabel('#')
    width = np.ma.sum(hist, axis=1)
    # width[hight.mask] = 0
    axHisty.barh(bottom=range(1, 337), width=width, align='center', linewidth=0)
    axHisty.set_ylim((336.5, 0.5))
    if hist.all() is np.ma.masked:
        axHisty.set_xlim((0, 1))
    axHisty.locator_params(axis='x', nbins=3)
    axHisty.ticklabel_format(style='sci', scilimits=(0, 4), axis='x')
    axHisty.set_xlabel('#')

    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_occupancy(hist, title='Occupancy', z_max=None, filename=None):
    if z_max == 'median':
        median = np.ma.median(hist)
        z_max = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif z_max == 'maximum' or z_max is None:
        maximum = np.ma.max(hist)
        z_max = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1

    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.set_adjustable('box-forced')
#     extent = [yedges[0] - 0.5, yedges[-1] + 0.5, xedges[-1] + 0.5, xedges[0] - 0.5]
    extent = [0.5, 80.5, 336.5, 0.5]
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
#     norm = colors.LogNorm()

    im = ax.imshow(hist, interpolation='nearest', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    ax.set_ylim((336.5, 0.5))
    ax.set_xlim((0.5, 80.5))
    ax.set_title(title + ' (%d entrie(s))' % (0 if hist.all() is np.ma.masked else np.ma.sum(hist)))
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')

    divider = make_axes_locatable(ax)

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = fig.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
    cb.set_label("#")

    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def make_occupancy_hist(cols, rows, ncols=80, nrows=336):
    hist, xedges, yedges = np.histogram2d(rows, cols, bins=(nrows, ncols), range=[[1, nrows], [1, ncols]])
#     extent = [yedges[0] - 0.5, yedges[-1] + 0.5, xedges[-1] + 0.5, xedges[0] - 0.5]

    return np.ma.masked_equal(hist, 0)  # , extent


def plot_profile_histogram(x, y, n_bins=100, title=None, x_label=None, y_label=None, log_y=False, filename=None):
    '''Takes 2D point data (x,y) and creates a profile histogram similar to the TProfile in ROOT. It calculates
    the y mean for every bin at the bin center and gives the y mean error as error bars.

    Parameters
    ----------
    x : array like
        data x positions
    y : array like
        data y positions
    n_bins : int
        the number of bins used to create the histogram
    '''
    if len(x) != len(y):
        raise ValueError('x and y dimensions have to be the same')
    n, bin_edges = np.histogram(x, bins=n_bins)  # needed to calculate the number of points per bin
    sy = np.histogram(x, bins=n_bins, weights=y)[0]  # the sum of the bin values
    sy2 = np.histogram(x, bins=n_bins, weights=y * y)[0]  # the quadratic sum of the bin values
    bin_centers = (bin_edges[1:] + bin_edges[:-1]) / 2  # calculate the bin center for all bins
    mean = sy / n  # calculate the mean of all bins
    std = np.sqrt((sy2 / n - mean * mean))  # TODO: no understood, need check if this is really the standard deviation
    #     std_mean = np.sqrt((sy2 - 2 * mean * sy + mean * mean) / (1*(n - 1)))  # this should be the formular ?!
    std_mean = std / np.sqrt((n - 1))
    mean[np.isnan(mean)] = 0.
    std_mean[np.isnan(std_mean)] = 0.
#     from scipy.special import erf
#     def scurve(x, A, mu, sigma):
#         return 0.5 * A * erf((-x + mu) / (np.sqrt(2) * sigma)) + 0.5 * A
#     popt, _ = curve_fit(scurve, bin_centers, mean, p0=[1.5, 9000, 500])
#     polynom_fit = np.poly1d(np.polyfit(bin_centers, mean, deg=7))
#     fig.plot(bin_centers, polynom_fit(bin_centers), 'r-')

    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.errorbar(bin_centers, mean, yerr=std_mean, fmt='o')
    ax.set_title(title)
    if x_label is not None:
        ax.set_xlabel(x_label)
    if y_label is not None:
        ax.set_ylabel(y_label)
    if log_y:
        ax.yscale('log')
    ax.grid(True)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_scatter(x, y, x_err=None, y_err=None, title=None, legend=None, plot_range=None, plot_range_y=None, x_label=None, y_label=None, marker_style='-o', log_x=False, log_y=False, filename=None):
    logging.info("Plot scatter plot %s" % ((': ' + title) if title is not None else ''))
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    if x_err is not None:
        x_err = [x_err, x_err]
    if y_err is not None:
        y_err = [y_err, y_err]
    if x_err is not None or y_err is not None:
        ax.errorbar(x, y, xerr=x_err, yerr=y_err, fmt=marker_style)
    else:
        ax.plot(x, y, marker_style, markersize=1)
    ax.set_title(title)
    if x_label is not None:
        ax.set_xlabel(x_label)
    if y_label is not None:
        ax.set_ylabel(y_label)
    if log_x:
        ax.xscale('log')
    if log_y:
        ax.yscale('log')
    if plot_range:
        ax.set_xlim((min(plot_range), max(plot_range)))
    if plot_range_y:
        ax.set_ylim((min(plot_range_y), max(plot_range_y)))
    if legend:
        ax.legend(legend, 0)
    ax.grid(True)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_correlation(hist, title="Hit correlation", xlabel=None, ylabel=None, filename=None):
    logging.info("Plotting correlations")
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(1, 1, 1)
    cmap = cm.get_cmap('jet')
    extent = [hist[2][0] - 0.5, hist[2][-1] + 0.5, hist[1][-1] + 0.5, hist[1][0] - 0.5]
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    im = ax.imshow(hist[0], extent=extent, cmap=cmap, interpolation='nearest')
    ax.invert_yaxis()
    # add colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    z_max = np.max(hist[0])
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    fig.colorbar(im, boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_pixel_matrix(hist, title="Hit correlation", filename=None):
    logging.info("Plotting pixel matrix: " + title)
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.set_title(title)
    ax.set_xlabel('Col')
    ax.set_ylabel('Row')
    cmap = cm.get_cmap('jet')
#             extent = [hist_mean[2] - 0.5, hist_mean[2][-1] + 0.5, hist_mean[1][-1] + 0.5, hist_mean[1][0] - 0.5]
    ax.imshow(hist.T, aspect='auto', cmap=cmap, interpolation='nearest')
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    z_max = np.max(hist)
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    fig.colorbar(boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_n_cluster(hist, title=None, filename=None):
    plot_1d_hist(hist=hist[0], title='Cluster per event (' + str(np.sum(hist[0])) + ' entries)' if title is None else title, log_y=True, x_axis_title='Cluster per event', y_axis_title='#', filename=filename)


def round_to_multiple(number, multiple):
    '''Rounding up to the nearest multiple of any positive integer

    Parameters
    ----------
    number : int, float
        Input number.
    multiple : int
        Round up to multiple of multiple. Will be converted to int. Must not be equal zero.
    Returns
    -------
    ceil_mod_number : int
        Rounded up number.
    '''
    multiple = int(multiple)
    if multiple == 0:
        multiple = 1
    ceil_mod_number = number - number % (-multiple)
    return int(ceil_mod_number)


def plot_relative_bcid(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Relative BCID (former LVL1ID)' if title is None else title, log_y=True, plot_range=range(0, 16), x_axis_title='Relative BCID [25 ns]', y_axis_title='#', filename=filename, figure_name='Relative BCID')


def plot_relative_bcid_stop_mode(hist, filename=None):
    try:
        max_plot_range = np.where(hist[:] != 0)[0][-1] + 1
    except IndexError:
        max_plot_range = 1
    plot_1d_hist(hist=hist, title='Latency window in stop mode', plot_range=range(0, max_plot_range), x_axis_title='Lantency window [BCID]', y_axis_title='#', filename=filename, figure_name='Latency window in stop mode')


def plot_tot(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Time-over-Threshold distribution (ToT code)' if title is None else title, plot_range=range(0, 16), x_axis_title='ToT [25 ns]', y_axis_title='#', color='b', filename=filename, figure_name='Hit Tot')


def plot_tdc(hist, title=None, filename=None):
    masked_hist, indices = hist_quantiles(hist, prob=(0., 0.99), return_indices=True)
    plot_1d_hist(hist=masked_hist, title='TDC Hit distribution (' + str(np.sum(hist)) + ' entries)' if title is None else title, plot_range=range(*indices), x_axis_title='hit TDC', y_axis_title='#', color='b', filename=filename, figure_name='Hit TDC')


def plot_tdc_counter(hist, title=None, filename=None):
    masked_hist, indices = hist_quantiles(hist, prob=(0., 0.99), return_indices=True)
    plot_1d_hist(hist=masked_hist, title='TDC counter distribution (' + str(np.sum(hist)) + ' entries)' if title is None else title, plot_range=range(*indices), x_axis_title='TDC value', y_axis_title='#', color='b', filename=filename, figure_name='Counter TDC')


def plot_event_errors(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Event status' if title is None else title, plot_range=range(0, 11), x_ticks=('SR\noccured', 'No\ntrigger', 'LVL1ID\nnot const.', '#BCID\nwrong', 'unknown\nword', 'BCID\njump', 'trigger\nerror', 'truncated', 'TDC\nword', '> 1 TDC\nwords', 'TDC\noverflow'), color='g', y_axis_title='#', filename=filename, figure_name='Event Errors')


def plot_trigger_errors(hist, filename=None):
    plot_1d_hist(hist=hist, title='Trigger errors', plot_range=range(0, 8), x_ticks=('increase\nerror', 'more than\none trg.', 'TLU\naccept', 'TLU\ntime out', 'not\nused', 'not\nused', 'not\nused', 'not\nused'), color='g', y_axis_title='#', filename=filename, figure_name='Trigger Errors')


def plot_service_records(hist, filename=None):
    plot_1d_hist(hist=hist, title='Service records (' + str(np.sum(hist)) + ' entries)', x_axis_title='Service record code', color='g', y_axis_title='#', filename=filename, figure_name='Service Records')


def plot_cluster_tot(hist, median=False, max_occ=None, filename=None):
    plot_1d_hist(hist=hist[:, 0], title='Cluster ToT (' + str(sum(hist[:, 0])) + ' entries)', plot_range=range(0, 32), x_axis_title='cluster ToT', y_axis_title='#', filename=filename)


def plot_cluster_size(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Cluster size (' + str(np.sum(hist)) + ' entries)' if title is None else title, log_y=True, plot_range=range(0, 32), x_axis_title='Cluster size', y_axis_title='#', filename=filename)


def plot_scurves(occupancy_hist, scan_parameters, title='S-Curves', ylabel='Occupancy', max_occ=None, scan_parameter_name=None, filename=None):  # tornado plot
    occ_mask = np.all(occupancy_hist == 0, axis=2)
    if max_occ is None:
        max_occ = 2 * np.median(np.amax(occupancy_hist, axis=2))
        if np.allclose(max_occ, 0.0):
            max_occ = np.amax(occupancy_hist)
        if np.allclose(max_occ, 0.0):
            max_occ = 1
    if len(occupancy_hist.shape) < 3:
        raise ValueError('Found array with shape %s' % str(occupancy_hist.shape))
#     y = occupancy_hist.reshape(-1)  # np.ravel(occupancy_hist) or occupancy_hist.flat
    n_pixel = occupancy_hist.shape[0] * occupancy_hist.shape[1]
#     x = np.tile(scan_parameters, n_pixel)
    cmap = cm.get_cmap('jet', 200)
    for index, scan_parameter in enumerate(scan_parameters):
        compressed_data = np.ma.masked_array(occupancy_hist[:, :, index], mask=occ_mask).compressed()
        heatmap, xedges, yedges = np.histogram2d(compressed_data, [scan_parameter] * compressed_data.shape[0], range=[[0, max_occ], [scan_parameters[0], scan_parameters[-1]]], bins=(max_occ + 1, len(scan_parameters)))
        if index == 0:
            hist = heatmap
        else:
            hist += heatmap
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor('white')
    if len(scan_parameters) > 1:
        scan_parameter_dist = (np.amax(scan_parameters) - np.amin(scan_parameters)) / (len(scan_parameters) - 1)
    else:
        scan_parameter_dist = 0
    extent = [yedges[0] - scan_parameter_dist / 2, yedges[-1] + scan_parameter_dist / 2, xedges[-1] + 0.5, xedges[0] - 0.5]
    norm = colors.LogNorm()
    im = ax.imshow(hist, interpolation='nearest', aspect="auto", cmap=cmap, extent=extent, norm=norm)
    ax.invert_yaxis()
    fig.colorbar(im)
    ax.set_title(title + ' for %d pixel(s)' % (n_pixel - np.count_nonzero(occ_mask)))
    if scan_parameter_name is None:
        ax.set_xlabel('Scan parameter')
    else:
        ax.set_xlabel(scan_parameter_name)
    ax.set_ylabel(ylabel)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_scatter_time(x, y, yerr=None, title=None, legend=None, plot_range=None, plot_range_y=None, x_label=None, y_label=None, marker_style='-o', log_x=False, log_y=False, filename=None):
    logging.info("Plot time scatter plot %s" % ((': ' + title) if title is not None else ''))
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.format_xdata = mdates.DateFormatter('%Y-%m-%d')
    times = []
    for time in x:
        times.append(datetime.fromtimestamp(time))
    if yerr is not None:
        ax.errorbar(times, y, yerr=[yerr, yerr], fmt=marker_style)
    else:
        ax.plot(times, y, marker_style)
    ax.set_title(title)
    if x_label is not None:
        ax.set_xlabel(x_label)
    if y_label is not None:
        ax.set_ylabel(y_label)
    if log_x:
        ax.xscale('log')
    if log_y:
        ax.yscale('log')
    if plot_range:
        ax.set_xlim((min(plot_range), max(plot_range)))
    if plot_range_y:
        ax.set_ylim((min(plot_range_y), max(plot_range_y)))
    if legend:
        ax.legend(legend, 0)
    ax.grid(True)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_cluster_tot_size(hist, median=False, z_max=None, filename=None):
    H = hist[0:50, 0:20]
    if z_max is None:
        z_max = np.ma.max(H)
    if z_max < 1 or H.all() is np.ma.masked:
        z_max = 1
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    extent = [-0.5, 20.5, 49.5, -0.5]
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(H, aspect="auto", interpolation='nearest', cmap=cmap, norm=norm, extent=extent)  # for monitoring
    ax.set_title('Cluster size and cluster ToT (' + str(np.sum(H) / 2) + ' entries)')
    ax.set_xlabel('cluster size')
    ax.set_ylabel('cluster ToT')
    # fig.colorbar(cmap=cmap)
    ax.invert_yaxis()
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = fig.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
    cb.set_label("#")
    fig.patch.set_facecolor('white')
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_1d_hist(hist, yerr=None, title=None, x_axis_title=None, y_axis_title=None, x_ticks=None, color='r', plot_range=None, log_y=False, filename=None, figure_name=None):
    logging.info("Plot 1d histogram%s" % ((': ' + title) if title is not None else ''))
    fig = Figure()
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(111)
    if plot_range is None:
        plot_range = range(0, len(hist))
    if not plot_range:
        plot_range = [0]
    if yerr is not None:
        ax.bar(left=plot_range, height=hist[plot_range], color=color, align='center', yerr=yerr)
    else:
        ax.bar(left=plot_range, height=hist[plot_range], color=color, align='center')
    ax.set_xlim((min(plot_range) - 0.5, max(plot_range) + 0.5))
    ax.set_title(title)
    if x_axis_title is not None:
        ax.set_xlabel(x_axis_title)
    if y_axis_title is not None:
        ax.set_ylabel(y_axis_title)
    if x_ticks is not None:
        ax.set_xticks(range(0, len(hist[:])) if plot_range is None else plot_range, x_ticks)
#         ax.set_tick_params(which='both', labelsize=8)
    if np.allclose(hist, 0.0):
        ax.set_ylim((0, 1))
    else:
        if log_y:
            ax.set_yscale('log')
    ax.grid(True)
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def create_2d_pixel_hist(fig, ax, hist2d, title=None, x_axis_title=None, y_axis_title=None, z_max=None):
    extent = [0.5, 80.5, 336.5, 0.5]
    if z_max is None:
        if hist2d.all() is np.ma.masked:  # check if masked array is fully masked
            z_max = 1
        else:
            z_max = 2 * math.ceil(hist2d.max())
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(hist2d, interpolation='nearest', aspect="auto", cmap=cmap, norm=norm, extent=extent)
    if title is not None:
        ax.set_title(title)
    if x_axis_title is not None:
        ax.set_xlabel(x_axis_title)
    if y_axis_title is not None:
        ax.set_ylabel(y_axis_title)
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)


def create_1d_hist(fig, ax, hist, title=None, x_axis_title=None, y_axis_title=None, bins=101, x_min=None, x_max=None):
    if hist.all() is np.ma.masked:
        median = 0.0
        mean = 0.0
        rms = 0.0
    else:
        median = np.ma.median(hist)
        mean = np.ma.mean(hist)
        rms = np.ma.std(hist, dtype=np.float64)
    if x_min is None:
        x_min = 0.0
    if x_max is None:
        if hist.all() is np.ma.masked:  # check if masked array is fully masked
            x_max = 1.0
        else:
            x_max = math.ceil(hist.max())
    hist_bins = int(x_max - x_min) + 1 if bins is None else bins
    if hist_bins > 1:
        bin_width = (x_max - x_min) / (hist_bins - 1.0)
    else:
        bin_width = 1.0
    hist_range = (x_min - bin_width / 2.0, x_max + bin_width / 2.0)
    masked_hist = np.ma.masked_array(hist)
    masked_hist[masked_hist.mask] = np.iinfo(masked_hist.dtype).max
    _, _, _ = ax.hist(x=masked_hist.compressed(), bins=hist_bins, range=hist_range, align='mid')  # re-bin to 1d histogram, x argument needs to be 1D
    # BUG: np.ma.compressed(np.ma.masked_array(hist)) (2D) is not equal to np.ma.masked_array(hist).compressed() (1D) if hist is ndarray
    ax.set_xlim(hist_range)  # overwrite xlim
    if hist.all() is np.ma.masked:  # or np.allclose(hist, 0.0):
        ax.set_ylim((0, 1))
        ax.set_xlim((-0.5, +0.5))
    # create histogram without masked elements, higher precision when calculating gauss
    h_1d, h_bins = np.histogram(np.ma.masked_array(hist).compressed(), bins=hist_bins, range=hist_range)
    if title is not None:
        ax.set_title(title)
    if x_axis_title is not None:
        ax.set_xlabel(x_axis_title)
    if y_axis_title is not None:
        ax.set_ylabel(y_axis_title)
    bin_centres = (h_bins[:-1] + h_bins[1:]) / 2.0
    amplitude = np.amax(h_1d)

    # defining gauss fit function
    def gauss(x, *p):
        A, mu, sigma = p
        return A * np.exp(-(x - mu) ** 2.0 / (2.0 * sigma ** 2.0))

    p0 = (amplitude, mean, rms)  # p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
    try:
        coeff, _ = curve_fit(gauss, bin_centres, h_1d, p0=p0)
        hist_fit = gauss(bin_centres, *coeff)
        ax.plot(bin_centres, hist_fit, "r--", label='Gauss fit')
        chi2 = 0.0
        for i in range(0, len(h_1d)):
            chi2 += (h_1d[i] - gauss(h_bins[i], *coeff)) ** 2.0
        textright = '$\mu=%.2f$\n$\sigma=%.2f$\n$\chi2=%.2f$' % (coeff[1], coeff[2], chi2)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.85, 0.9, textright, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)
    except RuntimeError, e:
        logging.info('Plot 1d histogram: gauss fit failed, %s' % e)
    except TypeError, e:
        logging.info('Plot 1d histogram: gauss fit failed, %s' % e)
    textleft = '$\mathrm{mean}=%.2f$\n$\mathrm{RMS}=%.2f$\n$\mathrm{median}=%.2f$' % (mean, rms, median)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.1, 0.9, textleft, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)


def create_pixel_scatter_plot(fig, ax, hist, title=None, x_axis_title=None, y_axis_title=None, y_min=None, y_max=None):
    scatter_y_mean = np.ma.mean(hist, axis=0)
    scatter_y = hist.flatten('F')
    ax.scatter(range(80 * 336), scatter_y, marker='o', s=0.8, rasterized=True)
    p1, = ax.plot(range(336 / 2, 80 * 336 + 336 / 2, 336), scatter_y_mean, 'o')
    ax.plot(range(336 / 2, 80 * 336 + 336 / 2, 336), scatter_y_mean, linewidth=2.0)
    ax.legend([p1], ["column mean"], prop={'size': 6})
    ax.set_xlim((0, 26880))
    if y_min is None:
        y_min = 0
    if y_max is None:
        if hist.all() is np.ma.masked:  # check if masked array is fully masked
            y_max = 1
        else:
            y_max = math.ceil(hist.max())  # np.max(scatter_y)
    ax.set_ylim(ymin=y_min)
    ax.set_ylim(ymax=y_max)
    if title is not None:
        ax.title(title)
    if x_axis_title is not None:
        ax.set_xlabel(x_axis_title)
    if y_axis_title is not None:
        ax.set_ylabel(y_axis_title)


def plotThreeWay(hist, title, filename=None, x_axis_title=None, minimum=None, maximum=None, bins=101):  # the famous 3 way plot (enhanced)
    if minimum is None:
        minimum = 0
    elif minimum == 'minimum':
        minimum = np.ma.min(hist)
    if maximum == 'median' or maximum is None:
        median = np.ma.median(hist)
        maximum = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif maximum == 'maximum':
        maximum = np.ma.max(hist)
        maximum = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if maximum < 1 or hist.all() is np.ma.masked:
        maximum = 1

    x_axis_title = '' if x_axis_title is None else x_axis_title
    fig = Figure()
    canvas = FigureCanvas(fig)
    fig.patch.set_facecolor('white')
    ax1 = fig.add_subplot(311)
    create_2d_pixel_hist(fig, ax1, hist, title=title, x_axis_title="column", y_axis_title="row", z_max=maximum)
    ax2 = fig.add_subplot(312)
    create_1d_hist(fig, ax2, hist, bins=bins, x_axis_title=x_axis_title, y_axis_title="#", x_min=minimum, x_max=maximum)
    ax3 = fig.add_subplot(313)
    create_pixel_scatter_plot(fig, ax3, hist, x_axis_title="channel=row + column*336", y_axis_title=x_axis_title, y_min=minimum, y_max=maximum)
    fig.tight_layout()
    if not filename:
        fig.show()
    elif isinstance(filename, PdfPages):
        filename.savefig(fig)
    else:
        fig.savefig(filename)


def plot_correlations(filenames, limit=None):
    DataFrame = pd.DataFrame()
    index = 0
    for fileName in filenames:
        print 'Opening ', fileName
        with pd.get_store(fileName, 'r') as store:
            tempDataFrame = pd.DataFrame({'Event': store.Hits.Event[:15000], 'Row' + str(index): store.Hits.Row[:15000]})
            tempDataFrame = tempDataFrame.set_index('Event')
            DataFrame = tempDataFrame.join(DataFrame)
            DataFrame = DataFrame.dropna()
            index += 1
            del tempDataFrame
    DataFrame["index"] = DataFrame.index
    DataFrame.drop_duplicates(take_last=True, inplace=True)
    del DataFrame["index"]
#     print DataFrame.head(10)
    correlationNames = ('Row')
    index = 0
    for corName in correlationNames:
        for colName in itertools.permutations(DataFrame.filter(regex=corName), 2):
            if(corName == 'Col'):
                heatmap, xedges, yedges = np.histogram2d(DataFrame[colName[0]], DataFrame[colName[1]], bins=(80, 80), range=[[1, 80], [1, 80]])
            else:
                heatmap, xedges, yedges = np.histogram2d(DataFrame[colName[0]], DataFrame[colName[1]], bins=(336, 336), range=[[1, 336], [1, 336]])
            extent = [yedges[0] - 0.5, yedges[-1] + 0.5, xedges[-1] + 0.5, xedges[0] - 0.5]
#             extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
            cmap = cm.get_cmap('hot', 40)
            fig = Figure()
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.imshow(heatmap, extent=extent, cmap=cmap, interpolation='nearest')
            ax.invert_yaxis()
            ax.set_xlabel(colName[0])
            ax.set_ylabel(colName[1])
            ax.set_title('Correlation plot(' + corName + ')')
            fig.savefig(colName[0] + '_' + colName[1] + '.pdf')
#             print 'store as ', fileNames[int(index/2)]
            index += 1


def hist_quantiles(hist, prob=(0.05, 0.95), return_indices=False, copy=False):
    '''Calculate quantiles from histograms, cuts off hist below and above given quantile. This function will not cut off more than the given values.

    Parameters
    ----------
    hist : array_like, iterable
        Input histogram with dimension at most 1.
    prob : float, list, tuple
        List of quantiles to compute. Upper and lower limit. From 0 to 1. Default is 0.05 and 0.95.
    return_indices : bool, optional
        If true, return the indices of the hist.
    copy : bool, optional
        Whether to copy the input data (True), or to use a reference instead. Default is False.

    Returns
    -------
    masked_hist : masked_array
       Hist with masked elements.
    masked_hist : masked_array, tuple
        Hist with masked elements and indices.
    '''
    # make np array
    hist_t = np.array(hist)
    # calculate cumulative distribution
    cdf = np.cumsum(hist_t)
    # copy, convert and normalize
    if cdf[-1] == 0:
        normcdf = cdf.astype('float')
    else:
        normcdf = cdf.astype('float') / cdf[-1]
    # calculate unique values from cumulative distribution and their indices
    unormcdf, indices = np.unique(normcdf, return_index=True)
    # calculate limits
    try:
        hp = np.where(unormcdf > prob[1])[0][0]
        lp = np.where(unormcdf >= prob[0])[0][0]
    except IndexError:
        hp_index = hist_t.shape[0]
        lp_index = 0
    else:
        hp_index = indices[hp]
        lp_index = indices[lp]
    # copy and create ma
    masked_hist = np.ma.array(hist, copy=copy, mask=True)
    masked_hist.mask[lp_index:hp_index + 1] = False
    if return_indices:
        return masked_hist, (lp_index, hp_index)
    else:
        return masked_hist


def hist_last_nonzero(hist, return_index=False, copy=False):
    '''Find the last nonzero index and mask the remaining entries.

    Parameters
    ----------
    hist : array_like, iterable
        Input histogram with dimension at most 1.
    return_index : bool, optional
        If true, return the index.
    copy : bool, optional
        Whether to copy the input data (True), or to use a reference instead. Default is False.

    Returns
    -------
    masked_hist : masked_array
       Hist with masked elements.
    masked_hist : masked_array, tuple
        Hist with masked elements and index of the element after the last nonzero value.
    '''
    # make np array
    hist_t = np.array(hist)
    index = (np.where(hist_t)[-1][-1] + 1) if np.sum(hist_t) > 1 else hist_t.shape[0]
    # copy and create ma
    masked_hist = np.ma.array(hist, copy=copy, mask=True)
    masked_hist.mask[index:] = False
    if return_index:
        return masked_hist, index
    else:
        return masked_hist


if __name__ == "__main__":
    pass
