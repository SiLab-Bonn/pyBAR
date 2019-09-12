"""A script that takes external trigger scan data where the TDC + TDC time stamp were activated and creates
time walk plots from the data.
"""
import logging

from matplotlib import pyplot as plt
from matplotlib import cm
import tables as tb
import numpy as np
from scipy.interpolate import interp1d

from tqdm import tqdm

from pybar.analysis import analysis_utils


def plsr_dac_to_charge(plsr_dac):
    return 72.16 * plsr_dac + 2777.63


def get_charge(max_tdc, tdc_calibration_values, tdc_pixel_calibration):  # Return the charge from calibration
    ''' Interpolatet the TDC calibration for each pixel from 0 to max_tdc'''
    charge_calibration = np.zeros(shape=(80, 336, max_tdc))
    for column in range(80):
        for row in range(336):
            actual_pixel_calibration = tdc_pixel_calibration[column, row, :]
            if np.any(actual_pixel_calibration != 0) and np.any(np.isfinite(actual_pixel_calibration)):
                selected_measurements = np.isfinite(actual_pixel_calibration)  # Select valid calibration steps
                selected_actual_pixel_calibration = actual_pixel_calibration[selected_measurements]
                selected_tdc_calibration_values = tdc_calibration_values[selected_measurements]
                interpolation = interp1d(x=selected_actual_pixel_calibration, y=selected_tdc_calibration_values, kind='slinear', bounds_error=False, fill_value=0)
                charge_calibration[column, row, :] = interpolation(np.arange(max_tdc))
    return charge_calibration


def get_charge_calibration(calibation_file, max_tdc):
    ''' Open the hit or calibration file and return the calibration per pixel'''
    with tb.open_file(calibation_file, mode="r") as in_file_calibration_h5:
        tdc_calibration = in_file_calibration_h5.root.HitOrCalibration[:, :, :, 1]
        tdc_calibration_values = in_file_calibration_h5.root.HitOrCalibration.attrs.scan_parameter_values[:]
    return get_charge(max_tdc, tdc_calibration_values, tdc_calibration)


def get_time_walk_hist(hit_file, charge_calibration, event_status_select_mask, event_status_condition, hit_selection_conditions, max_timesamp, max_tdc, max_charge):
    with tb.open_file(hit_file, 'r') as in_file_h5:
        cluster_hit_table = in_file_h5.root.ClusterHits

        logging.info('Select hits and create TDC histograms for %d cut conditions', len(hit_selection_conditions))
        pbar = tqdm(total=cluster_hit_table.shape[0], ncols=80)
        n_hits, n_selected_hits = 0, 0
        timewalk = np.zeros(shape=(200, max_timesamp), dtype=np.float32)
        for cluster_hits, _ in analysis_utils.data_aligned_at_events(cluster_hit_table, chunk_size=10000000):
            n_hits += cluster_hits.shape[0]
            selected_events_cluster_hits = cluster_hits[np.logical_and(cluster_hits['TDC'] < max_tdc, (cluster_hits['event_status'] & event_status_select_mask) == event_status_condition)]
            for _, condition in enumerate(hit_selection_conditions):
                selected_cluster_hits = analysis_utils.select_hits(selected_events_cluster_hits, condition)
                n_selected_hits += selected_cluster_hits.shape[0]
                column_index, row_index, tdc, tdc_timestamp = selected_cluster_hits['column'] - 1, selected_cluster_hits['row'] - 1, selected_cluster_hits['TDC'], selected_cluster_hits['TDC_time_stamp']

                # Charge values for each Col/Row/TDC tuple from per pixel charge calibration
                # and PlsrDAC calibration in electrons
                charge_values = plsr_dac_to_charge(charge_calibration[column_index, row_index, tdc]).astype(np.float32)

                actual_timewalk, xedges, yedges = np.histogram2d(charge_values, tdc_timestamp, bins=timewalk.shape, range=((0, max_charge), (0, max_timesamp)))
                timewalk += actual_timewalk

            pbar.update(n_hits - pbar.n)
        pbar.close()
        logging.info('Selected %d of %d hits = %1.1f percent', n_selected_hits, n_hits, float(n_selected_hits) / float(n_hits) * 100.0)
    return timewalk, xedges, yedges


