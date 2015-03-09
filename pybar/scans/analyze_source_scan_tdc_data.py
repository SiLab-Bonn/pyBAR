''' This script does a full analysis of the TDC values taken during a source scan.
Two steps are done automatically:
Step 1 Tnterpret the raw data:
    Interpret the raw data from the FE, create and plot distributions of all provided raw data files.
    A cluster hit table is created. Do not forget to tell the interpreter if trigger numbers are expected.
Step 2 Histogram TDC of selected hits:
    Creates TDC histograms for each pixel from hits fullfilling certain criterions (e.g. 'is_seed==0', 'n_cluster==1') and create plots.
'''

import logging
import tables as tb
import numpy as np
import re
import os.path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.interpolate import interp1d

from pybar.analysis import analysis_utils
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plotThreeWay, plot_1d_hist


analysis_configuration = {
    'scan_name': ['/media/davidlp/Data/SCC167/scc_167/56_scc_167_ext_trigger_scan'],  # the base file name(s) of the raw data file, no file suffix needed
    'input_file_calibration': '/media/davidlp/Data/SCC167/scc_167/23_scc_167_hit_or_calibration_calibration.h5',  # the Plsr<->TDC calibration file
    'hit_selection_conditions': ['(n_cluster>=1) & (cluster_size>=1)',
                                 '(n_cluster==1) & (cluster_size==1)',  # criterions for the hit selection based on hit properties, per criterion one hitogram is created
                                 '(n_cluster==1) & (cluster_size==2)',
                                 '(n_cluster==1) & (cluster_size>2)',
                                 '(n_cluster>1)'],
    'event_status_select_mask': 0b0000011111011110,  # the event status bits to cut on
    'event_status_condition': 0b0000000100000010,  # the event status number after the event_status_select_mask is bitwise ORed with the event number
    'min_pixel_hits': 1e3,  # minimum number of hits a pixel must see to contribute to the 1d corrected TDC histogram
    "analysis_steps": [1, 2],  # the analysis includes this selected steps only. See explanation above.
    "max_tot_value": 13,  # maximum tot value to use the hit
    "interpreter_plots": True,  # set to False to omit the Raw Data plots, saves time
    "interpreter_warnings": False,  # show interpreter warnings
    "overwrite_output_files": True  # overwrite already existing files from former analysis
}


