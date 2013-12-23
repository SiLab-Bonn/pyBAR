""" This script takes the data from a source scan where the global threshold was changed and clusters the hits for each global threshold setting.
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
from analysis.analysis_utils import get_scan_parameter, get_meta_data_at_scan_parameter, data_aligned_at_events, get_event_range


def analyze_per_scan_parameter():
    with tb.openFile(input_file_hits, mode="r+") as in_hit_file_h5:
        meta_data_array = in_hit_file_h5.root.meta_data[:]
        scan_parameter_values = get_scan_parameter(meta_data_array).itervalues().next()
        scan_parameter_name = get_scan_parameter(meta_data_array).keys()[0]
        logging.info('Analyze per scan parameter ' + scan_parameter_name + ' for ' + str(len(scan_parameter_values)) + ' different values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
        event_numbers = get_meta_data_at_scan_parameter(meta_data_array, scan_parameter_name)['event_number']  # get the event numbers in meta_data where the scan parameter changes
        parameter_ranges = np.column_stack((scan_parameter_values, get_event_range(event_numbers)))
        hit_table = in_hit_file_h5.root.Hits

        if not hit_table.cols.event_number.is_indexed:  # index event_number column to speed up everything
            logging.info('Create event_number index')
            hit_table.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
            logging.info('Done')
        else:
            logging.info('Event_number index exists already')

        output_pdf = PdfPages(folder + 'Cluster_sizes.pdf')
        cluster_size_total = np.zeros(shape=(len(event_numbers), 1024))

        with tb.openFile(output_file, mode="w") as out_file_h5:
            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
            parameter_goup = out_file_h5.createGroup(out_file_h5.root, scan_parameter_name, title=scan_parameter_name)

            total_hits = 0
            total_hits_2 = 0
            index = 0  # index where to start the read out, 0 at the beginning
            max_chunk_size = 10000000  # max chunk size used, if too big memory errors occur
            chunk_size = max_chunk_size

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_cluster_size_hist = True
            analyze_data.create_cluster_tot_hist = True
            analyze_data.histograming.set_no_scan_parameter()  # one has to tell the histogramer the # of scan parameters for correct occupancy hist allocation

            for parameter_index, parameter_range in enumerate(parameter_ranges):  # loop over the selected events
                analyze_data.reset()  # resets the data of the last analysis

                logging.info('Analyze ' + scan_parameter_name + ' = ' + str(parameter_range[0]) + ' ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')
                start_event_number = parameter_range[1]
                stop_event_number = parameter_range[2]
                logging.info('Data from events = [' + str(start_event_number) + ',' + str(stop_event_number) + '[')
                actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=scan_parameter_name + '_' + str(parameter_range[0]), title=scan_parameter_name + '_' + str(parameter_range[0]))

                # loop over the hits in the actual selected events with optimizations: variable chunk size, start word index given
                readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                for hits, index in data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start=index, chunk_size=chunk_size):
                    total_hits += hits.shape[0]
                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks

                    readout_hit_len += hits.shape[0]
                chunk_size = int(1.05 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                # store occupancy hist
                occupancy = np.zeros(80 * 336 * analyze_data.histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
                analyze_data.histograming.get_occupancy(occupancy)
                occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, analyze_data.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
                occupancy_array = np.swapaxes(occupancy_array, 0, 1)
                occupancy_array_table = out_file_h5.createCArray(actual_parameter_group, name='HistOcc', title='Occupancy Histogram', atom=tb.Atom.from_dtype(occupancy.dtype), shape=(336, 80, analyze_data.histograming.get_n_parameters()), filters=filter_table)
                occupancy_array_table[0:336, 0:80, 0:analyze_data.histograming.get_n_parameters()] = occupancy_array  # swap axis col,row,parameter --> row, col,parameter

                # store and plot cluster size hist
                cluster_size_hist = np.zeros(1024, dtype=np.uint32)
                analyze_data.clusterizer.get_cluster_size_hist(cluster_size_hist)
                cluster_size_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                cluster_size_hist_table[:] = cluster_size_hist
                plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + scan_parameter_name + '=' + str(scan_parameter_values[parameter_index]), filename=output_pdf)
                cluster_size_total[parameter_index] = cluster_size_hist

                total_hits_2 += np.sum(occupancy)

            if total_hits != total_hits_2:
                logging.warning('Analysis shows inconsistent number of hits. Check needed!')
            logging.info('Analyzed %d hits!' % total_hits)

            cluster_size_total_out = out_file_h5.createCArray(out_file_h5.root, name='AllHistClusterSize', title='All Cluster Size Histograms', atom=tb.Atom.from_dtype(cluster_size_total.dtype), shape=cluster_size_total.shape, filters=filter_table)
            cluster_size_total_out[:] = cluster_size_total
        output_pdf.close()

if __name__ == "__main__":
    start_time = datetime.now()
    analyze_per_scan_parameter()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
