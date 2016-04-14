import tables as tb
import numpy as np
import logging
import progressbar

from pybar.analysis import analysis_utils

from matplotlib import pyplot as plt
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages
from scipy.interpolate import interp1d

from mpl_toolkits.axes_grid1 import make_axes_locatable


def myround(x, base=1):
    return int(base * round(float(x) / base))


def plsr_dac_to_charge(plsr_dac):
    return 72.16 * plsr_dac + 2777.63


def plot_passive_cmos(hist, title, distinguish_flavour=True, z_title='#'):
    z_min, z_max = myround(np.amin(hist)), myround(np.amax(hist))
    extent = [0.5, hist.shape[1] + 0.5, 0.5, hist.shape[0] + 0.5]
    bounds = np.linspace(start=z_min, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('coolwarm')
    cmap.set_bad('w', 1.0)
    norm = colors.BoundaryNorm(bounds, cmap.N)

    im = plt.imshow(hist, interpolation='nearest', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    plt.ylim((0.5, hist.shape[0] + 0.5))
    plt.xlim((0.5, hist.shape[1] + 0.5))
    plt.title(title)
    plt.xlabel('Column')
    plt.ylabel('Row')

    if distinguish_flavour:
        plt.text(4, 19, 'AC', fontsize=15)
        plt.text(12, 19, 'DC', fontsize=15)
        plt.text(15, 4.5, '30 um', fontsize=10)
        plt.text(15, 13.5, '25 um', fontsize=10)
        plt.text(15, 22.5, '20 um', fontsize=10)
        plt.text(15, 31.5, '15 um', fontsize=10)

    plt.plot([8.5, 8.5], [0.5, 36.5], color='k', linestyle='-', linewidth=2)
    plt.plot([14.5, 14.5], [0.5, 36.5], color='k', linestyle='--', linewidth=2)
    for i in [9, 18, 27]:
        plt.plot([14.5, 16.5], [i + 0.5, i + 0.5], color='k', linestyle='--', linewidth=2)

    divider = make_axes_locatable(plt.gca())

    cax = divider.append_axes("right", size="5%", pad=0.1)
    cb = plt.gcf().colorbar(im, cax=cax, ticks=np.linspace(start=z_min, stop=z_max, num=9, endpoint=True))
    cb.set_label(z_title)

    plt.show()


def plot_timewalk(hist, xedges, yedges, title, max_time_walk=50):
    yedges *= 1.5625  # One TDC time stamp are 1/640 MHZ = 1.5625 ns
    timewalks = (yedges[0:-1] + yedges[1:]) / 2.
    charges = (xedges[0:-1] + xedges[1:]) / 2.
    print yedges
    def get_mean_from_histogram(counts, bin_positions):
        return np.dot(counts, np.array(bin_positions)) / np.sum(counts).astype('f4')

    # Rebin for more smooth time walk means
    z_min, z_max = myround(np.amin(hist)), myround(np.amax(hist))
    bounds = np.linspace(start=z_min, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w', 1.0)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    hist = np.ma.masked_where(hist == 0, hist)
    #im = plt.imshow(hist.T, interpolation='nearest', aspect='auto', origin='low', cmap=cmap, norm=norm, extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]])

    hist_mean = np.ma.average(hist, axis=1, weights=timewalks) * np.sum(timewalks) / np.sum(hist, axis=1).astype('f4')  # calculate the mean BCID per pixel and scan parameter

    mean, std = [], []
    for one_slice in hist:  # Clearly not the fastest way to calc mean + RMS from a 2D array, but one can understand it...
        mean.append(np.dot(one_slice, timewalks) / np.sum(one_slice))
        try:
            std.append(np.ma.std(np.ma.repeat(timewalks, one_slice, axis=0)))
        except TypeError:
            std.append(-1)

    mean, std = np.array(mean), np.array(std)
    mean = np.ma.masked_invalid(mean)
    std = np.ma.array(std, mask=mean.mask)
    # mean += 0.5  # To make mean fit with 2D binning offset
    zero_timewalk = np.ma.min(mean[-50:]) + 1 * np.ma.mean(std[-50:])  # Time walk is relative, define lowest timewalk as minimum mean time walk + 2 RMS of time walk spread of the pixels (here mean of 50 highest charge bins)

    percentages = []  # Percentages of hits for 5/10/15/... ns timewalk
    n_hits = np.ma.sum(hist)
    for timewalk_bin in range(0, max_time_walk + 1, 5):
        percentages.append(np.round(float(np.ma.sum(hist[:, np.where(timewalks <= zero_timewalk + timewalk_bin)])) / n_hits * 100., 1))

    mean -= zero_timewalk  # Time walk is relative

    plt.plot(charges, mean, '-', label='Mean')
    plt.yticks(np.arange(0, max_time_walk + 1, 5))  # One tick evety 5 ns
    plt.fill_between(charges, mean - np.array(std), mean + np.array(std), color='gray', alpha=0.5, facecolor='gray', label='RMS')

#     im = plt.imshow(hist, interpolation='nearest', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
    plt.ylim((0, max_time_walk))
    plt.xlim((0, max_charge))
    plt.title(title)
    plt.xlabel('Charge [e]')
    plt.ylabel('Time walk per %1.1f electrons [ns]' % (charges[1] - charges[0]))
    plt.legend(loc=0)
    plt.grid()

    ax2 = plt.gca().twinx()
    ax2.set_yticks(np.arange(0, max_time_walk + 1, 5))  # One tick evety 5 ns
    ax2.set_xlim((0, max_charge))
    ax2.set_ylim((0, max_time_walk))
    ax2.set_yticklabels(percentages)
    ax2.set_ylabel('Pixel hits up to corresponding time walk [%]')
    ax2.plot()

    plt.show()


if __name__ == '__main__':
    # Get per pixel TDC calibration for Charge(TDC) calculation
    hit_file = r'15_cmos_passive_1_ext_trigger_scan_interpreted.h5'
    calibation_file = r'14_cmos_passive_1_hit_or_calibration_calibration.h5'
    col_span = [1, 18]  # pixel column range to use in TDC scans; CMOS area + 1 column
    #col_span = [1, 9]  # pixel column range to use in TDC scans; CMOS area + 1 column
    # col_span = [9, 18]  # pixel column range to use in TDC scans; CMOS area + 1 column
    row_span = [295, 336] # pixel row range to use in TDC scans; CMOS area + 5 rows
#     hit_file = r'15_scc_30_ext_trigger_scan_interpreted.h5'
#     calibation_file = r'13_scc_30_hit_or_calibration_calibration.h5'
#     col_span = [55, 75]  # pixel column range to use in TDC scans; CMOS area + 1 column
#     row_span = [125, 225]  # pixel row range to use in TDC scans; CMOS area + 5 rows
#     hit_file = r'15_proto_7_ext_trigger_scan_interpreted.h5'
#     calibation_file = r'13_proto_7_hit_or_calibration_calibration.h5'
#     col_span = [55, 75]  # pixel column range to use in TDC scans; CMOS area + 1 column
#     row_span = [125, 225]  # pixel row range to use in TDC scans; CMOS area + 5 rows

#     hit_file = r'/media/davidlp/Data/tmp/18_proto_7_ext_trigger_scan_interpreted.h5'
#     calibation_file = r'/media/davidlp/Data/tmp/13_proto_7_hit_or_calibration_calibration.h5'
#     col_span = [55, 75]  # pixel column range to use in TDC scans; CMOS area + 1 column
#     row_span = [125, 225]  # pixel row range to use in TDC scans; CMOS area + 5 rows

    max_tdc = 1500
    max_timesamp = 2000
    event_status_select_mask = 0b0000111111111111,  # the event status bits to cut on
    event_status_condition = 0b0000000100000000
    hit_selection = '(column > %d) & (column < %d) & (row > %d) & (row < %d)' % (col_span[0] + 1, col_span[1] - 1, row_span[0] + 5, row_span[1] - 5)  # deselect edge pixels for better cluster size cut
    hit_selection_conditions = ['(n_cluster==1) & (cluster_size == 1) & (relative_BCID >= 1) & (relative_BCID <= 3) & ((tot > 12) | ((TDC * 1.5625 - tot * 25 < 100) & (tot * 25 - TDC * 1.5625 < 100))) & %s' % hit_selection]

    def get_charge(max_tdc, tdc_calibration_values, tdc_pixel_calibration):  # return the charge from calibration
        charge_calibration = np.zeros(shape=(80, 336, max_tdc))
        for column in range(80):
            for row in range(336):
                actual_pixel_calibration = tdc_pixel_calibration[column, row, :]
                if np.any(actual_pixel_calibration != 0) and np.all(np.isfinite(actual_pixel_calibration)):
                    interpolation = interp1d(x=actual_pixel_calibration, y=tdc_calibration_values, kind='slinear', bounds_error=False, fill_value=0)
                    charge_calibration[column, row, :] = interpolation(np.arange(max_tdc))
        return charge_calibration

    with tb.openFile(calibation_file, mode="r") as in_file_calibration_h5:
        tdc_calibration = in_file_calibration_h5.root.HitOrCalibration[:, :, :, 1]
        tdc_calibration_values = in_file_calibration_h5.root.HitOrCalibration.attrs.scan_parameter_values[:]
    charge_calibration = get_charge(max_tdc, tdc_calibration_values, tdc_calibration)
    max_charge = plsr_dac_to_charge(np.amax(charge_calibration))

    # 2_cmos_passive_1_ext_trigger_scan_interpreted.h5
    with tb.open_file(hit_file, 'r') as in_file_h5:
        cluster_hit_table = in_file_h5.root.ClusterHits

        logging.info('Select hits and create TDC histograms for %d cut conditions', len(hit_selection_conditions))
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=cluster_hit_table.shape[0], term_width=80)
        progress_bar.start()
        n_hits, n_selected_hits = 0, 0
        timewalk = np.zeros(shape=(200, max_timesamp), dtype=np.float32)
        for cluster_hits, _ in analysis_utils.data_aligned_at_events(cluster_hit_table, chunk_size=10000000):
            n_hits += cluster_hits.shape[0]
            selected_events_cluster_hits = cluster_hits[np.logical_and(cluster_hits['TDC'] < max_tdc, (cluster_hits['event_status'] & event_status_select_mask) == event_status_condition)]
            for index, condition in enumerate(hit_selection_conditions):
                selected_cluster_hits = analysis_utils.select_hits(selected_events_cluster_hits, condition)
                n_selected_hits += selected_cluster_hits.shape[0]
                column_index, row_index, tdc, tdc_timestamp = selected_cluster_hits['column'] - 1, selected_cluster_hits['row'] - 1, selected_cluster_hits['TDC'], selected_cluster_hits['TDC_time_stamp']

                charge_values = plsr_dac_to_charge(charge_calibration[column_index, row_index, tdc]).astype(np.float32)  # Charge values for each Col/Row/TDC tuple from per pixel charge calibration

                actual_timewalk, xedges, yedges = np.histogram2d(charge_values, tdc_timestamp, bins=timewalk.shape, range=((0, max_charge), (0, max_timesamp)))
                timewalk += actual_timewalk

            progress_bar.update(n_hits)
        progress_bar.finish()
        logging.info('Selected %d of %d hits = %1.1f percent', n_selected_hits, n_hits, float(n_selected_hits) / float(n_hits) * 100.)
        plot_timewalk(timewalk, xedges, yedges, title='Timewalk of sensor')

    plt.plot()


#     occ = in_file_h5.root.HistOcc[300:, :16, 0]
# plot_passive_cmos(occ, 'Am-241 hit map of LFoundry passive CMOS sensor on ATLAS FE-I4', z_title='#')
