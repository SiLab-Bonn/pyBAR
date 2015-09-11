''' This script does a full analysis of the TDC values taken during a source scan.
Two consecutive steps are done:
    Step 1: Tnterpret the raw data:
        Interpret the raw data from the FE, create and plot distributions of all provided raw data files.
        A cluster hit table is created. Do not forget to tell in the analysis_configuration to align at the trigger number (if trigger numbers are expected)
        or to align at the TDC word (if it is the first word of an event) and if you want to measure the TDC/trigger distance.
    Step 2: Histogram TDC of selected hits:
        Creates TDC histograms for each pixel from hits fullfilling certain criterions (e.g. 'is_seed==0', 'n_cluster==1') and create plots.
'''

import logging
import tables as tb
import progressbar
import numpy as np
import re
import os.path
import matplotlib.pyplot as plt
from matplotlib import colors, cm
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.backends.backend_pdf import PdfPages
from scipy.interpolate import interp1d

from pybar.analysis import analysis_utils
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_three_way, plot_1d_hist

hit_selection = '(column > 50) & (column < 78) & (row > 16) & (row < 324) & (((column % 2 == 1) & (row % 12 == 1)) | ((column % 2 == 0) & (row % 12 == 7)))'

analysis_configuration = {
    'scan_name': [r'L:\SCC30\TDC_Sr90\LongRun\2_scc_30_ext_trigger_scan'],  # the base file name(s) of the raw data file, no file suffix
    'align_at_trigger': True,  # align events to the trigger words, first event word has to be trigger word
    'align_at_tdc': False,  # align events to the tdc words, first event word has to be tdc word; not needed anymore for new pyBAR data
    'use_tdc_trigger_time_stamp': False,  # TDC + external trigger are used, thus fill the hit table with delay value between trigger and TDC (usefull for time walk measurements)
    'max_tdc_delay': 80,  # maximum TDC to trigger delay to consider the TDC word as a valid in-time event word; otherwise TDC word is neglected
    'input_file_calibration': r'L:\SCC30\TDCcalibration\scc_30\11_scc_30_hit_or_calibration_calibration.h5',  # the Plsr<->TDC calibration file
    'correct_calibration': r'L:\SCC112\TDC_ELSA\scc_112\19_scc_112_hit_or_calibration_calibration.h5',  # file name of another more actual calibration to be used to correct the calibration; changes are expected due to tempretature drifts
    'hit_selection_conditions': ['(n_cluster==1)',  # criterions for the hit selection based on hit properties, per criterion TDC hitograms are created
                                 '(n_cluster==1) & (cluster_size == 1) & %s' % hit_selection,
                                 '(n_cluster==1) & (cluster_size == 1) & (relative_BCID > 1) & (relative_BCID < 5) & ((tot > 12) | ((TDC * 1.5625 - tot * 25 < 100) & (tot * 25 - TDC * 1.5625 < 100))) & %s' % hit_selection
                                 ],
    'event_status_select_mask': 0b0000111111111111,  # the event status bits to cut on
    'event_status_condition': 0b0000000100000000,  # the event status number after the event_status_select_mask is bitwise ORed with the event number
    'max_tdc': 1000,
    'n_bins': 200,
    "analysis_steps": [1, 2],  # the analysis includes this selected steps only. See explanation above.
    "interpreter_plots": True,  # set to False to omit the Raw Data plots, saves time
    "interpreter_warnings": False,  # show interpreter warnings
    "overwrite_output_files": True  # overwrite already existing files from former analysis
}


