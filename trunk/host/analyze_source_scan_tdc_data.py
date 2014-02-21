''' This script does the full analysis of the tdc values taken during a source scan.
Several steps are done automatically:
Step 1 Tnterpret the raw data:
    This step interprets the raw data from the FE, creates and plots distributions for each data file seperately.
    Everything is summed up per data file.
Step 2 Analyze selected hits:
    This step just takes events with usable TDC information and stores the corresponding hits.
Step 3 Takes the hits and the calibration and creates a TDC histogram for all used pixel.
'''
import numpy as np
import tables as tb
import os.path
from matplotlib.backends.backend_pdf import PdfPages
from analysis import analysis
from analysis.plotting import plotting
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
    "overwrite_output_files": False,
    "plot_tdc_histograms": True
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
    with tb.openFile(output_file + '_histograms.h5', mode="w") as output_file_h5:
        chunk_size = max_chunk_size
        for input_files_hit in input_files_hits:
            with tb.openFile(input_files_hit, mode="r+") as in_hit_file_h5:
                output_pdf = PdfPages(output_file + '_histograms.pdf')
                logging.info('Calculate TDC histogram from hits in file %s' % input_files_hit)
                analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create index to efficiently work on data based on event numbers
                meta_data_array = in_hit_file_h5.root.meta_data[:]  # get the meta data array be able to select hits per scan parameter
                scan_parameter_values = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array, selected_columns_only=True)  # get the PlsrDAC/col/row values
                event_numbers = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array)['event_number']  # get the event numbers in meta_data where the scan parameters have different settings
                parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_ranges_from_array(event_numbers)))  # list with entries [scan_parameter_value, start_event_number, stop_event_number]
                analyze_data = AnalyzeRawData()
                analyze_data.create_tdc_hist = True
                analyze_data.histograming.set_no_scan_parameter()  # one has to tell the histogrammer the # of scan parameters for correct occupancy hist allocation
                start_index = 0
                for scan_parameter_value, start_event_number, stop_event_number in parameter_ranges:  # loop over the different PlsrDAC/col/row settings
                    analyze_data.reset()  # resets the data of the last analysis
                    column = scan_parameter_value[0]
                    row = scan_parameter_value[1]
                    logging.info("Analyze TDC words for pixel " + str(column) + "/" + str(row))
                    tdc_hist = np.zeros(4096, dtype=np.uint32)
                    readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                    for hits, start_index in analysis_utils.data_aligned_at_events(in_hit_file_h5.root.Hits, start_event_number=start_event_number, stop_event_number=stop_event_number, start=start_index, chunk_size=chunk_size):  # loop over hits for one PlsrDAC setting in chunks
                        analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                        readout_hit_len += hits.shape[0]
                    chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                    analyze_data.histograming.get_tdc_hist(tdc_hist)
                    if np.sum(tdc_hist) != readout_hit_len:
                        logging.warning('The TDC histogram does not have the correct number of hits, analysis has to be checked')
                    if analysis_configuration['plot_tdc_histograms']:
                        plotting.plot_tdc(tdc_hist, title="TDC histogram for pixel " + str(column) + "/" + str(row) + " (" + str(np.sum(tdc_hist)) + " entrie(s))", filename=output_pdf)
                output_pdf.close()


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
        analyze_tdc(input_files_hits=hit_cut_files, output_file=scan_base_names[0], output_file_pdf=None)
