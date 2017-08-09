''' This script changes the injection delay of the internal PlsrDAC (with global register PlsrDelay or PlsrIdacRamp, only PlsrDelay tested!)
and measures the mean BCID for each pixel (runtime ~ 1 h).

The PlsrDAC and injection delay values should be chosen equidistant and the lowest PlsrDAC value should be at threshold position!

The mean BCID changes for an increasing injection delay every 25 ns due to the 40 MHz clock in an S-curve like shape.
The mu of the S-curves is determined for different charges and for different BCIDs.
The change of the mu as a function of the charge is the timewalk that is calculated for each pixel.
The value of mu + mean BCID gives the absolute hit delay for the pixel.
Time walk and hit delay are calculated and plotted in different ways.
The analysis is quite complex, uses >> 1 Billion hits and takes 30 - 60 min.

The observation is that there is a dip in the hit delay curve, thus the fastest hits are not at the highest charge. This seems
to be a real measurement, carefull check shows this behavior for all pixels, a wrong injection delay calibration cannot explain the observation.
Although this is a real measurement this seems NOT to be a feature of the analog amplification, but a systematic measurement error that is introduced by the
PlsrDAC injection circuit. Because the direct hit delay measurements with a trigger + TDC time stamp do not show this behavior.
'''
import logging
import re
import multiprocessing as mp
import math
import warnings

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import tables as tb
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.interpolate import interp1d
from scipy.special import erf
warnings.simplefilter("ignore", OptimizeWarning)  # deactivate : Covariance warning

import progressbar

from pybar_fei4_interpreter.analysis_utils import hist_1d_index, hist_3d_index

from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.analysis.analysis_utils import get_hits_of_scan_parameter, get_scan_parameter, get_mean_from_histogram
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves, plot_three_way

warnings.simplefilter("ignore", OptimizeWarning)  # deactivate : Covariance warning


def scurve(x, offset, mu, sigma):
    return offset + 0.5 * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5


def fit_bcid_jumps(scurve_data, max_chi_2=2.0):  # Data of some pixels to fit, has to be global for the multiprocessing module
    offset_min = int(math.ceil(min(scurve_data)))  # Offset min is minimum BCID of Scurve fit
    offset_max = int(math.floor(max(scurve_data)))  # Offset max is minimum BCID of Scurve fit + 1

    if offset_max - offset_min > 2:  # Restrict to detection of two BCID jumps, otherwise most likely corrupt data
        offset_max = offset_min + 2
    index = range(len(scurve_data))
    result = -np.ones(4)
    for offset_index, offset in enumerate(xrange(offset_min, offset_max)):  # loop over up to two Scurves
        actual_index = [index[i] for i in index if offset <= scurve_data[i] <= offset + 1]
        if not actual_index or len(actual_index) < 5:  # Omit broken data
            continue
        actual_data = [scurve_data[i] for i in index if offset <= scurve_data[i] <= offset + 1]
        n_points_left = sum([1 for i in actual_data if i == offset])
        n_points_right = sum([1 for i in actual_data if i == offset + 1])
        if n_points_left < 2 or n_points_right < 2:  # Omit not sufficient data
            continue
        start_value = actual_index[np.argmax(np.diff(actual_data))]
        try:
            popt, _ = curve_fit(scurve, actual_index, actual_data, p0=[offset, start_value, 1.], check_finite=False)  # offset is also a fit parameter, since there are PlsrDAC settings that let the BCID jitter more
            if popt[1] > 0 and popt[0] > offset - 0.05:  # mu < 0 or too low offset indicates bad fit
                chi_2 = np.sum((scurve(actual_index, popt[0], popt[1], popt[2]) - actual_data) ** 2)
                if chi_2 < max_chi_2:  # Omit bad quality fits
                    result[offset_index * 2: offset_index * 2 + 1] = offset
                    result[offset_index * 2 + 1: offset_index * 2 + 2] = popt[1]
        except RuntimeError:  # Fit failed
            pass
    if result[0] == -1 and result[2] != -1:  # If the first scurve fit failed but not the second, define second s-curve as first
        result[0], result[1] = result[2], result[3]
        result[2], result[3] = -1, -1
    return result


