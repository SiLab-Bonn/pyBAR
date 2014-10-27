"""This is an example module how to use the raw data analyzer. It takes a table with FE-I4 raw data and interprets, histograms and plots it.
    The first "with-statement" interprets the raw data and can also histogram and cluster hits in the same analysis loop if activated to save time. 
    The second "with-statement" does the histogramming and clustering starting from hits. 
    This shows how to use the analysis if hits are already available 
"""

from datetime import datetime
import logging
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.analysis import analyze_hits_per_scan_parameter


def analyze_raw_data(input_file, output_file_hits, scan_data_filename):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_hit_table = False  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_cluster_hit_table = False  # adds the cluster id and seed info to each hit, std. setting is false
        analyze_raw_data.create_cluster_table = False  # enables the creation of a table with all clusters, std. setting is false

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

        analyze_raw_data.n_bcid = 16  # set the number of BCIDs per event, needed to judge the event structure, only active if settings are not taken from raw data file
        analyze_raw_data.n_injections = 100  # set the numbers of injections, needed for fast threshold/noise determination
        analyze_raw_data.max_tot_value = 13  # set the maximum ToT value considered to be a hit, 14 is a late hit
        analyze_raw_data.use_trigger_number = False
        analyze_raw_data.set_stop_mode = False  # special analysis if data was taken in stop mode
        analyze_raw_data.interpreter.use_tdc_word(False)  # use the TDC word to align the events, assume that they are first words in the event

        analyze_raw_data.interpreter.set_debug_output(False)  # std. setting is False
        analyze_raw_data.interpreter.set_info_output(False)  # std. setting is False
        analyze_raw_data.interpreter.set_warning_output(True)  # std. setting is True
        analyze_raw_data.clusterizer.set_warning_output(True)  # std. setting is True
        analyze_raw_data.interpreter.debug_events(3832, 3850, False)  # events to be printed onto the console for debugging, usually deactivated
        analyze_raw_data.interpret_word_table()  # the actual start conversion command
        analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
        analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename)  # plots all activated histograms into one pdf


def analyze_hits(input_file, output_file_hits, scan_data_filename, output_file_hits_analyzed=None):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_source_scan_hist = True
        analyze_raw_data.create_cluster_hit_table = True
        analyze_raw_data.create_cluster_table = True
        analyze_raw_data.create_cluster_size_hist = True
        analyze_raw_data.create_cluster_tot_hist = True
        analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
        analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename, analyzed_data_file=output_file_hits_analyzed)


def analyze_raw_data_per_scan_parameter(input_file, output_file_hits, scan_data_filename, scan_parameters=['PlsrDAC']):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram

        for data_one_step, one_step_parameter in analyze_hits_per_scan_parameter(analyze_data=analyze_raw_data, scan_parameters=scan_parameters):
            data_one_step.plot_histograms(scan_data_filename + '_' + one_step_parameter, create_hit_hists_only=True)


if __name__ == "__main__":
    scan_name = '73_mdbm_120_ext_trigger_gdac_scan'
    folder = '..//mdbm_120//'
    input_file = folder + scan_name + ".h5"
    output_file_hits = folder + scan_name + "_interpreted.h5"
    output_file_hits_analyzed = folder + scan_name + "_analyzed.h5"
    scan_data_filename = folder + scan_name
    start_time = datetime.now()
    analyze_raw_data(input_file, output_file_hits, scan_data_filename)
#     analyze_raw_data_per_scan_parameter(input_file, output_file_hits, scan_data_filename, scan_parameters=['PlsrDAC'])
#     analyze_hits(input_file, output_file_hits, scan_data_filename, output_file_hits_analyzed=output_file_hits_analyzed)
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
