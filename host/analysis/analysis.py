"""This module makes a lot of analysis functions available.
"""

import logging
import re
from datetime import datetime
import sys
import os
import itertools
import time
import analysis_utils
import collections
import pandas as pd
from RawDataConverter import data_struct
import numpy as np
import tables as tb
import numexpr as ne
from plotting import plotting
from analyze_raw_data import AnalyzeRawData
from matplotlib.backends.backend_pdf import PdfPages
from operator import itemgetter
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.sparse import coo_matrix
from scipy.interpolate import splrep, splev

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def analyze_beam_spot(scan_base, combine_n_readouts=1000, max_chunk_size=10000000, plot_occupancy_hists=False, output_pdf=None, **kwarg):
    ''' Determines the mean x and y beam spot position as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts'). The occupancy is determined
    for the given combined events and stored into a pdf file. At the end the beam x and y is plotted into a scatter plot with absolute positions in um.

     Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    max_chunk_size: int
        the maximum chink size used during read, if too big memory error occurs, if too small analysis takes longer
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''
    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r+") as in_hit_file_h5:
            # get data and data pointer
            meta_data_array = in_hit_file_h5.root.meta_data[:]
            hit_table = in_hit_file_h5.root.Hits

            # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
            parameter_ranges = np.column_stack((meta_data_array['timestamp_start'][::combine_n_readouts], meta_data_array['timestamp_stop'][::combine_n_readouts], analysis_utils.get_event_range(meta_data_array['event_number'][::combine_n_readouts])))

            # create a event_numer index (important)
            analysis_utils.index_event_number(hit_table)

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_tot_hist = False
            analyze_data.create_bcid_hist = False

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            chunk_size = max_chunk_size

            # result data
            timestamp = np.empty(shape=(len(parameter_ranges),))
            occupancy = np.zeros(80 * 336 * 1, dtype=np.uint32)  # create linear array as it is created in histogram class

            x = []
            y = []

            # loop over the selected events
            for parameter_index, parameter_range in enumerate(parameter_ranges):
                logging.info('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[2]) + ',' + str(parameter_range[3]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')

                analyze_data.reset()  # resets the data of the last analysis

                # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
                readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=parameter_range[2], stop_event_number=parameter_range[3], start=index, chunk_size=chunk_size):
                    analyze_data.analyze_hits(hits, scan_parameter=False)  # analyze the selected hits in chunks
                    readout_hit_len += hits.shape[0]
                chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                # get and store results
                timestamp[parameter_index] = parameter_range[0]
                analyze_data.histograming.get_occupancy(occupancy)
                occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, analyze_data.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
                occupancy_array = np.swapaxes(occupancy_array, 0, 1)
                x.append(analysis_utils.get_mean_from_histogram(np.sum(occupancy_array, axis=0), bin_positions=range(0, 80)))
                y.append(analysis_utils.get_mean_from_histogram(np.sum(occupancy_array, axis=1), bin_positions=range(0, 336)))
                if plot_occupancy_hists:
                    plotting.plot_occupancy(occupancy_array[:, :, 0], title='Occupancy for events between ' + time.strftime('%H:%M:%S', time.localtime(parameter_range[0])) + ' and ' + time.strftime('%H:%M:%S', time.localtime(parameter_range[1])), filename=output_pdf)
            plotting.plot_scatter([i * 250 for i in x], [i * 50 for i in y], title='Mean beam position', x_label='x [um]', y_label='y [um]', marker_style='-o', filename=output_pdf)


def analyze_event_rate(scan_base, combine_n_readouts=1000, max_chunk_size=10000000, time_line_absolute=True, plot_occupancy_hists=False, output_pdf=None, **kwarg):
    ''' Determines the number of events as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts'). The number of events is taken from the meta data info
    and stored into a pdf file.

    Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    max_chunk_size: int
        the maximum chink size used during read, if too big memory error occurs, if too small analysis takes longer
    time_line_absolute: bool
        if true the analysis uses absolute time stamps
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''
    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r") as in_file_h5:
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_ranges = np.column_stack((meta_data_array['timestamp_start'][::combine_n_readouts], meta_data_array['timestamp_stop'][::combine_n_readouts], analysis_utils.get_event_range(meta_data_array['event_number'][::combine_n_readouts])))
            if time_line_absolute:
                x = parameter_ranges[:-1, 0] + (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]) / 2.
                plotting.plot_scatter_time(x, y=parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2], title='Events per time', filename=output_pdf)
            else:
                plotting.plot_scatter(x=(parameter_ranges[:-1, 0] + (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]) / 2. - parameter_ranges[0, 0]) / 60., y=parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2], title='Events per time', x_label='Progressed time [min.]', y_label='Events per time [a.u.]', filename=output_pdf)


