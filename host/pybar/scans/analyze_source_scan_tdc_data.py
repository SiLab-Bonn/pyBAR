''' This script does a full analysis of the TDC values taken during a source scan.
Two steps are done automatically:
Step 1 Tnterpret the raw data:
    Interpret the raw data from the FE, create and plot distributions of all provided raw data files.
    A cluster hit table is created. Do not forget to tell the interpreter if trigger numbers are expected.
Step 2 Histogram TDC of selected hits:
    Creates TDC histograms for each pixel from hits fullfilling certain criterions (e.g. 'is_seed==0', 'n_cluster==1')
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
from pybar.analysis.plotting.plotting import plotThreeWay


analysis_configuration = {
    'scan_name': ['D:\\data\\FE-I4\\SinglePixelCharge\\ana\\48_scc_30_ext_trigger_scan'],  # the base file name(s) of the raw data file, no file suffix needed
    'input_file_calibration': 'D:\\data\\FE-I4\\SinglePixelCharge\\61_scc_30_hit_or_calibration_calibration.h5',  # the Plsr<->TDC calibration file
    'hit_selection_conditions': ['(n_cluster==1)',  # criterions for the hit selection based on hit properties, per criterion one hitogram is created
                                 '(n_cluster==1) & (is_seed==0)',
                                 '(n_cluster==1) & (is_seed==1)'],
    'event_status_select_mask': 0b0000011111011111,  # the event status bits to cut on
    'event_status_condition': 0b0000000100000011,  # the event status number after the event_status_select_mask is bitwise ORed with the event number
    'min_pixel_hits': 1e3,  # minimum number of hits a pixel must see to contribute to the TDC histogram
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


def histogram_tdc_hits(input_file_hits, hit_selection_conditions, event_status_select_mask, event_status_condition, calibation_file=None, max_tdc=2000):
    for condition in hit_selection_conditions:
        logging.info('Histogram tdc hits with %s' % condition)

    def get_charge(max_tdc, tdc_calibration_values, tdc_pixel_calibration):  # return the charge from calibration
        charge_calibration = np.zeros(shape=(80, 336, max_tdc))
        for column in range(80):
            for row in range(336):
                actual_pixel_calibration = tdc_pixel_calibration[column, row, :]
                if np.any(actual_pixel_calibration != 0):
                    interpolation = interp1d(x=actual_pixel_calibration, y=tdc_calibration_values, kind='slinear', bounds_error=False, fill_value=0)
                    charge_calibration[column, row, :] = interpolation(np.arange(max_tdc))
        return charge_calibration

    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        cluster_hit_table = in_hit_file_h5.root.ClusterHits

        shape_tdc_hist, shape_mean_tdc_hist = (80, 336, max_tdc), (80, 336)
        shape_tdc_timestamp_hist, shape_mean_tdc_timestamp_hist = (80, 336, 256), (80, 336)
        tdc_hists_per_condition = [np.zeros(shape=shape_tdc_hist, dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        tdc_timestamp_hists_per_condition = [np.zeros(shape=shape_tdc_timestamp_hist, dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_tdc_hists_per_condition = [np.zeros(shape=shape_mean_tdc_hist, dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []
        mean_tdc_timestamp_hists_per_condition = [np.zeros(shape=shape_mean_tdc_timestamp_hist, dtype=np.uint16) for _ in hit_selection_conditions] if hit_selection_conditions else []

        n_hits_per_condition = [0 for _ in range(len(hit_selection_conditions) + 2)]  # 1/2 condition are all hits / hits of goode events

        for cluster_hits, _ in analysis_utils.data_aligned_at_events(cluster_hit_table, chunk_size=2e7):
            n_hits_per_condition[0] += cluster_hits.shape[0]
            selected_events_cluster_hits = cluster_hits[(cluster_hits['event_status'] & event_status_select_mask) == event_status_condition]
            n_hits_per_condition[1] += selected_events_cluster_hits.shape[0]
            for index, condition in enumerate(hit_selection_conditions):
                selected_cluster_hits = analysis_utils.select_hits(selected_events_cluster_hits, condition)
                n_hits_per_condition[2 + index] += selected_cluster_hits.shape[0]
                column, row, tdc = selected_cluster_hits['column'] - 1, selected_cluster_hits['row'] - 1, selected_cluster_hits['TDC']
                tdc_hists_per_condition[index] += analysis_utils.hist_3d_index(column, row, tdc, shape=shape_tdc_hist)
                mean_tdc_hists_per_condition[index] = np.average(tdc_hists_per_condition[index], axis=2, weights=range(0, max_tdc)) * np.sum(np.arange(0, max_tdc)) / tdc_hists_per_condition[index].sum(axis=2)
                tdc_timestamp = selected_cluster_hits['TDC_time_stamp']
                tdc_timestamp_hists_per_condition[index] += analysis_utils.hist_3d_index(column, row, tdc_timestamp, shape=shape_tdc_timestamp_hist)
                mean_tdc_timestamp_hists_per_condition[index] = np.average(tdc_timestamp_hists_per_condition[index], axis=2, weights=range(0, shape_tdc_timestamp_hist[2])) * np.sum(np.arange(0, shape_tdc_timestamp_hist[2])) / tdc_timestamp_hists_per_condition[index].sum(axis=2)

        plotThreeWay(mean_tdc_hists_per_condition[0].T * 1.5625, title='Mean TDC, condition 1', filename='test_tdc.pdf')  # , minimum=50, maximum=250)
        plotThreeWay(mean_tdc_timestamp_hists_per_condition[0].T * 1.5625, title='Mean TDC delay, condition 1', filename='test_tdc_ts.pdf', minimum=20, maximum=60)

        with tb.open_file(input_file_hits[:-3] + '_tdc_hists.h5', mode="w") as out_file_h5:
            for index, condition in enumerate(hit_selection_conditions):
                tdc_hist_result = np.swapaxes(tdc_hists_per_condition[index], 0, 1)
                tdc_timestamp_hist_result = np.swapaxes(tdc_timestamp_hists_per_condition[index], 0, 1)
                out = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcCondition_%d' % index, title='Hist PixelTdc with %s' % condition, atom=tb.Atom.from_dtype(tdc_hist_result.dtype), shape=tdc_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_2 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTdcTimestampCondition_%d' % index, title='Hist PixelTdcTimestamp with %s' % condition, atom=tb.Atom.from_dtype(tdc_timestamp_hist_result.dtype), shape=tdc_timestamp_hist_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out.attrs.dimensions = 'column, row, TDC value'
                out.attrs.condition = condition
                out.attrs.tdc_values = range(max_tdc)
                out_2.attrs.dimensions = 'column, row, TDC time stamp value'
                out_2.attrs.condition = condition
                out_2.attrs.tdc_values = range(shape_tdc_timestamp_hist[2])
                out[:] = tdc_hist_result
                out_2[:] = tdc_timestamp_hist_result

    with PdfPages(input_file_hits[:-3] + '_calibrated_tdc_hists.pdf') as output_pdf:
        logging.info('Create hits selection efficiency histogram for %d conditions' % (len(hit_selection_conditions) + 2))
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

        if calibation_file is not None:
            with tb.openFile(calibation_file, mode="r") as in_file_h5:
                tdc_calibration = in_file_h5.root.HitOrCalibration[:, :, 1:, 1]
                tdc_calibration_values = in_file_h5.root.HitOrCalibration.attrs.scan_parameter_values[1:]

            charge = get_charge(max_tdc, tdc_calibration_values, tdc_calibration)
            plt.clf()

            with tb.openFile(input_file_hits[:-3] + '_calibrated_tdc_hists.h5', mode="w") as out_file_h5:
                logging.info('Create corrected TDC histogram for %d conditions' % len(hit_selection_conditions))
                for index, condition in enumerate(hit_selection_conditions):
                    c_str = re.sub('[&]', '\n', condition)
                    x, y = [], []
                    for column in range(0, 80, 1):
                        for row in range(0, 336, 1):
                            if tdc_hists_per_condition[0][column, row, :].sum() < analysis_configuration['min_pixel_hits']:
                                continue
                            x.extend(charge[column, row, :].ravel())
                            y.extend(tdc_hists_per_condition[index][column, row, :].ravel())
                    x, y, _ = analysis_utils.get_profile_histogram(np.array(x) * 55., np.array(y), n_bins=120)
                    result = np.zeros(shape=(x.shape[0], ), dtype=[("x", np.float), ("y", np.float)])
                    result['x'], result['y'] = x, y
                    actual_tdc_hist_table = out_file_h5.create_table(out_file_h5.root, name='TdcHistTableCondition%d' % index, description=result.dtype, title='TDC histogram', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    actual_tdc_hist_table.append(result)
                    actual_tdc_hist_table.attrs.condition = condition
                    if index == 0:
                        normalization = 100. / np.amax(y)
                    plt.plot(x, y * normalization, '.', label=c_str)
                # Plot hists into one plot
                plt.plot([27.82 * 55., 27.82 * 55.], [0, 100], label='Threshold %d e' % (28.82 * 55.), linewidth=2)
                plt.ylim((0, 100))
                plt.legend(loc=0, prop={'size': 12})
                plt.xlabel('Charge [e]')
                plt.ylabel('#')
                plt.grid()
                output_pdf.savefig()

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
