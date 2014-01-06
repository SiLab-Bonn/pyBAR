import numpy as np
import tables as tb
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from scipy.special import erf
from scipy.optimize import curve_fit

from analysis.plotting.plotting import plot_profile_histogram, plot_scatter, plot_occupancy
from analysis import analysis_utils

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def scurve(x, A, mu, sigma):
    return 0.5 * (1 - A) * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5 * A


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


def select_hot_region(hits, cut_threshold=0.8):
    '''Takes the hit array and masks all pixels with occupancy < (max_occupancy-min_occupancy) * cut_threshold.

    Parameters
    ----------
    hits : array like
        If dim > 2 the additional dimensions are summed up.
    mean_threshold : float, [0, 1]
        A number to specify the threshold, which pixel to take. Pixels are masked if
        pixel_occupancy < mean_occupancy * mean_threshold

    Returns
    -------
    numpy.ma.array, shape=(80,336)
        The hits array with masked pixels.
    '''
    hits = np.sum(hits, axis=(-1)).astype('u8')
    return np.ma.masked_where(hits < cut_threshold * (np.amax(hits) - np.amin(hits)), hits)

if __name__ == "__main__":
    scan_name = 'scan_fei4_trigger_gdac_0'
    folder = 'K:\\data\\FE-I4\\ChargeRecoMethod\\'
    input_file_hits = folder + 'bias_20\\' + scan_name + "_cut_1_analyzed.h5"
    input_file_calibration = folder + 'calibration\\calibrate_threshold_gdac_SCC_99.h5'
    input_file_correction = folder + 'bias_20\\' + scan_name + "_cluster_sizes.h5"

    scan_name = 'bias_20\\scan_fei4_trigger_gdac_0'
    folder = 'K:\\data\\FE-I4\\ChargeRecoMethod\\'

    use_cluster_rate_correction = True

    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        with tb.openFile(input_file_hits, mode="r") as in_file_hits_h5:  # read scan data file from scan_fei4_trigger_gdac scan
            hits = in_file_hits_h5.root.HistOcc[:]
            mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
            threshold_calibration_table = in_file_calibration_h5.root.ThresholdCalibration[:]
            threshold_calibration_array = in_file_calibration_h5.root.HistThresholdCalibration[:]

            gdac_range_calibration = mean_threshold_calibration['gdac']
            gdac_range_source_scan = analysis_utils.get_scan_parameter(meta_data_array=in_file_hits_h5.root.meta_data[:])['GDAC']

            correction_factors = 1
            if use_cluster_rate_correction:
                correction_h5 = tb.openFile(input_file_correction, mode="r")
                cluster_size_histogram = correction_h5.root.AllHistClusterSize[:]
                correction_factors = get_hit_rate_correction(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_source_scan, cluster_size_histogram=cluster_size_histogram)

            logging.info('Analyzing source scan data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_source_scan), np.min(gdac_range_source_scan), np.max(gdac_range_source_scan), np.min(np.gradient(gdac_range_source_scan)), np.max(np.gradient(gdac_range_source_scan))))
            logging.info('Use calibration data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_calibration), np.min(gdac_range_calibration), np.max(gdac_range_calibration), np.min(np.gradient(gdac_range_calibration)), np.max(np.gradient(gdac_range_calibration))))

            pixel_thresholds = get_pixel_thresholds(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_calibration, threshold_calibration_array=threshold_calibration_array)  # interpolates the threshold at the source scan GDAC setting from the calibration
            pixel_hits = np.swapaxes(hits, 0, 1)  # create hit array with shape (col, row, ...)

            pixel_hits = pixel_hits * correction_factors

            # choose region with pixels that have a sufficient occupancy
            selected_pixel_hits = pixel_hits[~np.ma.getmaskarray(select_hot_region(pixel_hits)), :]  # reduce the data to pixels that are in the hot pixel region
            selected_pixel_thresholds = pixel_thresholds[~np.ma.getmaskarray(select_hot_region(pixel_hits)), :]  # reduce the data to pixels that are in the hot pixel region
            plot_occupancy(select_hot_region(pixel_hits), title='Select ' + str(len(selected_pixel_hits)) + ' pixels for analysis')

            # reshape to one dimension
            x = selected_pixel_thresholds.flatten()
            y = selected_pixel_hits.flatten()

            #nothing should be NAN, NAN is not supported yet
            if np.isnan(x).sum() > 0 or np.isnan(y).sum() > 0:
                logging.warning('There are pixels with NaN threshold or hit values, analysis will be wrong')

            # calculated profile histogram, fit scurve to it and plot results
            x_p, y_p, y_p_e = analysis_utils.get_profile_histogram(x, y, n_bins=100)  # profile histogram data
            plot_profile_histogram(x=x_p * 55., y=y_p / 100., n_bins=len(gdac_range_source_scan) / 2, title='\'Single hit cluster\'-rate for different pixel thresholds', x_label='Pixel threshold [e]', y_label='Single hit cluster rate [a.u.]')

            # fit Scurve and plot differentiated results
            popt, _ = curve_fit(scurve, x_p, y_p, sigma=y_p_e, p0=[11.5, 164, 73])  # fit scurve
            y_p_f = scurve(x_p, popt[0], popt[1], popt[2])  # calculate y from the fitted scurve function
            plt.plot(x_p * 55., -analysis_utils.central_difference(x_p, y_p), 'o')  # plot differentiated data
            plt.plot(x_p * 55., -analysis_utils.central_difference(x_p, y_p_f), '-')  # plot differentiated fit data
            plt.title('\'Single hit cluster\'-occupancy for different pixel thresholds')
            plt.xlabel('Pixel threshold [e]')
            plt.ylabel('Single hit cluster occupancy [a.u.]')
            plt.ylim((0, 8))
            plt.show()

            # calculate and plot mean results
            x_mean = get_mean_threshold(gdac_range_source_scan, mean_threshold_calibration)
            y_mean = selected_pixel_hits.mean(axis=(0))

            plot_scatter(x_mean * 55, y_mean, title='Mean single pixel cluster rate at different thresholds', x_label='mean threshold [e]', y_label='mean single pixel cluster rate')

    if use_cluster_rate_correction:
        correction_h5.close()
