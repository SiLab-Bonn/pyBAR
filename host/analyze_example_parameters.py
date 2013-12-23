"""Some scans have scan parameters that are varied during the scan (e.g. the global threshold). The analysis usually ignores the change of the scan parameter. The only exception is the
occupancy histograming to be able to quickly determine the threshold. If one wants to analyze the hits independently for the different scan parameters one can use this script as an example.
First the event of interest are determined. Then the hits in the chosen event range are taken and analyzed with the raw_data_converter.

This example takes the data from a source scan and determines the mean TOT as a function of the time.
"""
import tables as tb
import numpy as np
from datetime import datetime
import logging
from analysis.plotting.plotting import plot_scatter
from analysis.analyze_raw_data import AnalyzeRawData
from analysis.analysis_utils import data_aligned_at_events, get_event_range

@profile
def analyze_per_scan_parameter(input_file_hits):
    with tb.openFile(input_file_hits, mode="r+") as in_hit_file_h5:
        # get data and data pointer
        meta_data_array = in_hit_file_h5.root.meta_data[:]
        hit_table = in_hit_file_h5.root.Hits

        # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
        combine_n_readouts = 1000  # to increase analysis speed combine events of 1000 readouts
        parameter_ranges = np.column_stack((meta_data_array['timestamp_start'][::combine_n_readouts], get_event_range(meta_data_array['event_number'][::combine_n_readouts])))

        # create a event_numer index (important)
        if not hit_table.cols.event_number.is_indexed:  # index event_number column to speed up everything
            logging.info('Create event_number index')
            hit_table.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
            logging.info('Done')
        else:
            logging.info('Event_number index exists already')

        # initialize the analysis and set settings
        analyze_data = AnalyzeRawData()
        analyze_data.create_occupancy_hist = False
        analyze_data.create_bcid_hist = False

        # variables for read speed up
        index = 0  # index where to start the read out, 0 at the beginning, increased during looping
        max_chunk_size = 10000000  # max chunk size used, if too big you run out of RAM
        chunk_size = max_chunk_size

        # result data
        timestamp = np.empty(shape=(len(parameter_ranges),))
        mean_tot = np.empty(shape=(len(parameter_ranges),))

        # loop over the selected events
        for parameter_index, parameter_range in enumerate(parameter_ranges):
            logging.info('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[1]) + ',' + str(parameter_range[2]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')

            analyze_data.reset()  # resets the data of the last analysis

            # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
            readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
            for hits, index in data_aligned_at_events(hit_table, start_event_number=parameter_range[1], stop_event_number=parameter_range[2], start=index, chunk_size=chunk_size):
                analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                readout_hit_len += hits.shape[0]
            chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

            # get and store results
            timestamp[parameter_index] = parameter_range[0]
            tot_hist = np.zeros(16, dtype=np.uint32)  # initialize data structure
            analyze_data.histograming.get_tot_hist(tot_hist)  # get tot histogram
            mean_tot[parameter_index] = np.mean(tot_hist)

        # plot results
        plot_scatter(x=timestamp - np.amin(timestamp), y=mean_tot, title='Mean TOT development', x_label='relative time [s]', y_label='Mean TOT', marker_style='-o')


if __name__ == "__main__":
    scan_name = 'scan_fei4_trigger_gdac_0'
    folder = 'K:\\data\\FE-I4\\ChargeRecoMethod\\bias_20\\'
    input_file_hits = folder + scan_name + "_interpreted.h5"

    start_time = datetime.now()
    analyze_per_scan_parameter(input_file_hits)
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
