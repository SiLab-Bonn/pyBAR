import numpy as np
import tables as tb
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt

from analysis.plotting.plotting import plot_scatter, plot_occupancy
from analysis import analysis_utils

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def get_mean_threshold(gdac, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['gdac'], mean_threshold_calibration['mean_threshold'], kind='slinear', bounds_error=True)
    return interpolation(gdac)


def get_pixel_thresholds_from_table(column, row, gdacs, threshold_calibration_table):
    pixel_gdacs = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['gdac']
    pixel_thresholds = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['threshold']
    interpolation = interp1d(x=pixel_gdacs, y=pixel_thresholds, kind='slinear', bounds_error=True)
    return interpolation(gdacs)


def get_pixel_thresholds(gdacs, calibration_gdacs, threshold_calibration_array):
    '''Calculates the threshold for all pixels in threshold_calibration_array at the given GDAC settings via linear interpolation. The GDAC settings used during calibration have to be given.

    Parameters
    ----------
    gdacs : array like
        The GDAC settings where the threshold should be determined from the calibration
    calibration_gdacs : array like
        GDAC settings used during calibration, needed to translate the index of the calibration array to a value.
    threshold_calibration_array : numpy.array, shape=(80,336,# of GDACs during calibration)
        The calibration array

    Returns
    -------
    numpy.array, shape=(80,336,# gdacs given)
        The threshold values for each pixel at gdacs.
    '''
    if len(calibration_gdacs) != threshold_calibration_array.shape[2]:
        raise ValueError('Length of the provided pixel GDACs does not match the third dimension of the calibration array')
    interpolation = interp1d(x=calibration_gdacs, y=threshold_calibration_array, kind='slinear', bounds_error=True)
    return interpolation(gdacs)


def get_hit_rate_correction(gdacs, calibration_gdacs, cluster_size_histogram):
    '''Calculates a correction factor for single hit clusters at the given GDACs from the cluster_size_histogram via cubic interpolation.

    Parameters
    ----------
    gdacs : array like
        The GDAC settings where the threshold should be determined from the calibration
    calibration_gdacs : array like
        GDAC settings used during the source scan for the cluster size calibration.
    cluster_size_histogram : numpy.array, shape=(80,336,# of GDACs during calibration)
        The calibration array

    Returns
    -------
    numpy.array, shape=(80,336,# of GDACs during calibration)
        The threshold values for each pixel at gdacs.
    '''

    logging.info('Calculate the correction factor for the single hit cluster rate at %d given GDAC settings' % len(gdacs))
    hist_sum = np.sum(cluster_size_histogram, axis=1)
    hist_rel = cluster_size_histogram / hist_sum[:, np.newaxis] * 100
    maximum_rate = np.amax(hist_rel[:, 1])
    correction_factor = maximum_rate / hist_rel[:, 1]
    interpolation = interp1d(calibration_gdacs, correction_factor, kind='cubic', bounds_error=True)
    return interpolation(gdacs)


def get_normalization(meta_data, reference='event'):
    gdacs = analysis_utils.get_scan_parameter(meta_data_array=meta_data)['GDAC']
    if reference == 'event':
        event_numbers = analysis_utils.get_meta_data_at_scan_parameter(meta_data, 'GDAC')['event_number']  # get the event numbers in meta_data where the scan parameter changes
        event_range = analysis_utils.get_event_range(event_numbers)
        event_range[-1, 1] = event_range[-2, 1]  # hack the last event range not to be None
        n_events = event_range[:, 1] - event_range[:, 0]  # number of events for every GDAC
        n_events[-1] = n_events[-2]  # FIXME: set the last number of events manually, bad extrapolaton
        logging.warning('Last number of events unknown and extrapolated')
        plot_scatter(gdacs, n_events, title='Events per GDAC setting', x_label='GDAC', y_label='# events', log_x=True)
        return n_events.astype('f64') / np.amax(n_events)
    else:
        time_start = analysis_utils.get_meta_data_at_scan_parameter(meta_data, 'GDAC')['timestamp_start']
        time_spend = np.diff(time_start)
        time_spend = np.append(time_spend, meta_data[-1]['timestamp_stop'] - time_start[-1])  # TODO: needs check, add last missing entry
        plot_scatter(gdacs, time_spend, title='Measuring time per GDAC setting', x_label='GDAC', y_label='time [s]', log_x=True)
        return time_spend.astype('f64') / np.amax(time_spend)


