''' This script does the full analysis of the TDC values taken during a source scan.
Several steps are done automatically:
Step 1 Tnterpret the raw data:
    This step interprets the raw data from the FE, creates and plots distributions for each data file seperately.
    Everything is summed up per data file.
Step 2 Analyze selected hits:
    This step just takes events with usable TDC information and stores the corresponding hits.
Step 3 Takes the hits and the calibration and creates a TDC histogram for all used pixel.
'''
import os.path
from analysis import analysis
from analysis import analysis_utils
from analysis.analyze_raw_data import AnalyzeRawData
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


analysis_configuration = {
    'input_file_calibration': None,
    'scan_base_names': ['data//SCC_99//SCC_99_fei4_self_trigger_hit_or_633'],
    "chip_flavor": 'fei4a',
    "n_bcid": 16,
    "analysis_steps": [1, 2, 3],  # the analysis includes this selected steps. See explenation above.
    "max_tot_value": 13,  # maximum tot value to use the hit
    "vcal_calibration": 55.,   # calibration electrons/PlsrDAC
    "interpreter_plots": True,
    "interpreter_warnings": False,
    "overwrite_output_files": False
}


def analyze_raw_data(input_files, output_files_hits, chip_flavor, scan_data_filenames):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    for index in range(0, len(input_files)):  # loop over all raw data files
        if os.path.isfile(output_files_hits[index]) and not analysis_configuration['overwrite_output_files']:  # skip analysis if already done
            logging.info('Analyzed data file ' + output_files_hits[index] + ' already exists. Skip analysis for this file.')
        else:
            with AnalyzeRawData(raw_data_file=input_files[index], analyzed_data_file=output_files_hits[index]) as analyze_raw_data:
                analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
                analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
                analyze_raw_data.create_source_scan_hist = True  # create source scan hists
                analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
                analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
                analyze_raw_data.create_tdc_counter_hist = True
                analyze_raw_data.n_bcid = analysis_configuration['n_bcid']  # set the number of BCIDs per event, needed to judge the event structure
                analyze_raw_data.max_tot_value = analysis_configuration['max_tot_value']  # set the maximum ToT value considered to be a hit, 14 is a late hit
                analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
                analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
                analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
#                 analyze_raw_data.interpreter.debug_events(0, 10, True)
                analyze_raw_data.interpret_word_table(fei4b=True if(chip_flavor == 'fei4b') else False)  # the actual start conversion command
                analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
                if analysis_configuration['interpreter_plots']:
                    analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filenames[index])  # plots all activated histograms into one pdf


def analyse_selected_hits(input_files_hits, output_files_hits, output_files_hits_analyzed, scan_data_filenames, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1'):
    logging.info('Analyze selected hits with ' + cluster_size_condition + ' and ' + n_cluster_condition + ' for ' + str(len(input_files_hits)) + ' hit file(s)')
    for index in range(0, len(input_files_hits)):  # loop over all hit files
        if os.path.isfile(output_files_hits[index]) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
            logging.info('Selected hit data file ' + output_files_hits[index] + ' already exists. Skip analysis for this file.')
        else:
            analysis.select_hits_for_tdc_info(input_file_hits=input_files_hits[index], output_file_hits=output_files_hits[index], cluster_size_condition=cluster_size_condition, n_cluster_condition=n_cluster_condition, output_pdf=None)  # select hits and copy the mto new file


def analyze_tdc(input_files_hits, output_file, max_chunk_size=10000000, output_file_pdf=None):
    logging.info('Analyze the TDC histograms of %d different files' % len(input_files_hits))
    for input_files_hit in input_files_hits:
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=input_files_hit) as analyze_data:
            analyze_data.create_tdc_hist = True
            analyze_data.create_tdc_pixel_hist = True
            analyze_data.analyze_hit_table(analyzed_data_out_file=output_file)
            analyze_data.plot_histograms(scan_data_filename=output_file[:-3], analyzed_data_file=output_file)


if __name__ == "__main__":
    scan_base_names = analysis_utils.get_parameter_scan_bases_from_scan_base(analysis_configuration['scan_base_names'])
    logging.info('Found ' + str(len(scan_base_names)) + ' data files for different pixels')

    raw_data_files = [filename + '.h5' for filename in scan_base_names]
    hit_files = [filename + '_interpreted.h5' for filename in scan_base_names]
    hit_cut_files = [filename + '_cut_hits.h5' for filename in scan_base_names]
    hit_analyzed_files = [filename + '_cut_hits_analyzed.h5' for filename in scan_base_names]

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=raw_data_files, output_files_hits=hit_files, chip_flavor=analysis_configuration['chip_flavor'], scan_data_filenames=scan_base_names)
    if 2 in analysis_configuration['analysis_steps']:
        analyse_selected_hits(input_files_hits=hit_files, output_files_hits=hit_cut_files, output_files_hits_analyzed=hit_analyzed_files, scan_data_filenames=scan_base_names)
    if 3 in analysis_configuration['analysis_steps']:
        analyze_tdc(input_files_hits=hit_cut_files, output_file=scan_base_names[0] + '_histograms.h5', output_file_pdf=None)
