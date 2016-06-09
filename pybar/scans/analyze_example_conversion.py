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
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.align_at_trigger = True
            analyze_raw_data.max_cluster_size = 200000
            analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
            analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
            analyze_raw_data.align_at_tdc = False  # align events at the TDC word
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            
            
def analyze_hits(input_file, output_file_hits, scan_data_filename, output_file_hits_analyzed=None):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_source_scan_hist = True
        analyze_raw_data.create_cluster_hit_table = True
        analyze_raw_data.create_cluster_table = True
        analyze_raw_data.create_cluster_size_hist = True
        analyze_raw_data.create_cluster_tot_hist = True
        analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
        analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename, analyzed_data_file=output_file_hits_analyzed)


def analyze_raw_data_per_scan_parameter(input_file, output_file_hits, scan_data_filename, scan_parameters):
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram

        for data_one_step, one_step_parameter in analyze_hits_per_scan_parameter(analyze_data=analyze_raw_data, scan_parameters=scan_parameters):
            data_one_step.plot_histograms(scan_data_filename + '_' + one_step_parameter, create_hit_hists_only=True)


if __name__ == "__main__":
    scan_name = r'134_module_test_ext_trigger_scan'
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