def plot_cluster_sizes(in_file_cluster_h5, in_file_calibration_h5, gdac_range, vcal_calibration):
    mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
    hist = in_file_cluster_h5.root.AllHistClusterSize[:]
    hist_sum = np.sum(hist, axis=1)
    hist_rel = hist / hist_sum[:, np.newaxis] * 100
    x = get_mean_threshold(gdac_range, mean_threshold_calibration)
    plt.grid(True)
    plt.plot(x * vcal_calibration, hist_rel[:, 1], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 2], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 3], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 4], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 5], '-o')
    plt.title('Frequency of different cluster sizes for different thresholds')
    plt.xlabel('threshold [e]')
    plt.ylabel('cluster size frequency [%]')
    plt.legend(["1 hit cluster", "2 hit cluster", "3 hit cluster", "4 hit cluster", "5 hit cluster"], loc='best')
#             plt.ylim(0, 100)
#             plt.xlim(0, 12000)
    fig = plt.gca()
    fig.patch.set_facecolor('white')
    plt.show()
    plt.close()


def plot_result(x_p, y_p, y_p_e):
    ''' Fit spline to the profile histogramed data, differentiate, determine MPV and plot.
     Parameters
    ----------
        x_p, y_p : array like
            data points (x,y)
        y_p_e : array like
            error bars in y
    '''
    smoothed_data = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=0)
    smoothed_data_diff = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=1)
    p1 = plt.errorbar(x_p * vcal_calibration, y_p, yerr=y_p_e, fmt='o')  # plot differentiated data with error bars of data
    p2, = plt.plot(x_p * vcal_calibration, smoothed_data, '-r')  # plot smoothed data
    p3, = plt.plot(x_p * vcal_calibration, -100. * smoothed_data_diff, '-', lw=2)  # plot differentiated data
    mpv_index = np.argmax(-analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=1))
    p4, = plt.plot([x_p[mpv_index] * vcal_calibration, x_p[mpv_index] * vcal_calibration], [0, -100. * smoothed_data_diff[mpv_index]], 'k-', lw=2)
    text = 'MPV ' + str(int(x_p[mpv_index] * vcal_calibration)) + ' e'
    plt.text(1.01 * x_p[mpv_index] * vcal_calibration, -10. * smoothed_data_diff[mpv_index], text, ha='left')
    plt.legend([p1, p2, p3, p4], ['data', 'smoothed spline', 'spline differentiation', text], prop={'size': 12})
    plt.title('\'Single hit cluster\'-occupancy for different pixel thresholds')
    plt.xlabel('Pixel threshold [e]')
    plt.ylabel('Single hit cluster occupancy [a.u.]')
    plt.ylim((0, 1.05 * np.amax(y_p)))
    plt.show()


def select_hot_region(hits, cut_threshold=0.8):
    '''Takes the hit array and masks all pixels with occupancy < (max_occupancy-min_occupancy) * cut_threshold.

    Parameters
    ----------
    hits : array like
        If dim > 2 the additional dimensions are summed up.
    cut_threshold : float, [0, 1]
        A number to specify the threshold, which pixel to take. Pixels are masked if
        occupancy < (max_occupancy-min_occupancy) * cut_threshold
        1 means that all pixels are masked
        0 means that no pixels are masked

    Returns
    -------
    numpy.ma.array, shape=(80,336)
        The hits array with masked pixels.
    '''
    hits = np.sum(hits, axis=(-1)).astype('u8')
    dimension = (80, 336)
    mask = np.ones(dimension, dtype=np.uint8)
            
    mask[20:60, 20:150] = 0  # advanced indexing
#     pixel_mask = np.logical_and(mask, pixel_mask)
    
    ma = np.ma.masked_where(hits < cut_threshold * (np.amax(hits) - np.amin(hits)), hits)
    return np.ma.masked_where(mask, ma)

