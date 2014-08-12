''' This script does the full analysis of the TDC values taken during a source scan.
Several steps are done automatically:
Step 1 Tnterpret the raw data:
    This step interprets the raw data from the FE, creates and plots distributions all provided raw data files.
    Correct TDC analysis settings are set.
Step 2 Analyze selected hits:
    This step takes events with usable TDC information, stores the corresponding hits and histograms them.
'''
import os.path
from analysis import analysis
from analysis import analysis_utils
from analysis.analyze_raw_data import AnalyzeRawData
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


analysis_configuration = {
    'scan_name': ['data//MDBM_30_ext_trigger_scan_58'],  # the base file name(s) of the raw data file, no file suffix needed
    'cluster_size_condition': 'cluster_size==1',  # only select hit with cluster_size_condition
    'n_cluster_condition': 'n_cluster==1',  # only select hit with n_cluster_condition
    'hit_selection_condition': '(relative_BCID > 2) & (relative_BCID < 9)',  # an optional criterion for the hit selection based on hit properties (e.g. 'relative_BCID == 6')
    'event_status_select_mask': 0b0000010111011110,  # the event status bits to cut on
    'event_status_condition': 0b0000000100000000,  # the event status number after the event_status_select_mask is bitwise ORed with the event number
    'input_file_calibration': None,  # the Plsr<->TDC calibration file
    "analysis_steps": [1, 2],  # the analysis includes this selected steps. See explanation above.
    "max_tot_value": 13,  # maximum tot value to use the hit
    "interpreter_plots": True,  # set to False to omit the Raw Data plots, saves time
    "interpreter_warnings": False,  # show interpreter warnings
    "overwrite_output_files": True  # overwrite already existing files from former analysis
}


def analyze_raw_data(input_files, output_file_hits, scan_data_filename):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    if os.path.isfile(output_file_hits) and not analysis_configuration['overwrite_output_files']:  # skip analysis if already done
        logging.info('Analyzed data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        with AnalyzeRawData(raw_data_file=input_files, analyzed_data_file=output_file_hits) as analyze_raw_data:
#             analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
            analyze_raw_data.use_trigger_word = True # align events at trigger words
            analyze_raw_data.create_tdc_counter_hist = True  # create a histogram for all TDC words
            analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
#            analyze_raw_data.create_tdc_pixel_hist = True
            analyze_raw_data.use_trigger_number = False  # use the trigger number to align the events
#            analyze_raw_data.use_trigger_time_stamp = True # trigger numbers are time stamp
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is falsee
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_source_scan_hist = True  # create source scan hists
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.max_tot_value = analysis_configuration['max_tot_value']  # set the maximum ToT value considered to be a hit, 14 is a late hit
            analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
#             analyze_raw_data.interpreter.debug_events(0, 4, True)
            analyze_raw_data.interpret_word_table()  # the actual start conversion command
            analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
            if analysis_configuration['interpreter_plots']:
                analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename)  # plots all activated histograms into one pdf


def analyse_selected_hits(input_file_hits, output_file_hits, output_file_hits_analyzed):
    logging.info('Analyze selected hits with ' + analysis_configuration['cluster_size_condition'] + ' and ' + analysis_configuration['n_cluster_condition'] + ' in ' + input_file_hits)
    if os.path.isfile(output_file_hits) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
        logging.info('Selected hit data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        analysis.select_hits_for_tdc_info(input_file_hits=input_file_hits, output_file_hits=output_file_hits, cluster_size_condition=analysis_configuration['cluster_size_condition'], n_cluster_condition=analysis_configuration['n_cluster_condition'], hit_selection_condition=analysis_configuration['hit_selection_condition'], event_status_select_mask=analysis_configuration['event_status_select_mask'], event_status_condition=analysis_configuration['event_status_condition'])  # select hits and copy them into new file
    if os.path.isfile(output_file_hits_analyzed) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
        logging.info('Selected hit data file ' + output_file_hits_analyzed + ' already exists. Skip analysis for this file.')
    else:
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=output_file_hits) as analyze_data:
            analyze_data.create_tdc_hist = True
            analyze_data.create_tdc_pixel_hist = True
            analyze_raw_data.use_trigger_time_stamp = True
            analyze_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
            analyze_data.plot_histograms(scan_data_filename=output_file_hits_analyzed[:-3], analyzed_data_file=output_file_hits_analyzed)


if __name__ == "__main__":
    data_files = analysis_utils.get_data_file_names_from_scan_base(analysis_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'])
    logging.info('Found ' + str(len(data_files)) + ' data file(s)')

    raw_data_files = data_files
    hit_file = analysis_configuration['scan_name'][0] + '_interpreted.h5'
    hit_cut_file = analysis_configuration['scan_name'][0] + '_cut_hits.h5'
    hit_cut_analyzed_file = analysis_configuration['scan_name'][0] + '_cut_hits_analyzed.h5'

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=raw_data_files, output_file_hits=hit_file, scan_data_filename=analysis_configuration['scan_name'][0])
    if 2 in analysis_configuration['analysis_steps']:
        analyse_selected_hits(input_file_hits=hit_file, output_file_hits=hit_cut_file, output_file_hits_analyzed=analysis_configuration['scan_name'][0] + '_cut_hits_histograms.h5')
