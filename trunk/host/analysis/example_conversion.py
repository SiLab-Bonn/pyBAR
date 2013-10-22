"""This is an example module how to use the raw data analyzer. It takes a table with FE-I4 raw data and interprets, histograms and plots it.
    The first with environment interprets the raw data and can cluster hits in the same analysis loop. The second with environment just clusters
    data from hits. This shows how to use the clusterizer in the interpretation step or afterwards if hit infos are already available. 
"""
from os.path import expanduser
home = expanduser("~")

chip_flavor = 'fei4a'
input_file = home+"/workspace/PyBAR/host/data/scan_digital_1.h5"
output_file_hits = home+"/workspace/PyBAR/host/data/scan_digital_1_interpreted.h5"
output_file_cluster = home+"/workspace/PyBAR/host/data/scan_digital_1_clustered.h5"
scan_data_filename = home+"/workspace/PyBAR/host/data/"
 
from datetime import datetime
import logging
from analyze_raw_data import AnalyzeRawData
logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
 
start_time = datetime.now()
with AnalyzeRawData(input_file = input_file, output_file = output_file_hits) as analyze_raw_data:
    analyze_raw_data.create_hit_table = True # can be set to false to omit hit creation, can save some time, std. setting is false
    analyze_raw_data.create_cluster_hit_table = False  # can be set to false to omit cluster hit creation, can save some time, std. setting is false
    analyze_raw_data.create_cluster_table = False
    analyze_raw_data.create_meta_event_index = False # stores the event number for each readout in an additional meta data array, default: False
    analyze_raw_data.create_threshold_hists = False # makes only sense if threshold scan data is analyzed, std. setting is false
    analyze_raw_data.interpreter.set_warning_output(True) # std. setting is True
    analyze_raw_data.interpreter.debug_events(0,0,False) # events to be printed onto the console for debugging, usually deactivated
    analyze_raw_data.interpret_word_table(FEI4B = True if(chip_flavor == 'fei4b') else False) # the actual start conversion command
    analyze_raw_data.interpreter.print_summary() # prints the interpreter summary
    analyze_raw_data.plotHistograms(scan_data_filename = scan_data_filename) # plots all activated histograms
     
with AnalyzeRawData(input_file = output_file_hits, output_file = output_file_cluster) as analyze_raw_data:
    analyze_raw_data.create_cluster_hit_table = True  # can be set to false to omit cluster hit creation, can save some time, std. setting is false
    analyze_raw_data.create_cluster_table = True  # can be set to false to omit cluster table creation, can save some time, std. setting is false
    analyze_raw_data.cluster_hit_table()

logging.info('Script runtime %.1f seconds' % (datetime.now()-start_time).total_seconds())