if __name__ == "__main__":
    scan_name = 'scan_ext_trigger_gdac_0'
    folder = 'data\\'
    input_file_hits = folder + scan_name + "_cut_1_analyzed.h5"
    input_file_calibration = folder + 'calibrate_threshold_gdac_MDBM30.h5'
    input_file_correction = folder + scan_name + "_cluster_sizes.h5"

    use_cluster_rate_correction = True

    smoothness = 200  # the smoothness of the spline fit to the data
    vcal_calibration = 55.  # calibration electrons/PlsrDAC
    n_bins = 100  # number of bins for the profile histogram

    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        with tb.openFile(input_file_hits, mode="r") as in_file_hits_h5:  # read scan data file from scan_fei4_trigger_gdac scan
            hits = in_file_hits_h5.root.HistOcc[:]
            meta_data = in_file_hits_h5.root.meta_data[:]
            mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
            threshold_calibration_table = in_file_calibration_h5.root.ThresholdCalibration[:]
            threshold_calibration_array = in_file_calibration_h5.root.HistThresholdCalibration[:]

            gdac_range_calibration = mean_threshold_calibration['gdac']
            gdac_range_source_scan = analysis_utils.get_scan_parameter(meta_data_array=meta_data)['GDAC']

            normalization = get_normalization(meta_data, reference='event')  # normalize the number of hits for each GDAC setting, can be different due to different scan time

            correction_factors = 1
            if use_cluster_rate_correction:
                correction_h5 = tb.openFile(input_file_correction, mode="r")
                cluster_size_histogram = correction_h5.root.AllHistClusterSize[:]
                correction_factors = get_hit_rate_correction(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_source_scan, cluster_size_histogram=cluster_size_histogram)
                plot_cluster_sizes(correction_h5, in_file_calibration_h5, gdac_range=gdac_range_source_scan, vcal_calibration=vcal_calibration)

            logging.info('Analyzing source scan data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_source_scan), np.min(gdac_range_source_scan), np.max(gdac_range_source_scan), np.min(np.gradient(gdac_range_source_scan)), np.max(np.gradient(gdac_range_source_scan))))
            logging.info('Use calibration data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_calibration), np.min(gdac_range_calibration), np.max(gdac_range_calibration), np.min(np.gradient(gdac_range_calibration)), np.max(np.gradient(gdac_range_calibration))))

            pixel_thresholds = get_pixel_thresholds(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_calibration, threshold_calibration_array=threshold_calibration_array)  # interpolates the threshold at the source scan GDAC setting from the calibration
            pixel_hits = np.swapaxes(hits, 0, 1)  # create hit array with shape (col, row, ...)
            
            print pixel_thresholds.shape
            print pixel_thresholds[40, 80, :]

            normalization = 1.
            correction_factors = 1.
            pixel_hits = pixel_hits * correction_factors * normalization

            # choose region with pixels that have a sufficient occupancy
            hot_pixel = select_hot_region(pixel_hits, cut_threshold=0.01)
#             hot_pixel
            pixel_mask = ~np.ma.getmaskarray(hot_pixel)
            selected_pixel_hits = pixel_hits[pixel_mask, :]  # reduce the data to pixels that are in the hot pixel region
            selected_pixel_thresholds = pixel_thresholds[pixel_mask, :]  # reduce the data to pixels that are in the hot pixel region
            plot_occupancy(hot_pixel.T, title='Select ' + str(len(selected_pixel_hits)) + ' pixels for analysis')

            # reshape to one dimension
            x = selected_pixel_thresholds.flatten()
            y = selected_pixel_hits.flatten()
            
            plot_scatter(x * vcal_calibration, y, marker_style='o')
            
#             print x[:],y[:]
#  
#             #nothing should be NAN, NAN is not supported yet
#             if np.isnan(x).sum() > 0 or np.isnan(y).sum() > 0:
#                 logging.warning('There are pixels with NaN threshold or hit values, analysis will be wrong')
# 
# # 
# #             # calculated profile histogram
#             x_p, y_p, y_p_e = analysis_utils.get_profile_histogram(x, y, n_bins=n_bins)  # profile histogram data
# # 
# #             # select only the data point where the calibration worked
# #             selected_data = np.logical_or(x_p > 4840 / vcal_calibration, x_p < 4180 / vcal_calibration)
# #             x_p = x_p[selected_data]
# #             y_p = y_p[selected_data]
# #             y_p_e = y_p_e[selected_data]
#              
#             if np.isnan(x_p).sum() > 0 or np.isnan(y_p).sum() > 0 or np.isnan(y_p_e).sum() > 0:
#                 logging.error('There are pixels with NaN threshold or hit values, analysis will fail') 
#             print x_p
#             print y_p
#             print y_p_e
#             
# #             plt.plot(x_p, y_p)
# # 
#             plot_result(x_p, y_p, y_p_e)
# 
#             #  calculate and plot mean results
            x_mean = get_mean_threshold(gdac_range_source_scan, mean_threshold_calibration)
            y_mean = selected_pixel_hits.mean(axis=(0))

            plot_scatter(x_mean * 55, y_mean, title='Mean single pixel cluster rate at different thresholds', x_label='mean threshold [e]', y_label='mean single pixel cluster rate')

    if use_cluster_rate_correction:
        correction_h5.close()
