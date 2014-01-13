import numpy as np
import math
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pandas as pd
import itertools
import re
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def plot_fancy_occupancy(hist, z_max=None, filename=None):
    plt.clf()
    if z_max == 'median':
        median = np.ma.median(hist)
        z_max = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif z_max == 'maximum' or z_max is None:
        maximum = np.ma.max(hist)
        z_max = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1

#     plt.title('Occupancy (%d entries)' % np.sum(hist))
    fig = plt.figure(1)
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
#     plt.title('Occupancy (%d entries)' % np.sum(hist))
    ax.set_xlabel('Column')
    ax.set_ylabel('Row')

    # create new axes on the right and on the top of the current axes
    # The first argument of the new_vertical(new_horizontal) method is
    # the height (width) of the axes to be created in inches.
    divider = make_axes_locatable(ax)
    axHistx = divider.append_axes("top", 1.2, pad=0.2, sharex=ax)
    axHisty = divider.append_axes("right", 1.2, pad=0.2, sharey=ax)

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
#     cb = plt.colorbar(im, cax=cax)
    cb.set_label("#")

    # make some labels invisible
    plt.setp(axHistx.get_xticklabels() + axHisty.get_yticklabels(), visible=False)
    hight = np.ma.sum(hist, axis=0)
    hight[hight.mask] = 0
    axHistx.bar(left=range(1, 81), height=hight, align='center', linewidth=0)
    axHistx.set_xlim((0.5, 80.5))
    if hist.all() is np.ma.masked:
        axHistx.set_ylim((0, 1))
    axHistx.locator_params(axis='y', nbins=3)
    axHistx.ticklabel_format(style='sci', scilimits=(0, 4), axis='y')
    axHistx.set_ylabel('#')
    width = np.ma.sum(hist, axis=1)
    width[hight.mask] = 0
    axHisty.barh(bottom=range(1, 337), width=width, align='center', linewidth=0)
    axHisty.set_ylim((336.5, 0.5))
    if hist.all() is np.ma.masked:
        axHisty.set_xlim((0, 1))
    axHisty.locator_params(axis='x', nbins=3)
    axHisty.ticklabel_format(style='sci', scilimits=(0, 4), axis='x')
    axHisty.set_xlabel('#')

    if filename is None:
        plt.show()
    elif isinstance(filename, PdfPages):
        filename.savefig()
        pass
    else:
        plt.savefig(filename)
    plt.close()


def plot_occupancy(hist, title='Occupancy', z_max=None, filename=None):
    plt.clf()
    if z_max == 'median':
        median = np.ma.median(hist)
        z_max = median * 2  # round_to_multiple(median * 2, math.floor(math.log10(median * 2)))
    elif z_max == 'maximum' or z_max is None:
        maximum = np.ma.max(hist)
        z_max = maximum  # round_to_multiple(maximum, math.floor(math.log10(maximum)))
    if z_max < 1 or hist.all() is np.ma.masked:
        z_max = 1

    fig = plt.figure(1)
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
    plt.title(title + ' (%d entrie(s))' % (0 if hist.all() is np.ma.masked else np.ma.sum(hist)))
    plt.xlabel('Column')
    plt.ylabel('Row')

    divider = make_axes_locatable(ax)

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
#     cb = plt.colorbar(im, cax=cax)
    cb.set_label("#")

    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def make_occupancy_hist(cols, rows, ncols=80, nrows=336):
    hist, xedges, yedges = np.histogram2d(rows, cols, bins=(nrows, ncols), range=[[1, nrows], [1, ncols]])
#     extent = [yedges[0] - 0.5, yedges[-1] + 0.5, xedges[-1] + 0.5, xedges[0] - 0.5]

    return hist  # , extent


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
# #     
#     def scurve(x, A, mu, sigma):
#         return 0.5 * A * erf((-x + mu) / (np.sqrt(2) * sigma)) + 0.5 * A
#      
#     popt, _ = curve_fit(scurve, bin_centers, mean, p0=[1.5, 9000, 500])