def analyze_raw_data(input_files, output_file_hits, interpreter_plots, overwrite_output_files, pdf_filename, align_at_trigger=True, align_at_tdc=False, use_tdc_trigger_time_stamp=False, max_tdc_delay=80):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    if os.path.isfile(output_file_hits) and not overwrite_output_files:  # skip analysis if already done
        logging.info('Analyzed data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        with AnalyzeRawData(raw_data_file=input_files, analyzed_data_file=output_file_hits) as analyze_raw_data:
            analyze_raw_data.max_tdc_delay = max_tdc_delay  # max TDC delay to consider a valid in-time TDC word
            analyze_raw_data.use_tdc_trigger_time_stamp = use_tdc_trigger_time_stamp  # if you want to also measure the delay between trigger / hit-bus
            analyze_raw_data.align_at_trigger = align_at_trigger  # align events at TDC words, first word of event has to be a tdc word
            analyze_raw_data.align_at_tdc = align_at_tdc  # align events at TDC words, first word of event has to be a tdc word
            analyze_raw_data.create_tdc_counter_hist = True  # create a histogram for all TDC words
            analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
            analyze_raw_data.create_tdc_pixel_hist = True
            analyze_raw_data.create_tot_pixel_hist = True
            analyze_raw_data.create_cluster_hit_table = True  # enables the creation of a table with all cluster hits, std. setting is false
            analyze_raw_data.create_source_scan_hist = True  # create source scan hists
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.interpreter.print_status()
            analyze_raw_data.interpret_word_table()  # the actual start conversion command
            analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
            if interpreter_plots:
                analyze_raw_data.plot_histograms()  # plots all activated histograms into one pdf


def histogram_tdc_hits(input_file_hits, hit_selection_conditions, event_status_select_mask, event_status_condition, calibation_file=None, correct_calibration=None, max_tdc=analysis_configuration['max_tdc'], n_bins=analysis_configuration['n_bins']):
    for condition in hit_selection_conditions:
        logging.info('Histogram tdc hits with %s', condition)

    def get_charge(max_tdc, tdc_calibration_values, tdc_pixel_calibration):  # return the charge from calibration
        charge_calibration = np.zeros(shape=(80, 336, max_tdc))
        for column in range(80):
            for row in range(336):
                actual_pixel_calibration = tdc_pixel_calibration[column, row, :]
                if np.any(actual_pixel_calibration != 0) and np.all(np.isfinite(actual_pixel_calibration)):
                    interpolation = interp1d(x=actual_pixel_calibration, y=tdc_calibration_values, kind='slinear', bounds_error=False, fill_value=0)
                    charge_calibration[column, row, :] = interpolation(np.arange(max_tdc))
        return charge_calibration

    def plot_tdc_tot_correlation(data, condition, output_pdf):
        logging.info('Plot correlation histogram for %s', condition)
        plt.clf()
        data = np.ma.array(data, mask=(data <= 0))
        if np.ma.any(data > 0):
            cmap = cm.get_cmap('jet', 200)
            cmap.set_bad('w')
            plt.title('Correlation with %s' % condition)
            norm = colors.LogNorm()
            z_max = data.max(fill_value=0)
            plt.xlabel('TDC')
            plt.ylabel('TOT')
            im = plt.imshow(data, cmap=cmap, norm=norm, aspect='auto', interpolation='nearest')  # , norm=norm)
            divider = make_axes_locatable(plt.gca())
            plt.gca().invert_yaxis()
            cax = divider.append_axes("right", size="5%", pad=0.1)
            plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
            output_pdf.savefig()
        else:
            logging.warning('No data for correlation plotting for %s', condition)

    def plot_hits_per_condition(output_pdf):
        logging.info('Plot hits selection efficiency histogram for %d conditions', len(hit_selection_conditions) + 2)
        labels = ['All Hits', 'Hits of\ngood events']
        for condition in hit_selection_conditions:
            condition = re.sub('[&]', '\n', condition)
            condition = re.sub('[()]', '', condition)
            labels.append(condition)
        plt.clf()
        plt.bar(range(len(n_hits_per_condition)), n_hits_per_condition, align='center')
        plt.xticks(range(len(n_hits_per_condition)), labels, size=8)
        plt.title('Number of hits for different cuts')
        plt.yscale('log')
        plt.ylabel('#')
        plt.grid()
        for x, y in zip(np.arange(len(n_hits_per_condition)), n_hits_per_condition):
            plt.annotate('%d' % (float(y) / float(n_hits_per_condition[0]) * 100.) + r'%', xy=(x, y / 2.), xycoords='data', color='grey', size=15)
        output_pdf.savefig()

    def plot_corrected_tdc_hist(x, y, title, output_pdf, point_style='-'):
        logging.info('Plot TDC hist with TDC calibration')
        plt.clf()
        y /= np.amax(y) if y.shape[0] > 0 else y
        plt.plot(x, y, point_style)
        plt.title(title, size=10)
        plt.xlabel('Charge [PlsrDAC]')
        plt.ylabel('Count [a.u.]')
        plt.grid()
        output_pdf.savefig()

    def get_calibration_correction(tdc_calibration, tdc_calibration_values, filename_new_calibration):  # correct the TDC calibration with the TDC calib in filename_new_calibration by shifting the means
        with tb.open_file(filename_new_calibration, 'r') as in_file_2:
            charge_calibration_1, charge_calibration_2 = tdc_calibration, in_file_2.root.HitOrCalibration[:, :, :, 1]

            plsr_dacs = tdc_calibration_values
            if not np.all(plsr_dacs == in_file_2.root.HitOrCalibration._v_attrs.scan_parameter_values):
                raise NotImplementedError('The check calibration file has to have the same PlsrDAC values')

            valid_pixel = np.where(np.logical_and(charge_calibration_1.sum(axis=2) > 0, charge_calibration_2.sum(axis=2) > 0))  # valid pixel have a calibration in the new and the old calibration
            mean_charge_calibration = charge_calibration_2[valid_pixel].mean(axis=0)
            offset_mean = (charge_calibration_1[valid_pixel] - charge_calibration_2[valid_pixel]).mean(axis=0)

            dPlsrDAC_dTDC = analysis_utils.smooth_differentiation(plsr_dacs, mean_charge_calibration, order=3, smoothness=0, derivation=1)

            plt.clf()
            plt.plot(plsr_dacs, offset_mean / dPlsrDAC_dTDC, '.-', label='PlsrDAC')
            plt.plot(plsr_dacs, offset_mean, '.-', label='TDC')
            plt.grid()
            plt.xlabel('PlsrDAC')
            plt.ylabel('Mean calibration offset')
            plt.legend(loc=0)
            plt.title('Mean offset between TDC calibration data, old - new ')
            plt.show()
            return offset_mean

    # Create data
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        cluster_hit_table = in_hit_file_h5.root.ClusterHits

        # Result hists, initialized per condition
        pixel_tdc_hists_per_condition = [np.zeros(shape=(80, 336, max_tdc), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        pixel_tdc_timestamp_hists_per_condition = [np.zeros(shape=(80, 336, 256), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_pixel_tdc_hists_per_condition = [np.zeros(shape=(80, 336), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_pixel_tdc_timestamp_hists_per_condition = [np.zeros(shape=(80, 336), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        tdc_hists_per_condition = [np.zeros(shape=(max_tdc), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        tdc_corr_hists_per_condition = [np.zeros(shape=(max_tdc, 16), dtype=np.uint32) for _ in hit_selection_conditions] if hit_selection_conditions else []

        n_hits_per_condition = [0 for _ in range(len(hit_selection_conditions) + 2)]  # condition 1, 2 are all hits, hits of goode events

        logging.info('Select hits and create TDC histograms for %d cut conditions', len(hit_selection_conditions))
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=cluster_hit_table.shape[0], term_width=80)
        progress_bar.start()
        for cluster_hits, _ in analysis_utils.data_aligned_at_events(cluster_hit_table, chunk_size=10000000):
            n_hits_per_condition[0] += cluster_hits.shape[0]
            selected_events_cluster_hits = cluster_hits[np.logical_and(cluster_hits['TDC'] < max_tdc, (cluster_hits['event_status'] & event_status_select_mask) == event_status_condition)]
            n_hits_per_condition[1] += selected_events_cluster_hits.shape[0]
            for index, condition in enumerate(hit_selection_conditions):
                selected_cluster_hits = analysis_utils.select_hits(selected_events_cluster_hits, condition)
                n_hits_per_condition[2 + index] += selected_cluster_hits.shape[0]
                column, row, tdc = selected_cluster_hits['column'] - 1, selected_cluster_hits['row'] - 1, selected_cluster_hits['TDC']
                pixel_tdc_hists_per_condition[index] += analysis_utils.hist_3d_index(column, row, tdc, shape=(80, 336, max_tdc))
                mean_pixel_tdc_hists_per_condition[index] = np.average(pixel_tdc_hists_per_condition[index], axis=2, weights=range(0, max_tdc)) * np.sum(np.arange(0, max_tdc)) / pixel_tdc_hists_per_condition[index].sum(axis=2)
                tdc_timestamp = selected_cluster_hits['TDC_time_stamp']
                pixel_tdc_timestamp_hists_per_condition[index] += analysis_utils.hist_3d_index(column, row, tdc_timestamp, shape=(80, 336, 256))
                mean_pixel_tdc_timestamp_hists_per_condition[index] = np.average(pixel_tdc_timestamp_hists_per_condition[index], axis=2, weights=range(0, 256)) * np.sum(np.arange(0, 256)) / pixel_tdc_timestamp_hists_per_condition[index].sum(axis=2)
                tdc_hists_per_condition[index] = pixel_tdc_hists_per_condition[index].sum(axis=(0, 1))
                tdc_corr_hists_per_condition[index] += analysis_utils.hist_2d_index(tdc, selected_cluster_hits['tot'], shape=(max_tdc, 16))
            progress_bar.update(n_hits_per_condition[0])
        progress_bar.finish()

        # Take TDC calibration if available and calculate charge for each TDC value and pixel
        if calibation_file is not None:
            with tb.openFile(calibation_file, mode="r") as in_file_calibration_h5:
                tdc_calibration = in_file_calibration_h5.root.HitOrCalibration[:, :, :, 1]
                tdc_calibration_values = in_file_calibration_h5.root.HitOrCalibration.attrs.scan_parameter_values[:]
                if correct_calibration is not None:
                    tdc_calibration += get_calibration_correction(tdc_calibration, tdc_calibration_values, correct_calibration)
            charge_calibration = get_charge(max_tdc, tdc_calibration_values, tdc_calibration)
        else:
            charge_calibration = None

        # Store data of result histograms
        with tb.open_file(input_file_hits[:-3] + '_tdc_hists.h5', mode="w") as out_file_h5:
            for index, condition in enumerate(hit_selection_conditions):
                pixel_tdc_hist_result = np.swapaxes(pixel_tdc_hists_per_condition[index], 0, 1)
                pixel_tdc_timestamp_hist_result = np.swapaxes(pixel_tdc_timestamp_hists_per_condition[index], 0, 1)
                mean_pixel_tdc_hist_result = np.swapaxes(mean_pixel_tdc_hists_per_condition[index], 0, 1)
                mean_pixel_tdc_timestamp_hist_result = np.swapaxes(mean_pixel_tdc_timestamp_hists_per_condition[index], 0, 1)
                tdc_hists_per_condition_result = tdc_hists_per_condition[index]
                tdc_corr_hist_result = np.swapaxes(tdc_corr_hists_per_condition[index], 0, 1)
                # Create result hists
                out_1 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcCondition_%d' % index, title='Hist Pixel Tdc with %s' % condition, atom=tb.Atom.from_dtype(pixel_tdc_hist_result.dtype), shape=pixel_tdc_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_2 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcTimestampCondition_%d' % index, title='Hist Pixel Tdc Timestamp with %s' % condition, atom=tb.Atom.from_dtype(pixel_tdc_timestamp_hist_result.dtype), shape=pixel_tdc_timestamp_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_3 = out_file_h5.createCArray(out_file_h5.root, name='HistMeanPixelTdcCondition_%d' % index, title='Hist Mean Pixel Tdc with %s' % condition, atom=tb.Atom.from_dtype(mean_pixel_tdc_hist_result.dtype), shape=mean_pixel_tdc_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_4 = out_file_h5.createCArray(out_file_h5.root, name='HistMeanPixelTdcTimestampCondition_%d' % index, title='Hist Mean Pixel Tdc Timestamp with %s' % condition, atom=tb.Atom.from_dtype(mean_pixel_tdc_timestamp_hist_result.dtype), shape=mean_pixel_tdc_timestamp_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_5 = out_file_h5.createCArray(out_file_h5.root, name='HistTdcCondition_%d' % index, title='Hist Tdc with %s' % condition, atom=tb.Atom.from_dtype(tdc_hists_per_condition_result.dtype), shape=tdc_hists_per_condition_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_6 = out_file_h5.createCArray(out_file_h5.root, name='HistTdcCorrCondition_%d' % index, title='Hist Correlation Tdc/Tot with %s' % condition, atom=tb.Atom.from_dtype(tdc_corr_hist_result.dtype), shape=tdc_corr_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                # Add result hists information
                out_1.attrs.dimensions, out_1.attrs.condition, out_1.attrs.tdc_values = 'column, row, TDC value', condition, range(max_tdc)
                out_2.attrs.dimensions, out_2.attrs.condition, out_2.attrs.tdc_values = 'column, row, TDC time stamp value', condition, range(256)
                out_3.attrs.dimensions, out_3.attrs.condition = 'column, row, mean TDC value', condition
                out_4.attrs.dimensions, out_4.attrs.condition = 'column, row, mean TDC time stamp value', condition
                out_5.attrs.dimensions, out_5.attrs.condition = 'PlsrDAC', condition
                out_6.attrs.dimensions, out_6.attrs.condition = 'TDC, TOT', condition
                out_1[:], out_2[:], out_3[:], out_4[:], out_5[:], out_6[:] = pixel_tdc_hist_result, pixel_tdc_timestamp_hist_result, mean_pixel_tdc_hist_result, mean_pixel_tdc_timestamp_hist_result, tdc_hists_per_condition_result, tdc_corr_hist_result

                if charge_calibration is not None:
                    # Select only valid pixel for histograming: they have data and a calibration (that is any charge(TDC) calibration != 0)
                    valid_pixel = np.where(np.logical_and(charge_calibration[:, :, :max_tdc].sum(axis=2) > 0, pixel_tdc_hist_result[:, :, :max_tdc].swapaxes(0, 1).sum(axis=2) > 0))

                    mean_charge_calibration = charge_calibration[valid_pixel][:, :max_tdc].mean(axis=0)
                    mean_tdc_hist = pixel_tdc_hist_result.swapaxes(0, 1)[valid_pixel][:, :max_tdc].mean(axis=0)
                    result_array = np.rec.array(np.column_stack((mean_charge_calibration, mean_tdc_hist)), dtype=[('charge', float), ('count', float)])
                    out_6 = out_file_h5.create_table(out_file_h5.root, name='HistMeanTdcCalibratedCondition_%d' % index, description=result_array.dtype, title='Hist Tdc with mean charge calibration and %s' % condition, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out_6.attrs.condition = condition
                    out_6.attrs.n_pixel = valid_pixel[0].shape[0]
                    out_6.append(result_array)
                    # Create charge histogram with per pixel TDC(charge) calibration
                    x, y = charge_calibration[valid_pixel][:, :max_tdc].ravel(), np.ravel(pixel_tdc_hist_result.swapaxes(0, 1)[valid_pixel][:, :max_tdc].ravel())
                    y, x = y[x > 0], x[x > 0]  # remove the hit tdcs without proper calibration plsrDAC(TDC) calibration
                    x, y, yerr = analysis_utils.get_profile_histogram(x, y, n_bins=n_bins)
                    result_array = np.rec.array(np.column_stack((x, y, yerr)), dtype=[('charge', float), ('count', float), ('count_error', float)])
                    out_7 = out_file_h5.create_table(out_file_h5.root, name='HistTdcCalibratedCondition_%d' % index, description=result_array.dtype, title='Hist Tdc with per pixel charge calibration and %s' % condition, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out_7.attrs.condition = condition
                    out_7.attrs.n_pixel = valid_pixel[0].shape[0]
                    out_7.append(result_array)

    # Plot Data
    with PdfPages(input_file_hits[:-3] + '_calibrated_tdc_hists.pdf') as output_pdf:
        plot_hits_per_condition(output_pdf)
        with tb.open_file(input_file_hits[:-3] + '_tdc_hists.h5', mode="r") as in_file_h5:
            for node in in_file_h5.root:  # go through the data and plot them
                if 'MeanPixel' in node.name:
                    try:
                        plot_three_way(np.ma.masked_invalid(node[:]) * 1.5625, title='Mean TDC delay, hits with\n%s' % node._v_attrs.condition if 'Timestamp' in node.name else 'Mean TDC, hits with\n%s' % node._v_attrs.condition, filename=output_pdf)
                    except ValueError:
                        logging.warning('Cannot plot TDC delay')
                elif 'HistTdcCondition' in node.name:
                    hist_1d = node[:]
                    entry_index = np.where(hist_1d != 0)
                    if entry_index[0].shape[0] != 0:
                        max_index = np.amax(entry_index)
                    else:
                        max_index = max_tdc
                    plot_1d_hist(hist_1d[:max_index + 10], title='TDC histogram, hits with\n%s' % node._v_attrs.condition if 'Timestamp' not in node.name else 'TDC time stamp histogram, hits with\n%s' % node._v_attrs.condition, x_axis_title='TDC' if 'Timestamp' not in node.name else 'TDC time stamp', filename=output_pdf)
                elif 'HistPixelTdc' in node.name:
                    hist_3d = node[:]
                    entry_index = np.where(hist_3d.sum(axis=(0, 1)) != 0)
                    if entry_index[0].shape[0] != 0:
                        max_index = np.amax(entry_index)
                    else:
                        max_index = max_tdc
                    best_pixel_index = np.where(hist_3d.sum(axis=2) == np.amax(node[:].sum(axis=2)))
                    if best_pixel_index[0].shape[0] == 1:  # there could be more than one pixel with most hits
                        plot_1d_hist(hist_3d[best_pixel_index][0, :max_index], title='TDC histogram of pixel %d, %d\n%s' % (best_pixel_index[1] + 1, best_pixel_index[0] + 1, node._v_attrs.condition) if 'Timestamp' not in node.name else 'TDC time stamp histogram, hits of pixel %d, %d' % (best_pixel_index[1] + 1, best_pixel_index[0] + 1), x_axis_title='TDC' if 'Timestamp' not in node.name else 'TDC time stamp', filename=output_pdf)
                elif 'HistTdcCalibratedCondition' in node.name:
                    plot_corrected_tdc_hist(node[:]['charge'], node[:]['count'], title='TDC histogram, %d pixel, per pixel TDC calib.\n%s' % (node._v_attrs.n_pixel, node._v_attrs.condition), output_pdf=output_pdf)
                elif 'HistMeanTdcCalibratedCondition' in node.name:
                    plot_corrected_tdc_hist(node[:]['charge'], node[:]['count'], title='TDC histogram, %d pixel, mean TDC calib.\n%s' % (node._v_attrs.n_pixel, node._v_attrs.condition), output_pdf=output_pdf)
                elif 'HistTdcCorr' in node.name:
                    plot_tdc_tot_correlation(node[:], node._v_attrs.condition, output_pdf)

if __name__ == "__main__":
    raw_data_files = analysis_utils.get_data_file_names_from_scan_base(analysis_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=False)
    logging.info('Found ' + str(len(raw_data_files)) + ' raw data file(s)')

    hit_file = analysis_configuration['scan_name'][0] + '_interpreted.h5'
    hit_cut_file = analysis_configuration['scan_name'][0] + '_cut_hits.h5'
    hit_cut_analyzed_file = analysis_configuration['scan_name'][0] + '_cut_hits_analyzed.h5'

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=raw_data_files,
                         output_file_hits=hit_file,
                         interpreter_plots=analysis_configuration['interpreter_plots'],
                         overwrite_output_files=analysis_configuration['overwrite_output_files'],
                         pdf_filename=analysis_configuration['scan_name'][0],
                         align_at_trigger=analysis_configuration['align_at_trigger'],
                         align_at_tdc=analysis_configuration['align_at_tdc'],
                         use_tdc_trigger_time_stamp=analysis_configuration['use_tdc_trigger_time_stamp'],
                         max_tdc_delay=analysis_configuration['max_tdc_delay'])
    if 2 in analysis_configuration['analysis_steps']:
        histogram_tdc_hits(hit_file,
                           hit_selection_conditions=analysis_configuration['hit_selection_conditions'],
                           event_status_select_mask=analysis_configuration['event_status_select_mask'],
                           event_status_condition=analysis_configuration['event_status_condition'],
                           calibation_file=analysis_configuration['input_file_calibration'])