def analyze_hit_delay(raw_data_file):
    # Interpret data and create hit table
    with AnalyzeRawData(raw_data_file=raw_data_file, create_pdf=False) as analyze_raw_data:
        analyze_raw_data.create_occupancy_hist = False  # Too many scan parameters to do in ram histogramming
        analyze_raw_data.create_hit_table = True
        analyze_raw_data.interpreter.set_warning_output(False)  # A lot of data produces unknown words
        analyze_raw_data.interpret_word_table()
        analyze_raw_data.interpreter.print_summary()
        # Store calibration values in variables
        vcal_c0 = analyze_raw_data.vcal_c0
        vcal_c1 = analyze_raw_data.vcal_c1
        c_high = analyze_raw_data.c_high

    # Create relative BCID and mean relative BCID histogram for each pixel / injection delay / PlsrDAC setting
    with tb.open_file(raw_data_file + '_analyzed.h5', mode="w") as out_file_h5:
        hists_folder = out_file_h5.create_group(out_file_h5.root, 'PixelHistsMeanRelBcid')
        hists_folder_2 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsRelBcid')
        hists_folder_3 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsTot')
        hists_folder_4 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsMeanTot')
        hists_folder_5 = out_file_h5.create_group(out_file_h5.root, 'HistsTot')

        def store_bcid_histograms(bcid_array, tot_array, tot_pixel_array):
            logging.debug('Store histograms for PlsrDAC ' + str(old_plsr_dac))
            bcid_mean_array = np.average(bcid_array, axis=3, weights=range(0, 16)) * sum(range(0, 16)) / np.sum(bcid_array, axis=3).astype('f4')  # calculate the mean BCID per pixel and scan parameter
            tot_pixel_mean_array = np.average(tot_pixel_array, axis=3, weights=range(0, 16)) * sum(range(0, 16)) / np.sum(tot_pixel_array, axis=3).astype('f4')  # calculate the mean tot per pixel and scan parameter
            bcid_mean_result = np.swapaxes(bcid_mean_array, 0, 1)
            bcid_result = np.swapaxes(bcid_array, 0, 1)
            tot_pixel_result = np.swapaxes(tot_pixel_array, 0, 1)
            tot_mean_pixel_result = np.swapaxes(tot_pixel_mean_array, 0, 1)

            out = out_file_h5.create_carray(hists_folder, name='HistPixelMeanRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Mean relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_mean_result.dtype), shape=bcid_mean_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out.attrs.dimensions = 'column, row, injection delay'
            out.attrs.injection_delay_values = injection_delay
            out[:] = bcid_mean_result
            out_2 = out_file_h5.create_carray(hists_folder_2, name='HistPixelRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_result.dtype), shape=bcid_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_2.attrs.dimensions = 'column, row, injection delay, relative bcid'
            out_2.attrs.injection_delay_values = injection_delay
            out_2[:] = bcid_result
            out_3 = out_file_h5.create_carray(hists_folder_3, name='HistPixelTotPerDelayPlsrDac_%03d' % old_plsr_dac, title='Tot hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_pixel_result.dtype), shape=tot_pixel_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_3.attrs.dimensions = 'column, row, injection delay'
            out_3.attrs.injection_delay_values = injection_delay
            out_3[:] = tot_pixel_result
            out_4 = out_file_h5.create_carray(hists_folder_4, name='HistPixelMeanTotPerDelayPlsrDac_%03d' % old_plsr_dac, title='Mean tot hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_mean_pixel_result.dtype), shape=tot_mean_pixel_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_4.attrs.dimensions = 'column, row, injection delay'
            out_4.attrs.injection_delay_values = injection_delay
            out_4[:] = tot_mean_pixel_result
            out_5 = out_file_h5.create_carray(hists_folder_5, name='HistTotPlsrDac_%03d' % old_plsr_dac, title='Tot histogram for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_array.dtype), shape=tot_array.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_5.attrs.injection_delay_values = injection_delay
            out_5[:] = tot_array

        old_plsr_dac = None

        # Get scan parameters from interpreted file
        with tb.open_file(raw_data_file + '_interpreted.h5', 'r') as in_file_h5:
            scan_parameters_dict = get_scan_parameter(in_file_h5.root.meta_data[:])
            plsr_dac = scan_parameters_dict['PlsrDAC']
            hists_folder._v_attrs.plsr_dac_values = plsr_dac
            hists_folder_2._v_attrs.plsr_dac_values = plsr_dac
            hists_folder_3._v_attrs.plsr_dac_values = plsr_dac
            hists_folder_4._v_attrs.plsr_dac_values = plsr_dac
            injection_delay = scan_parameters_dict[scan_parameters_dict.keys()[1]]  # injection delay par name is unknown and should be in the inner loop
            scan_parameters = scan_parameters_dict.keys()

        bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.uint16)  # bcid array of actual PlsrDAC
        tot_pixel_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.uint16)  # tot pixel array of actual PlsrDAC
        tot_array = np.zeros((16,), dtype=np.uint32)  # tot array of actual PlsrDAC

        logging.info('Store histograms for PlsrDAC values ' + str(plsr_dac))
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=max(plsr_dac) - min(plsr_dac), term_width=80)

        for index, (parameters, hits) in enumerate(get_hits_of_scan_parameter(raw_data_file + '_interpreted.h5', scan_parameters, try_speedup=True, chunk_size=10000000)):
            if index == 0:
                progress_bar.start()  # Start after the event index is created to get reasonable ETA
            actual_plsr_dac, actual_injection_delay = parameters[0], parameters[1]
            column, row, rel_bcid, tot = hits['column'] - 1, hits['row'] - 1, hits['relative_BCID'], hits['tot']
            bcid_array_fast = hist_3d_index(column, row, rel_bcid, shape=(80, 336, 16))
            tot_pixel_array_fast = hist_3d_index(column, row, tot, shape=(80, 336, 16))
            tot_array_fast = hist_1d_index(tot, shape=(16,))

            if old_plsr_dac != actual_plsr_dac:  # Store the data of the actual PlsrDAC value
                if old_plsr_dac:  # Special case for the first PlsrDAC setting
                    store_bcid_histograms(bcid_array, tot_array, tot_pixel_array)
                    progress_bar.update(old_plsr_dac - min(plsr_dac))
                # Reset the histrograms for the next PlsrDAC setting
                bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.uint16)
                tot_pixel_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.uint16)
                tot_array = np.zeros((16,), dtype=np.uint32)
                old_plsr_dac = actual_plsr_dac
            injection_delay_index = np.where(np.array(injection_delay) == actual_injection_delay)[0][0]
            bcid_array[:, :, injection_delay_index, :] += bcid_array_fast
            tot_pixel_array[:, :, injection_delay_index, :] += tot_pixel_array_fast
            tot_array += tot_array_fast
        store_bcid_histograms(bcid_array, tot_array, tot_pixel_array)  # save histograms of last PlsrDAC setting
        progress_bar.finish()

    # Take the mean relative BCID histogram of each PlsrDAC value and calculate the delay for each pixel
    with tb.open_file(raw_data_file + '_analyzed.h5', mode="r+") as in_file_h5:
        hists_folder = in_file_h5.create_group(in_file_h5.root, 'PixelHistsBcidJumps')
        plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values

        # Info output with progressbar
        logging.info('Detect BCID jumps with pixel based S-Curve fits for PlsrDACs ' + str(plsr_dac_values))
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(plsr_dac_values), term_width=80)
        progress_bar.start()

        for index, node in enumerate(in_file_h5.root.PixelHistsMeanRelBcid):  # loop over all mean relative BCID hists for all PlsrDAC values and determine the BCID jumps
            actual_plsr_dac = int(re.search(r'\d+', node.name).group())  # actual node plsr dac value
            # Select the S-curves and interpolate Nans
            pixel_data = node[:, :, :]
            pixel_data_fixed = pixel_data.reshape(pixel_data.shape[0] * pixel_data.shape[1] * pixel_data.shape[2])  # Reshape for interpolation of Nans
            nans, x = ~np.isfinite(pixel_data_fixed), lambda z: z.nonzero()[0]
            pixel_data_fixed[nans] = np.interp(x(nans), x(~nans), pixel_data_fixed[~nans])  # interpolate Nans
            pixel_data_fixed = pixel_data_fixed.reshape(pixel_data.shape[0], pixel_data.shape[1], pixel_data.shape[2])  # Reshape after interpolation of Nans

            # Fit all BCID jumps per pixel (1 - 2 jumps expected) with multithreading
            pixel_data_shaped = pixel_data_fixed.reshape(pixel_data_fixed.shape[0] * pixel_data_fixed.shape[1], pixel_data_fixed.shape[2]).tolist()
            pool = mp.Pool()  # create as many workers as physical cores are available
            result_array = np.array(pool.map(fit_bcid_jumps, pixel_data_shaped))
            pool.close()
            pool.join()
            result_array = result_array.reshape(pixel_data_fixed.shape[0], pixel_data_fixed.shape[1], 4)

            # Store array to file
            out = in_file_h5.create_carray(hists_folder, name='PixelHistsBcidJumpsPlsrDac_%03d' % actual_plsr_dac, title='BCID jumps per pixel for PlsrDAC ' + str(actual_plsr_dac), atom=tb.Atom.from_dtype(result_array.dtype), shape=result_array.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out.attrs.dimensions = 'column, row, BCID first jump, delay first jump, BCID second jump, delay second jump'
            out[:] = result_array
            progress_bar.update(index)

    # Calibrate the step size of the injection delay and create absolute and relative (=time walk) hit delay histograms
    with tb.open_file(raw_data_file + '_analyzed.h5', mode="r+") as out_file_h5:
        # Calculate injection delay step size using the average difference of two Scurves of all pixels and plsrDAC settings and the minimum BCID to fix the absolute time scale
        differences = np.zeros(shape=(336, 80, sum(1 for _ in out_file_h5.root.PixelHistsBcidJumps)), dtype=np.float)
        min_bcid = 15
        for index, node in enumerate(out_file_h5.root.PixelHistsBcidJumps):  # Loop to get last node (the node with most charge injected)
            pixel_data = node[:, :, :]
            selection = (np.logical_and(pixel_data[:, :, 0] > 0, pixel_data[:, :, 2] > 0))  # select pixels with two Scurve fits
            difference = np.zeros_like(differences[:, :, 0])
            difference[selection] = pixel_data[selection, 3] - pixel_data[selection, 1]  # Difference in delay settings between the scurves
            difference[np.logical_or(difference < 15, difference > 60)] = 0  # Get rid of bad data leading to difference that is too small / large
            differences[:, :, index] = difference
            if np.any(pixel_data[selection, 0]) and np.min(pixel_data[selection, 0]) < min_bcid:  # Search for the minimum rel. BCID delay (= fastes hits)
                min_bcid = np.amin(pixel_data[selection, 0])

        differences = np.ma.masked_where(np.logical_or(differences == 0, ~np.isfinite(differences)), differences)

        step_size = np.ma.median(differences)  # Delay steps needed for 25 ns
        step_size_error = np.ma.std(differences)  # Delay steps needed for 25 ns

        logging.info('Mean step size for the PLsrDAC delay is %1.2f +-  %1.2f ns', 25. / step_size, 25. / step_size ** 2 * step_size_error)

        # Calculate the hit delay per pixel
        plsr_dac_values = out_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values
        hit_delay = np.zeros(shape=(336, 80, len(plsr_dac_values)), dtype=np.float)  # Result array
        for node in out_file_h5.root.PixelHistsBcidJumps:  # loop over all BCID jump hists for all PlsrDAC values to calculate the hit delay
            actual_plsr_dac = int(re.search(r'\d+', node.name).group())  # actual node plsr dac value
            plsr_dac_index = np.where(plsr_dac_values == actual_plsr_dac)[0][0]
            pixel_data = node[:, :, :]
            actual_hit_delay = (pixel_data[:, :, 0] - min_bcid + 1) * 25. - pixel_data[:, :, 1] * 25. / step_size
            hit_delay[:, :, plsr_dac_index] = actual_hit_delay
        hit_delay = np.ma.masked_less(hit_delay, 0)
        timewalk = hit_delay - np.amin(hit_delay, axis=2)[:, :, np.newaxis]  # Time walk calc. by normalization to minimum hit delay for every pixel

        # Calculate the mean TOT per PlsrDAC (additional information, not needed for hit delay)
        tot = np.zeros(shape=(len(plsr_dac_values),), dtype=np.float16)  # Result array
        for node in out_file_h5.root.HistsTot:  # Loop over tot hist for all PlsrDAC values
            plsr_dac = int(re.search(r'\d+', node.name).group())
            plsr_dac_index = np.where(plsr_dac_values == plsr_dac)[0][0]
            tot_data = node[:]
            tot[plsr_dac_index] = get_mean_from_histogram(tot_data, range(16))

        # Store the data
        out = out_file_h5.create_carray(out_file_h5.root, name='HistPixelTimewalkPerPlsrDac', title='Time walk per pixel and PlsrDAC', atom=tb.Atom.from_dtype(timewalk.dtype), shape=timewalk.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        out_2 = out_file_h5.create_carray(out_file_h5.root, name='HistPixelHitDelayPerPlsrDac', title='Hit delay per pixel and PlsrDAC', atom=tb.Atom.from_dtype(hit_delay.dtype), shape=hit_delay.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        out_3 = out_file_h5.create_carray(out_file_h5.root, name='HistTotPerPlsrDac', title='Tot per PlsrDAC', atom=tb.Atom.from_dtype(tot.dtype), shape=tot.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        out.attrs.dimensions = 'column, row, PlsrDAC'
        out.attrs.delay_calibration = step_size
        out.attrs.delay_calibration_error = step_size_error
        out.attrs.plsr_dac_values = plsr_dac_values
        out_2.attrs.dimensions = 'column, row, PlsrDAC'
        out_2.attrs.delay_calibration = step_size
        out_2.attrs.delay_calibration_error = step_size_error
        out_2.attrs.plsr_dac_values = plsr_dac_values
        out_3.attrs.dimensions = 'PlsrDAC'
        out_3.attrs.plsr_dac_values = plsr_dac_values
        out[:] = timewalk.filled(fill_value=np.NaN)
        out_2[:] = hit_delay.filled(fill_value=np.NaN)
        out_3[:] = tot

    # Mask the pixels that have non valid data and create plots with the time walk and hit delay for all pixels
    with tb.open_file(raw_data_file + '_analyzed.h5', mode="r") as in_file_h5:
        def plsr_dac_to_charge(plsr_dac, vcal_c0, vcal_c1, c_high):  # Calibration values are taken from file
            voltage = vcal_c0 + vcal_c1 * plsr_dac
            return voltage * c_high / 0.16022

        def plot_hit_delay(hist_3d, charge_values, title, xlabel, ylabel, filename, threshold=None, tot_values=None):
            # Interpolate tot values for second tot axis
            interpolation = interp1d(tot_values, charge_values, kind='slinear', bounds_error=True)
            tot = np.arange(16)
            tot = tot[np.logical_and(tot >= np.min(tot_values), tot <= np.max(tot_values))]

            array = np.transpose(hist_3d, axes=(2, 1, 0)).reshape(hist_3d.shape[2], hist_3d.shape[0] * hist_3d.shape[1])
            y = np.mean(array, axis=1)
            y_err = np.std(array, axis=1)

            fig = Figure()
            FigureCanvas(fig)
            ax = fig.add_subplot(111)
            fig.patch.set_facecolor('white')
            ax.grid(True)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_xlim((0, np.max(charge_values)))
            ax.set_ylim((np.min(y - y_err), np.max(y + y_err)))
            ax.plot(charge_values, y, '.-', color='black', label=title)
            if threshold is not None:
                ax.plot([threshold, threshold], [np.min(y - y_err), np.max(y + y_err)], linestyle='--', color='black', label='Threshold\n%d e' % (threshold))
            ax.fill_between(charge_values, y - y_err, y + y_err, color='gray', alpha=0.5, facecolor='gray', label='RMS')
            ax2 = ax.twiny()
            ax2.set_xlabel("ToT")

            ticklab = ax2.xaxis.get_ticklabels()[0]
            trans = ticklab.get_transform()
            ax2.xaxis.set_label_coords(np.max(charge_values), 1, transform=trans)
            ax2.set_xlim(ax.get_xlim())
            ax2.set_xticks(interpolation(tot))
            ax2.set_xticklabels([str(int(i)) for i in tot])
            ax.text(0.5, 1.07, title, horizontalalignment='center', fontsize=18, transform=ax2.transAxes)
            ax.legend()
            filename.savefig(fig)

        plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values
        charge_values = plsr_dac_to_charge(np.array(plsr_dac_values), vcal_c0, vcal_c1, c_high)
        hist_timewalk = in_file_h5.root.HistPixelTimewalkPerPlsrDac[:, :, :]
        hist_hit_delay = in_file_h5.root.HistPixelHitDelayPerPlsrDac[:, :, :]
        tot = in_file_h5.root.HistTotPerPlsrDac[:]

        hist_timewalk = np.ma.masked_invalid(hist_timewalk)
        hist_hit_delay = np.ma.masked_invalid(hist_hit_delay)

        output_pdf = PdfPages(raw_data_file + '_analyzed.pdf')
        plot_hit_delay(np.swapaxes(hist_timewalk, 0, 1), charge_values=charge_values, title='Time walk', xlabel='Charge [e]', ylabel='Time walk [ns]', filename=output_pdf, threshold=np.amin(charge_values), tot_values=tot)
        plot_hit_delay(np.swapaxes(hist_hit_delay, 0, 1), charge_values=charge_values, title='Hit delay', xlabel='Charge [e]', ylabel='Hit delay [ns]', filename=output_pdf, threshold=np.amin(charge_values), tot_values=tot)
        plot_scurves(np.swapaxes(hist_timewalk, 0, 1), scan_parameters=charge_values, title='Timewalk of the FE-I4', scan_parameter_name='Charge [e]', ylabel='Timewalk [ns]', min_x=0, filename=output_pdf)
        plot_scurves(np.swapaxes(hist_hit_delay[:, :, :], 0, 1), scan_parameters=charge_values, title='Hit delay (T0) with internal charge injection\nof the FE-I4', scan_parameter_name='Charge [e]', ylabel='Hit delay [ns]', min_x=0, filename=output_pdf)

        for i in [0, 1, len(plsr_dac_values) / 4, len(plsr_dac_values) / 2, -1]:  # Plot 2d hist at min, 1/4, 1/2, max PlsrDAC setting
            plot_three_way(hist_timewalk[:, :, i], title='Time walk at %.0f e' % (charge_values[i]), x_axis_title='Time walk [ns]', filename=output_pdf)
            plot_three_way(hist_hit_delay[:, :, i], title='Hit delay (T0) with internal charge injection at %.0f e' % (charge_values[i]), x_axis_title='Hit delay [ns]', minimum=np.amin(hist_hit_delay[:, :, i]), maximum=np.max(hist_hit_delay[:, :, i]), filename=output_pdf)
        output_pdf.close()


class HitDelayScan(Fei4RunBase):

    '''Standard Hit Delay Scan

    Implementation of a hit delay scan.
    '''
    _default_run_conf = {
        "broadcast_commands": True,
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "n_injections": 20,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', range(21, 801, 15)), ('PlsrDelay', range(1, 63))],  # make sure to set the lowest PlsrDAC to the threshold position!
        "step_size": 1,  # step size of the PlsrDelay during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        delay_parameter_name = self.scan_parameters._fields[1]
        logging.info("Scanning PlsrDAC = %s and %s = %s", str(self.scan_parameters[0]), delay_parameter_name, str(self.scan_parameters[1]))

        plsr_dac_values = self.scan_parameters.PlsrDAC[:]  # create deep copy of scan_parameters, they are overwritten in self.readout
        delay_parameter_values = self.scan_parameters.PlsrDelay[:]  # create deep copy of scan_parameters, they are overwritten in self.readout

        for plsr_dac_value in plsr_dac_values:
            # Change the Plsr DAC parameter
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value('PlsrDAC', plsr_dac_value)
            commands.extend(self.register.get_commands("WrRegister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)
            for delay_parameter_value in delay_parameter_values:  # Loop over the Plsr delay parameter
                if self.stop_run.is_set():
                    break

                # Change the Plsr delay parameter
                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value(delay_parameter_name, delay_parameter_value)
                commands.extend(self.register.get_commands("WrRegister", name=[delay_parameter_name]))
                self.register_utils.send_commands(commands)

                cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

                with self.readout(plsr_dac_value, delay_parameter_value):
                    scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
        analyze_hit_delay(self.output_filename)


if __name__ == "__main__":
    RunManager('..\configuration.yaml').run_run(HitDelayScan)
#     analyze_hit_delay(r'L:\hitdelay\2_scc_99_hit_delay_scan')
