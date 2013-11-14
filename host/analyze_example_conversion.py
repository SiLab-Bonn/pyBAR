"""This is an example module how to use the raw data analyzer. It takes a table with FE-I4 raw data and interprets, histograms and plots it.
    The first "with-statement" interprets the raw data and can cluster hits in the same analysis loop if activated. The second "with-statement" just clusters
    data from hits. This shows how to use the clusterizer afterwards if hit infos are already available. 
"""
# from os.path import expanduser
# home = expanduser("~")

scan_name='scan_digital_0'

chip_flavor = 'fei4a'
input_file = "data/"+scan_name+".h5"
output_file_hits = "data/"+scan_name+"_interpreted.h5"
output_file_cluster = "data/"+scan_name+"_clustered.h5"
scan_data_filename = "data/"+scan_name
 
from datetime import datetime
import logging
from analysis.analyze_raw_data import AnalyzeRawData
logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
 
start_time = datetime.now()
with AnalyzeRawData(input_file = input_file, output_file = output_file_hits) as analyze_raw_data:
    analyze_raw_data.create_hit_table = False            # can be set to false to omit hit table creation, std. setting is false
    analyze_raw_data.create_cluster_hit_table = False   # adds the cluster id and seed info to each hit, std. setting is false
    analyze_raw_data.create_cluster_table = False       # enables the creation of a table with all clusters, std. setting is false
    
    analyze_raw_data.create_occupancy_hist = True       # creates a colxrow histogram with accumulated hits for each scan parameter
    analyze_raw_data.create_tot_hist = True             # creates a tot histogram
    analyze_raw_data.create_rel_bcid_hist = True        # creates a histogram with the relative BCID of the hits
    analyze_raw_data.create_service_record_hist = True  # creates a histogram with all SR send out from the FE
    analyze_raw_data.create_error_hist = True           # creates a histogram summing up the event errors that occurred
    analyze_raw_data.create_trigger_error_hist = False  # creates a histogram summing up the trigger errors
    analyze_raw_data.create_cluster_size_hist = False   # enables cluster size histogramming, can save some time, std. setting is false
    analyze_raw_data.create_cluster_tot_hist = False    # enables cluster tot histogramming per cluster size, std. setting is false
    analyze_raw_data.create_threshold_hists = False     # makes only sense if threshold scan data is analyzed, std. setting is false
    
    analyze_raw_data.create_meta_word_index = False     # stores the start and stop raw data word index for every event, std. setting is false
    analyze_raw_data.create_meta_event_index = False    # stores the event number for each readout in an additional meta data array, default: False
    
    analyze_raw_data.interpreter.set_warning_output(True) # std. setting is True
    analyze_raw_data.interpreter.debug_events(0,0,True) # events to be printed onto the console for debugging, usually deactivated
    analyze_raw_data.interpret_word_table(FEI4B = True if(chip_flavor == 'fei4b') else False) # the actual start conversion command
    analyze_raw_data.interpreter.print_summary()        # prints the interpreter summary
    analyze_raw_data.plot_histograms(scan_data_filename = scan_data_filename) # plots all activated histograms into one pdf
     
with AnalyzeRawData(input_file = output_file_hits, output_file = output_file_cluster) as analyze_raw_data:
    analyze_raw_data.create_cluster_hit_table = True    # adds the cluster id and seed info to each hit, std. setting is false
    analyze_raw_data.create_cluster_table = True        # enables the creation of a table with all clusters, std. setting is false
    analyze_raw_data.create_cluster_size_hist = True    # enables cluster size histogramming, can save some time, std. setting is false
    analyze_raw_data.create_cluster_tot_hist = True     # enables cluster tot histogramming per cluster size, std. setting is false
    analyze_raw_data.cluster_hit_table()                # the command to start the clustering from the hit information
    analyze_raw_data.plot_histograms(scan_data_filename = scan_data_filename) # plots all activated histograms into one pdf

logging.info('Script runtime %.1f seconds' % (datetime.now()-start_time).total_seconds())