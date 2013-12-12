"""This is an example module how to use the raw data analyzer. It takes a table with FE-I4 raw data and interprets, histograms and plots it.
    The first "with-statement" interprets the raw data and can also histogram and cluster hits in the same analysis loop if activated to save time. 
    The second "with-statement" does the histogramming and clustering starting from hits. 
    This shows how to use the analysis if hits are already available 
"""
scan_name = 'scan_example'

chip_flavor = 'fei4a'
input_file = 'data/' + scan_name + ".h5"
output_file_hits = 'data/' + scan_name + "_interpreted.h5"
output_file_hits_analyzed = 'data/' + scan_name + "_analyzed.h5"
scan_data_filename = 'data/' + scan_name

from datetime import datetime
import logging
from analysis.analyze_raw_data import AnalyzeRawData


def analyze():
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_cluster_hit_table = False  # adds the cluster id and seed info to each hit, std. setting is false
        analyze_raw_data.create_cluster_table = False  # enables the creation of a table with all clusters, std. setting is false

        analyze_raw_data.create_occupancy_hist = True  # creates a colxrow histogram with accumulated hits for each scan parameter
        analyze_raw_data.create_source_scan_hist = False  # create source scan hists
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram
        analyze_raw_data.create_rel_bcid_hist = True  # creates a histogram with the relative BCID of the hits
        analyze_raw_data.create_service_record_hist = True  # creates a histogram with all SR send out from the FE
        analyze_raw_data.create_error_hist = True  # creates a histogram summing up the event errors that occurred
        analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
        analyze_raw_data.create_cluster_size_hist = False  # enables cluster size histogramming, can save some time, std. setting is false
        analyze_raw_data.create_cluster_tot_hist = False  # enables cluster ToT histogramming per cluster size, std. setting is false
        analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
        analyze_raw_data.create_threshold_mask = True  # masking of noisy or black pixels during histogramming, only affecting fast-algorithm
        analyze_raw_data.create_fitted_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
        analyze_raw_data.create_fitted_threshold_mask = True  # masking of noisy or black pixels during histogramming, only affecting S-curve fitting

        analyze_raw_data.create_meta_word_index = False  # stores the start and stop raw data word index for every event, std. setting is false
        analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False

        analyze_raw_data.n_injections = 100  # set the numbers of injections, needed for fast threshold/noise determination
        analyze_raw_data.n_bcid = 16  # set the number of BCIDs per event, needed to judge the event structure
        analyze_raw_data.max_tot_value = 14  # set the maximum ToT value considered to be a hit, 14 is a late hit

        analyze_raw_data.interpreter.set_warning_output(False)  # std. setting is True
        analyze_raw_data.interpreter.debug_events(0, 0, False)  # events to be printed onto the console for debugging, usually deactivated
        analyze_raw_data.interpret_word_table(FEI4B=True if(chip_flavor == 'fei4b') else False)  # the actual start conversion command
        analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
        analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename)  # plots all activated histograms into one pdf

#     with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
#         analyze_raw_data.create_cluster_hit_table = True
#         analyze_raw_data.create_cluster_table = True
#         analyze_raw_data.create_cluster_size_hist = True
#         analyze_raw_data.create_cluster_tot_hist = True
#         analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
#         analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename, analyzed_data_file=output_file_hits_analyzed)

if __name__ == "__main__":
    start_time = datetime.now()
    analyze()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