def analyze_raw_data(input_files, output_file_hits, interpreter_plots, pdf_filename):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    if os.path.isfile(output_file_hits) and not analysis_configuration['overwrite_output_files']:  # skip analysis if already done
        logging.info('Analyzed data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        with AnalyzeRawData(raw_data_file=input_files, analyzed_data_file=output_file_hits) as analyze_raw_data:
            # analyze_raw_data.use_trigger_number = False  # use the trigger number to align the events
            # analyze_raw_data.use_trigger_time_stamp = True # trigger numbers are time stamp
            analyze_raw_data.use_tdc_trigger_time_stamp = False  # if you want to also measure the delay between trigger / hit-bus
            analyze_raw_data.interpreter.debug_events(0, 4, False)
            analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
            analyze_raw_data.create_tdc_counter_hist = True  # create a histogram for all TDC words
            analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
            analyze_raw_data.create_tdc_pixel_hist = True
            analyze_raw_data.create_tot_pixel_hist = True
            analyze_raw_data.create_cluster_hit_table = True  # enables the creation of a table with all cluster hits, std. setting is false
            analyze_raw_data.create_source_scan_hist = True  # create source scan hists
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.max_tot_value = analysis_configuration['max_tot_value']  # set the maximum ToT value considered to be a hit, 14 is a late hit
            analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.interpret_word_table()  # the actual start conversion command
            analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
            if interpreter_plots:
                analyze_raw_data.plot_histograms(pdf_filename=pdf_filename)  # plots all activated histograms into one pdf


def histogram_tdc_hits(input_file_hits, hit_selection_conditions, event_status_select_mask, event_status_condition, calibation_file=None, max_tdc=2000, n_bins=1000):
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

    def plot_hits_per_condition(output_pdf):
        logging.info('Create hits selection efficiency histogram for %d conditions', len(hit_selection_conditions) + 2)
        labels = ['All Hits', 'Hits of\ngood events']
        for condition in hit_selection_conditions:
            condition = re.sub('[&]', '\n', condition)
            condition = re.sub('[()]', '', condition)
            labels.append(condition)
        plt.bar(range(len(n_hits_per_condition)), n_hits_per_condition, align='center')
        plt.xticks(range(len(n_hits_per_condition)), labels, size=8)
        plt.title('Number of hits for different cuts')
        plt.ylabel('#')
        plt.grid()
        for x, y in zip(np.arange(len(n_hits_per_condition)), n_hits_per_condition):
            plt.annotate('%d' % (float(y) / float(n_hits_per_condition[0]) * 100.) + r'%', xy=(x, y / 2.), xycoords='data', color='grey', size=15)
        output_pdf.savefig()

    def plot_corrected_tdc_hist(x, y, title, output_pdf):
        logging.info('Plot TDC hist with per pixel correction')
        plt.clf()
        plt.plot(x, y / np.amax(y), '-')
        plt.title(title, size=10)
        plt.xlabel('Charge [PlsrDAC]')
        plt.ylabel('Count [a.u.]')
        plt.grid()
        output_pdf.savefig()

    # Create data
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        cluster_hit_table = in_hit_file_h5.root.ClusterHits

        # Result hists, initialized per condition
        pixel_tdc_hists_per_condition = [np.zeros(shape=(80, 336, max_tdc), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        pixel_tdc_timestamp_hists_per_condition = [np.zeros(shape=(80, 336, 256), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_pixel_tdc_hists_per_condition = [np.zeros(shape=(80, 336), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_pixel_tdc_timestamp_hists_per_condition = [np.zeros(shape=(80, 336), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        tdc_hists_per_condition = [np.zeros(shape=(max_tdc), dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []

        n_hits_per_condition = [0 for _ in range(len(hit_selection_conditions) + 2)]  # condition 1, 2 are all hits, hits of goode events

        logging.info('Select hits and create TDC histograms for %d cut conditions', len(hit_selection_conditions))
        for cluster_hits, _ in analysis_utils.data_aligned_at_events(cluster_hit_table, chunk_size=2e7):
            n_hits_per_condition[0] += cluster_hits.shape[0]
            selected_events_cluster_hits = cluster_hits[(cluster_hits['event_status'] & event_status_select_mask) == event_status_condition]
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

        # Take TDC calibration if available and calculate charge for each TDC value and pixel
        if calibation_file is not None:
            with tb.openFile(calibation_file, mode="r") as in_file_calibration_h5:
                tdc_calibration = in_file_calibration_h5.root.HitOrCalibration[:, :, :, 1]
                tdc_calibration_values = in_file_calibration_h5.root.HitOrCalibration.attrs.scan_parameter_values[:]
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
                # Create result hists
                out_1 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcCondition_%d' % index, title='Hist Pixel Tdc with %s' % condition, atom=tb.Atom.from_dtype(pixel_tdc_hist_result.dtype), shape=pixel_tdc_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_2 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcTimestampCondition_%d' % index, title='Hist Pixel Tdc Timestamp with %s' % condition, atom=tb.Atom.from_dtype(pixel_tdc_timestamp_hist_result.dtype), shape=pixel_tdc_timestamp_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_3 = out_file_h5.createCArray(out_file_h5.root, name='HistMeanPixelTdcCondition_%d' % index, title='Hist Mean Pixel Tdc with %s' % condition, atom=tb.Atom.from_dtype(mean_pixel_tdc_hist_result.dtype), shape=mean_pixel_tdc_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_4 = out_file_h5.createCArray(out_file_h5.root, name='HistMeanPixelTdcTimestampCondition_%d' % index, title='Hist Mean Pixel Tdc Timestamp with %s' % condition, atom=tb.Atom.from_dtype(mean_pixel_tdc_timestamp_hist_result.dtype), shape=mean_pixel_tdc_timestamp_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_5 = out_file_h5.createCArray(out_file_h5.root, name='HistTdcCondition_%d' % index, title='Hist Tdc with %s' % condition, atom=tb.Atom.from_dtype(tdc_hists_per_condition_result.dtype), shape=tdc_hists_per_condition_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                # Add result hists information
                out_1.attrs.dimensions, out_1.attrs.condition, out_1.attrs.tdc_values = 'column, row, TDC value', condition, range(max_tdc)
                out_2.attrs.dimensions, out_2.attrs.condition, out_2.attrs.tdc_values = 'column, row, TDC time stamp value', condition, range(256)
                out_3.attrs.dimensions, out_3.attrs.condition = 'column, row, mean TDC value', condition
                out_4.attrs.dimensions, out_4.attrs.condition = 'column, row, mean TDC time stamp value', condition
                out_5.attrs.dimensions, out_5.attrs.condition = 'PlsrDAC', condition
                out_1[:], out_2[:], out_3[:], out_4[:], out_5[:] = pixel_tdc_hist_result, pixel_tdc_timestamp_hist_result, mean_pixel_tdc_hist_result, mean_pixel_tdc_timestamp_hist_result, tdc_hists_per_condition_result

                if charge_calibration is not None:
                    x, y = np.ravel(charge_calibration[:, :, :max_tdc]), np.ravel(pixel_tdc_hist_result[:, :, :max_tdc].swapaxes(0, 1))
                    y, x = y[x > 0], x[x > 0]  # reduce by TDC entries without proper calibration
                    x, y, yerr = analysis_utils.get_profile_histogram(x, y, n_bins=n_bins)
                    result_array = np.rec.array(np.column_stack((x, y, yerr)), dtype=[('charge', float), ('count', float), ('count_error', float)])
                    out_6 = out_file_h5.create_table(out_file_h5.root, name='HistTdcCalibratedCondition_%d' % index, description=result_array.dtype, title='Hist Tdc with charge calibration and %s' % condition, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out_6.attrs.condition = condition
                    out_6.append(result_array)

    # Plot Data
    with PdfPages(input_file_hits[:-3] + '_calibrated_tdc_hists.pdf') as output_pdf:
        plot_hits_per_condition(output_pdf)
        with tb.open_file(input_file_hits[:-3] + '_tdc_hists.h5', mode="r") as in_file_h5:
            for node in in_file_h5.root:  # go through the data and plot them
                if 'MeanPixel' in node.name:
                    plotThreeWay(np.ma.masked_invalid(node[:]) * 1.5625, title='Mean TDC delay, hits with %s' % node._v_attrs.condition if 'Timestamp' in node.name else 'Mean TDC, hits with %s' % node._v_attrs.condition, filename=output_pdf)
                elif 'HistTdcCondition' in node.name:
                    hist_1d = node[:]
                    max_index = np.amax(np.where(hist_1d != 0))
                    plot_1d_hist(hist_1d[:max_index + 10], title='TDC histogram, hits with %s' % node._v_attrs.condition if 'Timestamp' not in node.name else 'TDC time stamp histogram, hits with %s' % node._v_attrs.condition, x_axis_title='TDC' if 'Timestamp' not in node.name else 'TDC time stamp', filename=output_pdf)
                elif 'HistPixelTdc' in node.name:
                    hist_3d = node[:]
                    max_index = np.amax(np.where(hist_3d.sum(axis=(0, 1)) != 0))
                    best_pixel_index = np.where(hist_3d.sum(axis=2) == np.amax(node[:].sum(axis=2)))
                    if best_pixel_index[0].shape[0] == 1:
                        plot_1d_hist(hist_3d[best_pixel_index[0], best_pixel_index[1], :max_index][0], title='TDC histogram of pixel %d, %d' % (best_pixel_index[1], best_pixel_index[0]) if 'Timestamp' not in node.name else 'TDC time stamp histogram, hits of pixel %d, %d' % (best_pixel_index[1], best_pixel_index[0]), x_axis_title='TDC' if 'Timestamp' not in node.name else 'TDC time stamp', filename=output_pdf)
                elif 'HistTdcCalibratedCondition' in node.name:
                    plot_corrected_tdc_hist(node[:]['charge'], node[:]['count'], title='TDC histogram, per pixel charge calibration, %s' % node._v_attrs.condition, output_pdf=output_pdf)


if __name__ == "__main__":
    raw_data_files = analysis_utils.get_data_file_names_from_scan_base(analysis_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=False)
    logging.info('Found ' + str(len(raw_data_files)) + ' raw data file(s)')

    hit_file = analysis_configuration['scan_name'][0] + '_interpreted.h5'
    hit_cut_file = analysis_configuration['scan_name'][0] + '_cut_hits.h5'
    hit_cut_analyzed_file = analysis_configuration['scan_name'][0] + '_cut_hits_analyzed.h5'

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=raw_data_files, output_file_hits=hit_file, interpreter_plots=analysis_configuration['interpreter_plots'], pdf_filename=analysis_configuration['scan_name'][0])
    if 2 in analysis_configuration['analysis_steps']:
        histogram_tdc_hits(hit_file, hit_selection_conditions=analysis_configuration['hit_selection_conditions'], event_status_select_mask=analysis_configuration['event_status_select_mask'], event_status_condition=analysis_configuration['event_status_condition'], calibation_file=analysis_configuration['input_file_calibration'])
