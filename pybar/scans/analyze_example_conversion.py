"""This is an example module on how to use the raw data analyzer. FE-I4 raw data file is interpreted, histogrammed and plotted.
The analyze_raw_data function interprets the raw data and stores it into the hit table. Histogramming and clustering can be enabled.
The clusterizer has not a big impact on processing time since it uses the same analysis loop as the interpreter.
The analyze_hits function does the histogramming and clustering starting from the hit table.
The analyze_raw_data_per_scan_parameter function does the anylysis per scan parameter.
"""

from datetime import datetime
import logging
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.analysis import analyze_hits_per_scan_parameter


def analyze_raw_data(input_file, output_file_hits):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_hit_table = False  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_cluster_hit_table = False  # adds the cluster id and seed info to each hit, std. setting is false
        analyze_raw_data.create_cluster_table = False  # enables the creation of a table with all clusters, std. setting is false

        analyze_raw_data.create_empty_event_hits = False  # creates events with no hist in hit table
        analyze_raw_data.create_occupancy_hist = True  # creates a colxrow histogram with accumulated hits for each scan parameter
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram
        analyze_raw_data.create_rel_bcid_hist = True  # creates a histogram with the relative BCID of the hits
        analyze_raw_data.create_service_record_hist = True  # creates a histogram with all SR send out from the FE
        analyze_raw_data.create_error_hist = True  # creates a histogram summing up the event errors that occurred
        analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
        analyze_raw_data.create_source_scan_hist = False  # create source scan hists
        analyze_raw_data.create_cluster_size_hist = False  # enables cluster size histogramming, can save some time, std. setting is false
        analyze_raw_data.create_cluster_tot_hist = False  # enables cluster ToT histogramming per cluster size, std. setting is false
        analyze_raw_data.create_threshold_hists = False  # makes only sense if threshold scan data is analyzed, std. setting is false
        analyze_raw_data.create_threshold_mask = False  # masking of noisy or black pixels during histogramming, only affecting fast-algorithm
        analyze_raw_data.create_fitted_threshold_hists = False  # makes only sense if threshold scan data is analyzed, std. setting is false
        analyze_raw_data.create_fitted_threshold_mask = False  # masking of noisy or black pixels during histogramming, only affecting S-curve fitting

        analyze_raw_data.create_meta_word_index = False  # stores the start and stop raw data word index for every event, std. setting is false
        analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False

        analyze_raw_data.trig_count = 0  # set the number of BCIDs per trigger, needed to judge the event structure, only active if settings cannot be taken from raw data file
        analyze_raw_data.n_injections = 100  # set the numbers of injections, needed for fast threshold/noise determination
        analyze_raw_data.max_tot_value = 13  # set the maximum ToT value considered to be a hit, 14 is a late hit
        analyze_raw_data.align_at_trigger = False  # align the data at the trigger number; has to be first event word
        analyze_raw_data.align_at_tdc = False  # use the TDC word to align the events, assume that they are first words in the event
        analyze_raw_data.trigger_data_format = 0  # specify trigger data word format
        analyze_raw_data.set_stop_mode = False  # special analysis if data was taken in stop mode

        analyze_raw_data.interpreter.set_debug_output(False)  # std. setting is False
        analyze_raw_data.interpreter.set_info_output(False)  # std. setting is False
        analyze_raw_data.interpreter.set_warning_output(True)  # std. setting is True
        analyze_raw_data.interpreter.debug_events(3832, 3850, False)  # events to be printed onto the console for debugging, usually deactivated
        analyze_raw_data.interpret_word_table()  # the actual start conversion command
        analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
        analyze_raw_data.plot_histograms(pdf_filename=input_file)  # plots all activated histograms into one pdf


def analyze_hits(input_file, output_file_hits, scan_data_filename, output_file_hits_analyzed=None):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_source_scan_hist = True
        analyze_raw_data.create_cluster_hit_table = True
        analyze_raw_data.create_cluster_table = True
        analyze_raw_data.create_cluster_size_hist = True
        analyze_raw_data.create_cluster_tot_hist = True
        analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
        analyze_raw_data.plot_histograms(pdf_filename=scan_data_filename, analyzed_data_file=output_file_hits_analyzed)


def analyze_raw_data_per_scan_parameter(input_file, output_file_hits, scan_data_filename, scan_parameters):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram

        for data_one_step, one_step_parameter in analyze_hits_per_scan_parameter(analyze_data=analyze_raw_data, scan_parameters=scan_parameters):
            data_one_step.plot_histograms(scan_data_filename + '_' + one_step_parameter, create_hit_hists_only=True)


if __name__ == "__main__":
    scan_name = r'1_module_test_ext_trigger_scan'
    folder = r'../module_test/'
    input_file = folder + scan_name + ".h5"
    output_file_hits = folder + scan_name + "_interpreted.h5"
    output_file_hits_analyzed = folder + scan_name + "_analyzed.h5"
    scan_data_filename = folder + scan_name
    start_time = datetime.now()
    analyze_raw_data(input_file, output_file_hits)
#     analyze_hits(input_file, output_file_hits, scan_data_filename, output_file_hits_analyzed=output_file_hits_analyzed)
#     analyze_raw_data_per_scan_parameter(input_file, output_file_hits, scan_data_filename, scan_parameters=['PlsrDAC'])
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
    logging.info('FINISHED')