def plot_timewalk(hist, xedges, yedges, title, max_charge, max_time_walk=50):
    yedges *= 1.5625  # One TDC time stamp are 1/640 MHZ = 1.5625 ns
    timewalks = (yedges[0:-1] + yedges[1:]) / 2.
    charges = (xedges[0:-1] + xedges[1:]) / 2.

    def get_mean_from_histogram(counts, bin_positions):
        return np.dot(counts, np.array(bin_positions)) / np.sum(counts).astype('f4')

    # Rebin for more smooth time walk means
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w', 1.0)
    hist = np.ma.masked_where(hist == 0, hist)

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

    # Time walk is relative, define lowest timewalk as
    # minimum mean time walk + 2 RMS of time walk spread of the pixels (here mean of 50 highest charge bins)
    zero_timewalk = np.ma.min(mean[-50:]) + 1 * np.ma.mean(std[-50:])

    percentages = []  # Percentages of hits for 5/10/15/... ns timewalk
    n_hits = np.ma.sum(hist)
    for timewalk_bin in range(0, max_time_walk + 1, 5):
        percentages.append(np.round(float(np.ma.sum(hist[:, np.where(timewalks <= zero_timewalk + timewalk_bin)])) / n_hits * 100.0, 1))

    mean -= zero_timewalk  # Time walk is relative

    plt.plot(charges, mean, '-', label='Mean')
    plt.yticks(np.arange(0, max_time_walk + 1, 5))  # One tick evety 5 ns
    plt.fill_between(charges, mean - np.array(std), mean + np.array(std), color='gray', alpha=0.5, facecolor='gray', label='RMS')

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
    # TDC scan data and hit or calibration file
    hit_file = r'15_cmos_passive_1_ext_trigger_scan_interpreted.h5'
    calibation_file = r'14_cmos_passive_1_hit_or_calibration_calibration.h5'

    # Select pixel and TDC region
    col_span = [1, 80]  # Pixel column range to use for time walk analysis
    row_span = [1, 336]  # Pixel row range to use for time walk analysis
    max_tdc = 500
    max_timesamp = 2000

    # Event and hit cuts
    event_status_select_mask = 0b0000111111111111,  # the event status bits to cut on
    event_status_condition = 0b0000000100000000
    hit_selection = '(column > %d) & (column < %d) & (row > %d) & (row < %d)' % (col_span[0] + 1, col_span[1] - 1, row_span[0] + 5, row_span[1] - 5)  # deselect edge pixels for better cluster size cut
    hit_selection_conditions = ['(n_cluster==1) & (cluster_size == 1) & (relative_BCID >= 1) & (relative_BCID <= 3) & ((tot > 12) | ((TDC * 1.5625 - tot * 25 < 100) & (tot * 25 - TDC * 1.5625 < 100))) & %s' % hit_selection]

    # Create charge calibration from hit or calibration
    charge_calibration = get_charge_calibration(calibation_file, max_tdc)
    max_charge = plsr_dac_to_charge(np.amax(charge_calibration))  # Correspond to max TDC, just needed for plotting

    # Create and plot time walk histogram
    timewalk_hist, xedges, yedges = get_time_walk_hist(hit_file,
                                                       charge_calibration,
                                                       event_status_select_mask,
                                                       event_status_condition,
                                                       hit_selection_conditions,
                                                       max_timesamp,
                                                       max_tdc,
                                                       max_charge)
    plot_timewalk(timewalk_hist, xedges, yedges, title='Time walk', max_charge=max_charge)
