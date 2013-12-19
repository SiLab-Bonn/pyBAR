"""Some scans have scan parameters that are varied during the scan (e.g. the global threshold). The analysis usually ignores the change of the scan parameter. The only exception is the
occupancy histograming to be able to quickly determine the threshold. If one wants to analyze the hits independently for the different scan parameters one can use this script as an example.
First the events are determined where the scan parameter changes. Then the hits in this event range are taken and analyzed with the raw_data_converter.

This example takes the data from a source scan where the global threshold was changed and clusters the hits for each global threshold setting.
"""
scan_name = 'SCC29_raw_data_cut_0_analyzed'

chip_flavor = 'fei4a'
input_file = 'data/' + scan_name + ".h5"
input_file_hits = 'data/' + scan_name + "_interpreted.h5"
output_file = 'data/' + scan_name + "_analyzed_per_parameter.h5"
scan_data_filename = 'data/' + scan_name

import tables as tb
import numpy as np
from datetime import datetime
import logging
from analysis.RawDataConverter import data_struct
from analysis.analyze_raw_data import AnalyzeRawData
from analysis.analysis_utils import get_scan_parameter, get_meta_data_index_at_scan_parameter, get_hits_in_event_range


def analyze_per_scan_parameter():
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        hits = in_hit_file_h5.root.Hits[:]
        meta_data_array = in_hit_file_h5.root.meta_data[:]
        scan_parameter_values = get_scan_parameter(meta_data_array).itervalues().next()
        scan_parameter_name = get_scan_parameter(meta_data_array).keys()[0]
        logging.info('Analyze per scan parameter ' + scan_parameter_name + ' for ' + str(len(scan_parameter_values)) + ' different values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
        index = get_meta_data_index_at_scan_parameter(meta_data_array, scan_parameter_name)['index']  # get the index in meta_data where the scan parameter changes
        event_numbers = meta_data_array[index]['event_number']  # get the event numbers in meta_data where the scan parameter changes

        cluster_size_total = np.zeros(shape=(len(event_numbers) - 1, 1024))

        with tb.openFile(output_file, mode="w") as out_file_h5:
            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
            parameter_goup = out_file_h5.createGroup(out_file_h5.root, scan_parameter_name, title=scan_parameter_name)
            for event_number_index in range(0, len(event_numbers) - 1):
                analyze_data = AnalyzeRawData()
                analyze_data.create_cluster_size_hist = True
                analyze_data.create_cluster_tot_hist = True
                logging.info('Analyze ' + scan_parameter_name + ' = ' + str(scan_parameter_values[event_number_index]) + ' ' + str(int(float(float(event_number_index) / float(len(event_numbers)) * 100.))) + '%')
                actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=scan_parameter_name + '_' + str(scan_parameter_values[event_number_index]), title=scan_parameter_name + '_' + str(scan_parameter_values[event_number_index]))
                start_event_number = event_numbers[event_number_index]
                stop_event_number = event_numbers[event_number_index + 1]
                actual_scan_parameter_hits = get_hits_in_event_range(hits, event_start=start_event_number, event_stop=stop_event_number)
                cluster, cluster_hits = analyze_data.analyze_hits(actual_scan_parameter_hits)  # analyze the selected hits
                # store tot hist
                tot_hist = np.zeros(16, dtype=np.uint32)
                analyze_data.histograming.get_tot_hist(tot_hist)
                tot_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistTot', title='TOT Histogram', atom=tb.Atom.from_dtype(tot_hist.dtype), shape=tot_hist.shape, filters=filter_table)
                tot_hist_table[:] = tot_hist
                #store occupancy hist
                occupancy = np.zeros(80 * 336 * analyze_data.histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
                analyze_data.histograming.get_occupancy(occupancy)
                occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, analyze_data.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
                occupancy_array = np.swapaxes(occupancy_array, 0, 1)
                occupancy_array_table = out_file_h5.createCArray(actual_parameter_group, name='HistOcc', title='Occupancy Histogram', atom=tb.Atom.from_dtype(occupancy.dtype), shape=(336, 80, analyze_data.histograming.get_n_parameters()), filters=filter_table)
                occupancy_array_table[0:336, 0:80, 0:analyze_data.histograming.get_n_parameters()] = occupancy_array  # swap axis col,row,parameter --> row, col,parameter
                #store cluster size hist
                cluster_size_hist = np.zeros(1024, dtype=np.uint32)
                analyze_data.clusterizer.get_cluster_size_hist(cluster_size_hist)
                cluster_size_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                cluster_size_hist_table[:] = cluster_size_hist
                cluster_size_total[event_number_index] = cluster_size_hist
                #store cluster tot hist
                cluster_tot_hist = np.zeros(128 * 1024, dtype=np.uint32)  # create linear array as it is created in histogram class
                analyze_data.clusterizer.get_cluster_tot_hist(cluster_tot_hist)
                cluster_tot_hist = np.reshape(a=cluster_tot_hist.view(), newshape=(128, 1024), order='F')  # make linear array to 2d array (tot, cluster size)
                cluster_tot_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterTot', title='Cluster Tot Histogram', atom=tb.Atom.from_dtype(cluster_tot_hist.dtype), shape=cluster_tot_hist.shape, filters=filter_table)
                cluster_tot_hist_table[:] = cluster_tot_hist

            cluster_size_total_out = out_file_h5.createCArray(out_file_h5.root, name='AllHistClusterSize', title='All Cluster Size Histograms', atom=tb.Atom.from_dtype(cluster_size_total.dtype), shape=cluster_size_total.shape, filters=filter_table)
            cluster_size_total_out[:] = cluster_size_total

if __name__ == "__main__":
    start_time = datetime.now()
    analyze_per_scan_parameter()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