def analyse_n_cluster_per_event(scan_base, combine_n_readouts=1000, max_chunk_size=10000000, plot_n_cluster_hists=False, output_pdf=None, **kwarg):
    ''' Determines the number of cluster per event as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts').

    Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    max_chunk_size: int
        the maximum chink size used during read, if too big memory error occurs, if too small analysis takes longer
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''

    x = []
    y = []

    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r+") as in_cluster_file_h5:
            # get data and data pointer
            meta_data_array = in_cluster_file_h5.root.meta_data[:]
            cluster_table = in_cluster_file_h5.root.Cluster

            # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
            parameter_ranges = np.column_stack((meta_data_array['timestamp_start'][::combine_n_readouts], meta_data_array['timestamp_stop'][::combine_n_readouts], analysis_utils.get_event_range(meta_data_array['event_number'][::combine_n_readouts])))

            # create a event_numer index (important)
            analysis_utils.index_event_number(cluster_table)

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_tot_hist = False
            analyze_data.create_bcid_hist = False

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            chunk_size = max_chunk_size

            # loop over the selected events
            for parameter_index, parameter_range in enumerate(parameter_ranges):
                logging.info('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[2]) + ',' + str(parameter_range[3]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')

                analyze_data.reset()  # resets the data of the last analysis

                # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
                readout_cluster_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                hist = None
                for clusters, index in analysis_utils.data_aligned_at_events(cluster_table, start_event_number=parameter_range[2], stop_event_number=parameter_range[3], start=index, chunk_size=chunk_size):
                    n_cluster_per_event = analysis_utils.get_n_cluster_in_events(clusters)[:, 1]  # array with the number of cluster per event, cluster per event are at least 1
                    if hist is None:
                        hist = np.histogram(n_cluster_per_event, bins=10, range=(0, 10))[0]
                    else:
                        hist = np.add(hist, np.histogram(n_cluster_per_event, bins=10, range=(0, 10))[0])
                    if parameter_range[3] is not None:  # happend for the last readout
                        hist[0] = (parameter_range[3] - parameter_range[2]) - len(n_cluster_per_event)  # add the events without any cluster
                    if plot_n_cluster_hists:
                        plotting.plot_1d_hist(hist, title='Number of cluster per event at ' + str(parameter_range[0]), x_axis_title='Number of cluster', y_axis_title='fraction', log_y=True, filename=output_pdf)
                    hist = hist.astype('f4') / np.sum(hist)  # calculate fraction from total numbers
                    readout_cluster_len += clusters.shape[0]
                chunk_size = int(1.5 * readout_cluster_len) if int(1.05 * readout_cluster_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                x.append(parameter_range[0])
                y.append(hist)

    plotting.plot_scatter_time(x, y, title='Number of cluster per event as a function of time', filename=output_pdf, legend=('0 cluster', '1 cluster', '2 cluster', '3 cluster'))


def select_hits_from_cluster_info(input_file_hits, output_file_hits, cluster_size_condition, n_cluster_condition):
    ''' Takes a hit table and stores only selected hits into a new table. The selection is done on an event base and events are selected if they have a certain number of cluster or cluster size.
    To increase the analysis speed a event index for the input hit file is created first.

     Parameters
    ----------
    input_file_hits: str
        the input file name with hits
    output_file_hits: str
        the output file name for the hits
    cluster_size_condition: str
        the cluster size condition to select events (e.g.: 'cluster_size_condition <= 2')
    n_cluster_condition: str
        the number of cluster in a event ((e.g.: 'n_cluster_condition == 1')
    '''

    with tb.openFile(input_file_hits, mode="r+") as in_hit_file_h5:
        analysis_utils.index_event_number(in_hit_file_h5.root.Hits)
        analysis_utils.index_event_number(in_hit_file_h5.root.Cluster)
        with tb.openFile(output_file_hits, mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            for data, _ in analysis_utils.data_aligned_at_events(cluster_table):
                selected_events_1 = analysis_utils.get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition=cluster_size_condition)  # select the events with clusters of a certain size
                selected_events_2 = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition=n_cluster_condition)  # select the events with a certain cluster number
                selected_events = selected_events_1[analysis_utils.in1d_sorted(selected_events_1, selected_events_2)]  # select events with both conditions above
                logging.info('Selected ' + str(len(selected_events)) + ' events with ' + n_cluster_condition + ' and ' + cluster_size_condition)
                last_word_number = analysis_utils.write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file


def histogram_tdc_hits(scan_bases):
    ''' This method takes the interpreted hit table, selects events with only one hit with one hit cluster and histograms the TDC info for these hits.
    The created TDC histogram is stored in a hdf5 file.

     Parameters
    ----------
    scan_bases: list of str
        has the scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    '''
    with tb.openFile(scan_bases + '_interpreted.h5', mode="r+") as in_hit_file_h5:  # select hits
        analysis_utils.index_event_number(in_hit_file_h5.root.Hits)
        with tb.openFile(scan_bases + '_selected_hits.h5', mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            for data, _ in analysis_utils.data_aligned_at_events(cluster_table):
                selected_events_1 = analysis_utils.get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition='cluster_size==1')  # select the events with clusters of a certain size
                selected_events_2 = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition='n_cluster==1')  # select the events with a certain cluster number
                selected_events = selected_events_1[analysis_utils.in1d_sorted(selected_events_1, selected_events_2)]  # select events with both conditions above
                logging.info('Selected ' + str(len(selected_events)) + ' events with  n_cluster==1 and cluster_size==1')
                last_word_number = analysis_utils.write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file
    # histogram selected hits
    with tb.openFile(scan_bases + '_selected_hits.h5', mode="r") as in_hit_file_h5:
        with tb.openFile(scan_bases + '_histograms.h5', mode="w") as out_file_histograms_h5:
            hits = in_hit_file_h5.root.Hits[:]
            pixel = hits[:]['row'] + hits[:]['column'] * 335  # make 2d -> 1d hist to be able to use the supported 2d sparse matrix
            tdc_hist_per_pixel = coo_matrix((np.ones(shape=(len(pixel,)), dtype=np.uint8), (pixel, hits[:]['TDC'])), shape=(80 * 336, 4096)).todense()  # use sparse matrix to keep memory usage decend
            tdc_hist_array = out_file_histograms_h5.createCArray(out_file_histograms_h5.root, name='HistTdc', title='TDC Histograms', atom=tb.Atom.from_dtype(tdc_hist_per_pixel.dtype), shape=tdc_hist_per_pixel.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            tdc_hist_array[:] = tdc_hist_per_pixel


if __name__ == "__main__":
    print 'run analysis as main'
