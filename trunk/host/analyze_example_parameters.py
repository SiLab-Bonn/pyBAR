"""Some scans have scan parameters that are varied during the scan (e.g. the global threshold). The analysis usually ignores the change of the scan parameter. The only exception is the
occupancy histograming to be able to quickly determine the threshold. If one wants to analyze the hits independently for the different scan parameters one can use this script as an example.
First the events are determined where the scan parameter changes. Then the hits in this event range are taken and analyzed with the raw_data_converter.

This example takes the data from a source scan where the global threshold was changed and clusters the hits for each global threshold setting.
"""

scan_name = 'scan_fei4_trigger_gdac_0'
folder = 'K:\\data\\FE-I4\\ChargeRecoMethod\\bias_20\\'

chip_flavor = 'fei4a'
input_file = folder + scan_name + ".h5"
input_file_hits = folder + scan_name + "_interpreted.h5"
output_file = folder + scan_name + "_cluster_sizes.h5"
scan_data_filename = folder + scan_name

import tables as tb
import numpy as np
from datetime import datetime
import logging
from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting import plotting
from analysis.analyze_raw_data import AnalyzeRawData
from analysis.analysis_utils import get_scan_parameter, get_meta_data_index_at_scan_parameter, get_hits_in_event_range, data_aligned_at_events


def analyze_per_scan_parameter():
    with tb.openFile(input_file_hits, mode="r+") as in_hit_file_h5:
        meta_data_array = in_hit_file_h5.root.meta_data[:]
        scan_parameter_values = get_scan_parameter(meta_data_array).itervalues().next()
        scan_parameter_name = get_scan_parameter(meta_data_array).keys()[0]
        logging.info('Analyze per scan parameter ' + scan_parameter_name + ' for ' + str(len(scan_parameter_values)) + ' different values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
        index = get_meta_data_index_at_scan_parameter(meta_data_array, scan_parameter_name)['index']  # get the index in meta_data where the scan parameter changes
        event_numbers = meta_data_array[index]['event_number']  # get the event numbers in meta_data where the scan parameter changes
        event_numbers = np.append(event_numbers, meta_data_array[-1]['event_number'])  # add the last event number

        hit_table = in_hit_file_h5.root.Hits

        if not hit_table.cols.event_number.is_indexed:  # index event_number column to speed up everything
            logging.info('Create event_number index')
            hit_table.cols.event_number.remove_index()
            hit_table.cols.event_number.create_index(1, 'ultralight', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            logging.info('Done')
        else:
            logging.info('Event_number index exists already')

        output_pdf = PdfPages(folder + 'Cluster_sizes.pdf')
        cluster_size_total = np.zeros(shape=(len(event_numbers), 1024))

        with tb.openFile(output_file, mode="w") as out_file_h5:
            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
            parameter_goup = out_file_h5.createGroup(out_file_h5.root, scan_parameter_name, title=scan_parameter_name)

            stop_index = 0
            for event_number_index in range(0, len(event_numbers) - 2):  # TODO needs check
                analyze_data = AnalyzeRawData()
                analyze_data.create_cluster_size_hist = True
                analyze_data.create_cluster_tot_hist = True
                logging.info('Analyze ' + scan_parameter_name + ' = ' + str(scan_parameter_values[event_number_index]) + ' ' + str(int(float(float(event_number_index) / float(len(event_numbers)) * 100.))) + '%')
                actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=scan_parameter_name + '_' + str(scan_parameter_values[event_number_index]), title=scan_parameter_name + '_' + str(scan_parameter_values[event_number_index]))
                start_event_number = event_numbers[event_number_index]
                stop_event_number = event_numbers[event_number_index + 1]

                logging.info('Data from events = [' + str(start_event_number) + ',' + str(stop_event_number) + '[')

                for hits, stop_index in data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start=stop_index):
                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks

                # store occupancy hist
                occupancy = np.zeros(80 * 336 * analyze_data.histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
                analyze_data.histograming.get_occupancy(occupancy)
                occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, analyze_data.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
                occupancy_array = np.swapaxes(occupancy_array, 0, 1)
                occupancy_array_table = out_file_h5.createCArray(actual_parameter_group, name='HistOcc', title='Occupancy Histogram', atom=tb.Atom.from_dtype(occupancy.dtype), shape=(336, 80, analyze_data.histograming.get_n_parameters()), filters=filter_table)
                occupancy_array_table[0:336, 0:80, 0:analyze_data.histograming.get_n_parameters()] = occupancy_array  # swap axis col,row,parameter --> row, col,parameter
                # create cluster size hist
                cluster_size_hist = np.zeros(1024, dtype=np.uint32)
                analyze_data.clusterizer.get_cluster_size_hist(cluster_size_hist)
                cluster_size_total[event_number_index] = cluster_size_hist
                plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + scan_parameter_name + '=' + str(scan_parameter_values[event_number_index]), filename=output_pdf)

            cluster_size_total_out = out_file_h5.createCArray(out_file_h5.root, name='AllHistClusterSize', title='All Cluster Size Histograms', atom=tb.Atom.from_dtype(cluster_size_total.dtype), shape=cluster_size_total.shape, filters=filter_table)
            cluster_size_total_out[:] = cluster_size_total
        output_pdf.close()

if __name__ == "__main__":
    start_time = datetime.now()
    analyze_per_scan_parameter()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