#     polynom_fit = np.poly1d(np.polyfit(bin_centers, mean, deg=7))
#     plt.plot(bin_centers, polynom_fit(bin_centers), 'r-')
    plt.errorbar(bin_centers, mean, yerr=std_mean, fmt='o')
    plt.title(title)
    if x_label is not None:
        plt.xlabel(x_label)
    if y_label is not None:
        plt.ylabel(y_label)
    if log_y:
        plt.yscale('log')
    plt.grid(True)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_scatter(x, y, title=None, x_label=None, y_label=None, marker_style='-o', log_x=False, log_y=False, filename=None):
    logging.info("Plot scatter plot %s" % ((': ' + title) if title is not None else ''))
    plt.clf()
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    plt.plot(x, y, marker_style)
    plt.title(title)
    if x_label is not None:
        plt.xlabel(x_label)
    if y_label is not None:
        plt.ylabel(y_label)
    if log_x:
        plt.xscale('log')
    if log_y:
        plt.yscale('log')
    plt.grid(True)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_correlation(hist, title="Hit correlation", xlabel=None, ylabel=None, filename=None):
    logging.info("Plotting correlations")
    cmap = cm.get_cmap('jet')
    extent = [hist[2][0] - 0.5, hist[2][-1] + 0.5, hist[1][-1] + 0.5, hist[1][0] - 0.5]
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.imshow(hist[0], extent=extent, cmap=cmap, interpolation='nearest')
    plt.gca().invert_yaxis()
    # add colorbar
    divider = make_axes_locatable(plt.gca())
    cax = divider.append_axes("right", size="5%", pad=0.05)
    z_max = np.max(hist[0])
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.colorbar(boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_pixel_matrix(hist, title="Hit correlation", filename=None):
    logging.info("Plotting pixel matrix: " + title)
    plt.title(title)
    plt.xlabel('Col')
    plt.ylabel('Row')
    cmap = cm.get_cmap('jet')
#             extent = [hist_mean[2] - 0.5, hist_mean[2][-1] + 0.5, hist_mean[1][-1] + 0.5, hist_mean[1][0] - 0.5]
    plt.imshow(hist.T, aspect='auto', cmap=cmap, interpolation='nearest')
    divider = make_axes_locatable(plt.gca())
    cax = divider.append_axes("right", size="5%", pad=0.05)
    z_max = np.max(hist)
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.colorbar(boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_n_cluster(hist, title=None, filename=None):
    plot_1d_hist(hist=hist[0], title='Cluster per event (' + str(np.sum(hist[0])) + ' entries)' if title == None else title, log_y=True, x_axis_title='Cluster per event', y_axis_title='#', filename=filename)


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


def plot_relative_bcid(hist, filename=None):
    plot_1d_hist(hist=hist, title='Relative BCID (former LVL1ID)', log_y=True, plot_range=range(0, 16), x_axis_title='Relative BCID [25 ns]', y_axis_title='#', filename=filename)


def plot_tot(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Time-over-Threshold distribution (ToT code)' if title == None else title, plot_range=range(0, 16), x_axis_title='ToT [25 ns]', y_axis_title='#', color='b', filename=filename)


def plot_event_errors(hist, filename=None):
    plot_1d_hist(hist=hist, title='Event errors', plot_range=range(0, 8), x_ticks=('SR\noccured', 'No\ntrigger', 'LVL1ID\nnot const.', '#BCID\nwrong', 'unknown\nword', 'BCID\njump', 'trigger\nerror', 'truncated'), color='g', y_axis_title='#', filename=filename)


def plot_trigger_errors(hist, filename=None):
    plot_1d_hist(hist=hist, title='Trigger errors', plot_range=range(0, 8), x_ticks=('increase\nerror', 'more than\none trg.', 'TLU\naccept', 'TLU\ntime out', 'not\nused', 'not\nused', 'not\nused', 'not\nused'), color='g', y_axis_title='#', filename=filename)


def plot_service_records(hist, filename=None):
    plot_1d_hist(hist=hist, title='Service records (' + str(np.sum(hist)) + ' entries)', x_axis_title='Service record code', color='g', y_axis_title='#', filename=filename)


def plot_cluster_tot(hist, median=False, max_occ=None, filename=None):
    plot_1d_hist(hist=hist[:, 0], title='Cluster ToT (' + str(sum(hist[:, 0])) + ' entries)', plot_range=range(0, 32), x_axis_title='cluster ToT', y_axis_title='#', filename=filename)


def plot_cluster_size(hist, title=None, filename=None):
    plot_1d_hist(hist=hist, title='Cluster size (' + str(np.sum(hist)) + ' entries)' if title == None else title, log_y=True, plot_range=range(0, 32), x_axis_title='Cluster size', y_axis_title='#', filename=filename)


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
    plt.clf()
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    if len(scan_parameters) > 1:
        scan_parameter_dist = (np.amax(scan_parameters) - np.amin(scan_parameters)) / (len(scan_parameters) - 1)
    else:
        scan_parameter_dist = 0
    extent = [yedges[0] - scan_parameter_dist / 2, yedges[-1] + scan_parameter_dist / 2, xedges[-1] + 0.5, xedges[0] - 0.5]
    norm = colors.LogNorm()
    plt.imshow(hist, interpolation='nearest', aspect="auto", cmap=cmap, extent=extent, norm=norm)
    plt.gca().invert_yaxis()
    plt.colorbar()
    plt.title(title + ' for %d pixel(s)' % (n_pixel - np.count_nonzero(occ_mask)))
    if scan_parameter_name is None:
        plt.xlabel('Scan parameter')
    else:
        plt.xlabel(scan_parameter_name)
    plt.ylabel(ylabel)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_cluster_tot_size(hist, median=False, z_max=None, filename=None):
    plt.clf()
    H = hist[0:50, 0:20]
    if z_max is None:
        z_max = np.ma.max(H)
    if z_max < 1 or H.all() is np.ma.masked:
        z_max = 1
    fig = plt.figure(1)
    ax = fig.add_subplot(111)
    extent = [0.5, 20.5, 49.5, -0.5]
    bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(H, aspect="auto", interpolation='nearest', cmap=cmap, norm=norm, extent=extent) # for monitoring
    plt.title('Cluster size and cluster ToT (' + str(np.sum(H) / 2) + ' entries)')
    ax.set_xlabel('cluster size')
    ax.set_ylabel('cluster ToT')
    #ax.colorbar(cmap=cmap)
    ax.invert_yaxis()
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
    cb.set_label("#")
    fig.patch.set_facecolor('white')
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_1d_hist(hist, title=None, x_axis_title=None, y_axis_title=None, x_ticks=None, color='r', plot_range=None, log_y=False, filename=None):
    logging.info("Plot 1d histogram%s" % ((': ' + title) if title is not None else ''))
    plt.clf()
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    if plot_range is None:
        plot_range = range(0, len(hist))
    plt.bar(left=plot_range, height=hist[plot_range], color=color, align='center')
    plt.xlim((min(plot_range) - 0.5, max(plot_range) + 0.5))
    plt.title(title)
    if x_axis_title is not None:
        plt.xlabel(x_axis_title)
    if y_axis_title is not None:
        plt.ylabel(y_axis_title)
    if x_ticks is not None:
        plt.xticks(range(0, len(hist[:])) if plot_range == None else plot_range, x_ticks)
    if np.allclose(hist, 0.0):
        plt.ylim((0, 1))
    else:
        if log_y:
            plt.yscale('log')
    plt.grid(True)
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


# def plot_pixel_mask(mask, maskname, filename=None):
#     plt.clf()
#     extent = [0.5, 80.5, 336.5, 0.5]
#     plt.imshow(mask, interpolation='nearest', aspect="auto", extent=extent) # for monitoring
#     plt.title(maskname+" mask")
#     plt.xlabel('Column')
#     plt.ylabel('Row')
#     plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)  # FIXME: missing parameters
#     if filename is None:
#         plt.show()
#     elif type(filename) == PdfPages:
#         filename.savefig()
#     else:
#         plt.savefig(filename)
#
#
# def plot_pixel_dac_config(dacconfig, dacname, filename = None):
#     plt.clf()
#     extent = [0.5, 80.5, 336.5, 0.5]
#     cmap = cm.get_cmap('hot')
#     ceil_number = dacconfig.max()  # TODO: get max value from register object
#     bounds = range(0, ceil_number+1, ceil_number/255)
#     norm = colors.BoundaryNorm(bounds, cmap.N)
#     plt.imshow(dacconfig, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent)
#     plt.title(dacname+" distribution")
#     plt.xlabel('Column')
#     plt.ylabel('Row')
#     plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
#     if filename is None:
#         plt.show()
#     elif type(filename) == PdfPages:
#         filename.savefig()
#     else:
#         plt.savefig(filename)


def create_2d_pixel_hist(hist2d, title=None, x_axis_title=None, y_axis_title=None, z_max=None):
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
    # plot
    plt.imshow(hist2d, interpolation='nearest', aspect="auto", cmap=cmap, norm=norm, extent=extent)
    if title is not None:
        plt.title(title)
    if x_axis_title is not None:
        plt.xlabel(x_axis_title)
    if y_axis_title is not None:
        plt.ylabel(y_axis_title)
    ax = plt.subplot(311)
#     ax = plt.plot()
    divider = make_axes_locatable(ax)
#     ax = plt.plot()
    ax = plt.subplot(311)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    plt.colorbar(boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)


def create_1d_hist(hist, title=None, x_axis_title=None, y_axis_title=None, bins=None, x_min=None, x_max=None):
    if hist.all() is np.ma.masked:
        median = 0.
        mean = 0.
        rms = 0.
    else:
        median = np.ma.median(hist)
        mean = np.ma.mean(hist)
        rms = np.ma.std(hist, dtype=np.float64)
    hist_bins = 100 if bins is None else bins
    if x_min is None:
        x_min = 0
    if x_max is None:
        if hist.all() is np.ma.masked:  # check if masked array is fully masked
            x_max = 1
        else:
            x_max = math.ceil(hist.max())
    hist_range = (x_min, x_max)
    # plot
    _, _, _ = plt.hist(x=hist.ravel(), bins=hist_bins, range=hist_range)  # re-bin to 1d histogram
    plt.xlim(hist_range)  # overwrite xlim
    if hist.all() is np.ma.masked or np.allclose(hist, 0.0):
        plt.ylim((0, 1))
    # create histogram without masked elements, higher precision when calculating gauss
    h_1d, h_bins = np.histogram(np.ma.compressed(hist), bins=hist_bins, range=hist_range)
    if title is not None:
        plt.title(title)
    if x_axis_title is not None:
        plt.xlabel(x_axis_title)
    if y_axis_title is not None:
        plt.ylabel(y_axis_title)
    bin_centres = (h_bins[:-1] + h_bins[1:]) / 2
    amplitude = np.amax(h_1d)

    # defining gauss fit function
    def gauss(x, *p):
        A, mu, sigma = p
        return A * np.exp(-(x - mu) ** 2 / (2.0 * sigma ** 2))

    p0 = (amplitude, mean, rms)  # p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
    ax = plt.subplot(312)
    try:
        coeff, _ = curve_fit(gauss, bin_centres, h_1d, p0=p0)
        hist_fit = gauss(bin_centres, *coeff)
        plt.plot(bin_centres, hist_fit, "r--", label='Gauss fit')
        chi2 = 0
        for i in range(0, len(h_1d)):
            chi2 += (h_1d[i] - gauss(h_bins[i], *coeff)) ** 2
        textright = '$\mu=%.2f$\n$\sigma=%.2f$\n$\chi2=%.2f$' % (coeff[1], coeff[2], chi2)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.85, 0.9, textright, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)
    except RuntimeError:
        logging.info('Plot 1d histogram: gauss fit failed, do not draw curve')
    textleft = '$\mathrm{mean}=%.2f$\n$\mathrm{RMS}=%.2f$\n$\mathrm{median}=%.2f$' % (mean, rms, median)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.1, 0.9, textleft, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)


def create_pixel_scatter_plot(hist, title=None, x_axis_title=None, y_axis_title=None, y_min=None, y_max=None):
    scatter_y_mean = np.ma.mean(hist, axis=0)
    scatter_y = hist.flatten('F')
    plt.scatter(range(80 * 336), scatter_y, marker='o', s=0.8, rasterized=True)
    p1, = plt.plot(range(336 / 2, 80 * 336 + 336 / 2, 336), scatter_y_mean, 'o')
    plt.plot(range(336 / 2, 80 * 336 + 336 / 2, 336), scatter_y_mean, linewidth=2.0)
    plt.legend([p1], ["column mean"], prop={'size': 6})
    plt.xlim((0, 26880))
    if y_min is None:
        y_min = 0
    if y_max is None:
        if hist.all() is np.ma.masked:  # check if masked array is fully masked
            y_max = 1
        else:
            y_max = math.ceil(hist.max())  # np.max(scatter_y)
    plt.ylim(ymin=y_min)
    plt.ylim(ymax=y_max)
    if title is not None:
        plt.title(title)
    if x_axis_title is not None:
        plt.xlabel(x_axis_title)
    if y_axis_title is not None:
        plt.ylabel(y_axis_title)


def plotThreeWay(hist, title, filename=None, x_axis_title=None, minimum=None, maximum=None, bins=None):  # the famous 3 way plot (enhanced)
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
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    plt.subplot(311)
    create_2d_pixel_hist(hist, title=title, x_axis_title="column", y_axis_title="row", z_max=maximum)
    plt.subplot(312)
    create_1d_hist(hist, bins=bins, x_axis_title=x_axis_title, y_axis_title="#", x_min=minimum, x_max=maximum)
    plt.subplot(313)
    create_pixel_scatter_plot(hist, x_axis_title="channel=row + column*336", y_axis_title=x_axis_title, y_min=minimum, y_max=maximum)
    plt.tight_layout()
    if filename is None:
        plt.show()
    elif type(filename) == PdfPages:
        filename.savefig()
    else:
        plt.savefig(filename)
    plt.close()


def plot_correlations(filenames, limit=None):
    plt.clf()
    DataFrame = pd.DataFrame()
    index = 0
    for fileName in filenames:
        print 'open ', fileName
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
    print DataFrame.head(10)
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
            plt.clf()
            cmap = cm.get_cmap('hot', 40)
            plt.imshow(heatmap, extent=extent, cmap=cmap, interpolation='nearest')
            plt.gca().invert_yaxis()
            plt.xlabel(colName[0])
            plt.ylabel(colName[1])
            plt.title('Correlation plot(' + corName + ')')
            plt.savefig(colName[0] + '_' + colName[1] + '.pdf')
#             print 'store as ', fileNames[int(index/2)]
            index += 1

if __name__ == "__main__":
    filename = "HitMap.txt"
    with open(filename, 'r') as f:
        H = np.empty(shape=(80, 336))
        for line in f.readlines():
            values = re.split("\s", line)
            col = int(values[0])
            row = int(values[1])
            hits = int(values[2])
            # print str(col)
            H[col, row] = hits
    plotThreeWay(H.transpose(), title='Occupancy', x_axis_title='occupancy', filename='SourceScanOccupancy.pdf')

#     with tb.openFile('out.h5', 'r') as in_file:
#         H=np.empty(shape=(336,80),dtype=in_file.root.HistOcc.dtype)
#         H[:]=in_file.root.HistThreshold[:,:]
#         plotThreeWay(hist = in_file.root.HistThreshold[:,:], title = "Threshold", filename = "Threshold.pdf", label = "noise[e]")

# TODO: set color for bad pixels
# set nan to special value
# masked_array = np.ma.array (a, mask=np.isnan(a))
# cmap = matplotlib.cm.jet
# cmap.set_bad('w',1.)
# ax.imshow(masked_array, interpolation='nearest', cmap=cmap)
