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
    x = []
    y = []
    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r+") as in_hit_file_h5:
            # get data and data pointer
            meta_data_array = in_hit_file_h5.root.meta_data[:]
            hit_table = in_hit_file_h5.root.Hits

            # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
            parameter_ranges = np.column_stack((analysis_utils.get_ranges_from_array(meta_data_array['timestamp_start'][::combine_n_readouts]), analysis_utils.get_ranges_from_array(meta_data_array['event_number'][::combine_n_readouts])))

            # create a event_numer index (important)
            analysis_utils.index_event_number(hit_table)

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_tot_hist = False
            analyze_data.create_bcid_hist = False
            analyze_data.histograming.set_no_scan_parameter()

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            chunk_size = max_chunk_size

            # result data
            occupancy = np.zeros(80 * 336 * 1, dtype=np.uint32)  # create linear array as it is created in histogram class

            # loop over the selected events
            for parameter_index, parameter_range in enumerate(parameter_ranges):
                logging.info('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[2]) + ',' + str(parameter_range[3]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')

                analyze_data.reset()  # resets the data of the last analysis

                # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
                readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=parameter_range[2], stop_event_number=parameter_range[3], start=index, chunk_size=chunk_size):
                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                    readout_hit_len += hits.shape[0]
                chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                # get and store results
                analyze_data.histograming.get_occupancy(occupancy)
                occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, analyze_data.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
                occupancy_array = np.swapaxes(occupancy_array, 0, 1)
                projection_x = np.sum(occupancy_array, axis=0).ravel()
                projection_y = np.sum(occupancy_array, axis=1).ravel()
                x.append(analysis_utils.get_mean_from_histogram(projection_x, bin_positions=range(0, 80)))
                y.append(analysis_utils.get_mean_from_histogram(projection_y, bin_positions=range(0, 336)))
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
    x = []
    y = []

    start_time_set = False

    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r") as in_file_h5:
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_ranges = np.column_stack((analysis_utils.get_ranges_from_array(meta_data_array['timestamp_start'][::combine_n_readouts]), analysis_utils.get_ranges_from_array(meta_data_array['event_number'][::combine_n_readouts])))

            if time_line_absolute:
                x.extend(parameter_ranges[:-1, 0])
                y.extend((parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2]) / (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]))  # d#Events / dt
            else:
                if not start_time_set:
                    start_time = parameter_ranges[0, 0]
                    start_time_set = True
                x.extend((parameter_ranges[:-1, 0] - start_time) / 60.)
                y.extend((parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2]) / (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]))  # d#Events / dt
#                 y.extend(parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2])
    if time_line_absolute:
        plotting.plot_scatter_time(x, y, title='Event rate [Hz]', filename=output_pdf)
    else:
        plotting.plot_scatter(x, y, title='Events per time', x_label='Progressed time [min.]', y_label='Events rate [Hz]', filename=output_pdf)


def analyse_n_cluster_per_event(scan_base, include_no_cluster=False, time_line_absolute=True, combine_n_readouts=1000, max_chunk_size=10000000, plot_n_cluster_hists=False, output_pdf=None, **kwarg):
    ''' Determines the number of cluster per event as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts').

    Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    include_no_cluster: bool
        Set to true to also consider all events without any hit.
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    max_chunk_size: int
        the maximum chink size used during read, if too big memory error occurs, if too small analysis takes longer
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''

    x = []
    y = []

    start_time_set = False

    for data_file in scan_base:
        with tb.openFile(data_file + '_interpreted.h5', mode="r+") as in_cluster_file_h5:
            # get data and data pointer
            meta_data_array = in_cluster_file_h5.root.meta_data[:]
            cluster_table = in_cluster_file_h5.root.Cluster

            # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
            parameter_ranges = np.column_stack((analysis_utils.get_ranges_from_array(meta_data_array['timestamp_start'][::combine_n_readouts]), analysis_utils.get_ranges_from_array(meta_data_array['event_number'][::combine_n_readouts])))

            # create a event_numer index (important)
            analysis_utils.index_event_number(cluster_table)

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_tot_hist = False
            analyze_data.create_bcid_hist = False

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            chunk_size = max_chunk_size

            total_cluster = cluster_table.shape[0]

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
                    if include_no_cluster and parameter_range[3] is not None:  # happend for the last readout
                        hist[0] = (parameter_range[3] - parameter_range[2]) - len(n_cluster_per_event)  # add the events without any cluster
                    readout_cluster_len += clusters.shape[0]
                    total_cluster -= len(clusters)
                chunk_size = int(1.5 * readout_cluster_len) if int(1.05 * readout_cluster_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                if plot_n_cluster_hists:
                    plotting.plot_1d_hist(hist, title='Number of cluster per event at ' + str(parameter_range[0]), x_axis_title='Number of cluster', y_axis_title='#', log_y=True, filename=output_pdf)
                hist = hist.astype('f4') / np.sum(hist)  # calculate fraction from total numbers

                if time_line_absolute:
                    x.append(parameter_range[0])
                else:
                    if not start_time_set:
                        start_time = parameter_ranges[0, 0]
                        start_time_set = True
                    x.append((parameter_range[0] - start_time) / 60.)
                y.append(hist)

            if total_cluster != 0:
                logging.warning('Not all clusters were selected during analysis. Analysis is therefore not exact')

    if time_line_absolute:
        plotting.plot_scatter_time(x, y, title='Number of cluster per event as a function of time', filename=output_pdf, legend=('0 cluster', '1 cluster', '2 cluster', '3 cluster') if include_no_cluster else ('0 cluster not plotted', '1 cluster', '2 cluster', '3 cluster'))
    else:
        plotting.plot_scatter(x, y, title='Number of cluster per event as a function of time', x_label='time [min.]', filename=output_pdf, legend=('0 cluster', '1 cluster', '2 cluster', '3 cluster') if include_no_cluster else ('0 cluster not plotted', '1 cluster', '2 cluster', '3 cluster'))


def select_hits_from_cluster_info(input_file_hits, output_file_hits, cluster_size_condition, n_cluster_condition, output_pdf=None, **kwarg):
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
    logging.info('Write hits of events from ' + str(input_file_hits) + ' with ' + cluster_size_condition + ' and ' + n_cluster_condition + ' into ' + str(output_file_hits))
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


def histogram_tdc_hits(scan_bases, output_pdf=None, **kwarg):
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


def analyze_cluster_size_per_scan_parameter(scan_bases, output_file_cluster_size, parameter='GDAC', max_chunk_size=10000000, overwrite_output_files=False, output_pdf=None, **kwarg):
    ''' This method takes multiple hit files and determines the cluster size for different scan parameter values of

     Parameters
    ----------
    scan_bases: list of str
        has the scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    output_file_cluster_size: str
        The data file with the results
    parameter: int
        The name of the parameter to separate the data into (e.g.: PlsrDAC)
    max_chunk_size: int
        the maximum chink size used during read, if too big memory error occurs, if too small analysis takes longer
    overwrite_output_files: bool
        Set to true to overwrite the output file if it already exists
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''
    logging.info('Analyze the cluster sizes for different ' + parameter + ' settings for ' + str(len(scan_bases)) + ' different files')
    if os.path.isfile(output_file_cluster_size) and not overwrite_output_files:  # skip analysis if already done
            logging.info('Analyzed cluster size file ' + output_file_cluster_size + ' already exists. Skip cluster size analysis.')
    else:
        with tb.openFile(output_file_cluster_size, mode="w") as out_file_h5:  # file to write the data into
            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)  # compression of the written data
            parameter_goup = out_file_h5.createGroup(out_file_h5.root, parameter, title=parameter)  # note to store the data
            cluster_size_total = None  # final array for the cluster size per GDAC
            for index in range(0, len(scan_bases)):  # loop over all hit files
                with tb.openFile(scan_bases[index], mode="r+") as in_hit_file_h5:  # open the actual hit file
                    meta_data_array = in_hit_file_h5.root.meta_data[:]
                    scan_parameter = analysis_utils.get_scan_parameter(meta_data_array)  # get the scan parameters
                    if scan_parameter:  # if a GDAC scan parameter was used analyze the cluster size per GDAC setting
                        scan_parameter_values = scan_parameter.itervalues().next()  # scan parameter settings used
                        if len(scan_parameter_values) == 1:  # only analyze per scan step if there are more than one scan step
                            logging.info('Extract from ' + scan_bases[index] + ' the cluster size for ' + parameter + ' = ' + str(scan_parameter_values[0]))
                            cluster_size_hist = in_hit_file_h5.root.HistClusterSize[:]
                            plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + parameter + ' =' + str(scan_parameter_values[0]), filename=output_pdf)
                            if cluster_size_total is None:  # true if no data was appended to the array yet
                                cluster_size_total = cluster_size_hist
                            else:
                                cluster_size_total = np.vstack([cluster_size_total, cluster_size_hist])
                            actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=parameter + '_' + str(scan_parameter_values[0]), title=parameter + '_' + str(scan_parameter_values[0]))
                            cluster_size_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                            cluster_size_hist_table[:] = cluster_size_hist
                        else:
                            logging.info('Analyze ' + scan_bases[index] + ' per scan parameter ' + parameter + ' for ' + str(len(scan_parameter_values)) + ' values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
                            event_numbers = analysis_utils.get_meta_data_at_scan_parameter(meta_data_array, parameter)['event_number']  # get the event numbers in meta_data where the scan parameter changes
                            parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_ranges_from_array(event_numbers)))
                            hit_table = in_hit_file_h5.root.Hits
                            analysis_utils.index_event_number(hit_table)
                            total_hits = 0
                            total_hits_2 = 0
                            index = 0  # index where to start the read out, 0 at the beginning
                            chunk_size = max_chunk_size
                            # initialize the analysis and set settings
                            analyze_data = AnalyzeRawData()
                            analyze_data.create_cluster_size_hist = True
                            analyze_data.create_cluster_tot_hist = True
                            analyze_data.histograming.set_no_scan_parameter()  # one has to tell the histogramer the # of scan parameters for correct occupancy hist allocation
                            for parameter_index, parameter_range in enumerate(parameter_ranges):  # loop over the selected events
                                analyze_data.reset()  # resets the data of the last analysis
                                logging.info('Analyze GDAC = ' + str(parameter_range[0]) + ' ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.))) + '%')
                                start_event_number = parameter_range[1]
                                stop_event_number = parameter_range[2]
                                logging.info('Data from events = [' + str(start_event_number) + ',' + str(stop_event_number) + '[')
                                actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=parameter + '_' + str(parameter_range[0]), title=parameter + '_' + str(parameter_range[0]))
                                # loop over the hits in the actual selected events with optimizations: variable chunk size, start word index given
                                readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                                for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start=index, chunk_size=chunk_size):
                                    total_hits += hits.shape[0]
                                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                                    readout_hit_len += hits.shape[0]
                                chunk_size = int(1.05 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                                if chunk_size < 50:  # limit the lower chunk size, there can always be a crazy event with more than 20 hits
                                    chunk_size = 50
                                # get occupancy hist
                                occupancy = np.zeros(80 * 336 * analyze_data.histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
                                analyze_data.histograming.get_occupancy(occupancy)  # just here to check histograming is consistend

                                # store and plot cluster size hist
                                cluster_size_hist = np.zeros(1024, dtype=np.uint32)
                                analyze_data.clusterizer.get_cluster_size_hist(cluster_size_hist)
                                cluster_size_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                                cluster_size_hist_table[:] = cluster_size_hist
                                plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + parameter + ' = ' + str(scan_parameter_values[parameter_index]), filename=output_pdf)
                                if cluster_size_total is None:  # true if no data was appended to the array yet
                                    cluster_size_total = cluster_size_hist
                                else:
                                    cluster_size_total = np.vstack([cluster_size_total, cluster_size_hist])

                                total_hits_2 += np.sum(occupancy)

                            if total_hits != total_hits_2:
                                logging.warning('Analysis shows inconsistent number of hits. Check needed!')
                            logging.info('Analyzed %d hits!' % total_hits)
                    else:  # no scan parameter is given, therefore the data file contains hits of only one GDAC setting and no analysis is necessary
                        parameter_value = analysis_utils.get_parameter_value_from_file_names([scan_bases[index]], parameter).keys()[0]  # get the parameter value from the file name
                        logging.info('Extract from ' + scan_bases[index] + ' the cluster size for ' + parameter + ' = ' + str(parameter_value))
                        cluster_size_hist = in_hit_file_h5.root.HistClusterSize[:]
                        plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + parameter + ' =' + str(parameter_value), filename=output_pdf)
                        if cluster_size_total is None:  # true if no data was appended to the array yet
                            cluster_size_total = cluster_size_hist
                        else:
                            cluster_size_total = np.vstack([cluster_size_total, cluster_size_hist])
                        actual_parameter_group = out_file_h5.createGroup(parameter_goup, name=parameter + '_' + str(parameter_value), title=parameter + '_' + str(parameter_value))
                        cluster_size_hist_table = out_file_h5.createCArray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                        cluster_size_hist_table[:] = cluster_size_hist
            cluster_size_total_out = out_file_h5.createCArray(out_file_h5.root, name='AllHistClusterSize', title='All Cluster Size Histograms', atom=tb.Atom.from_dtype(cluster_size_total.dtype), shape=cluster_size_total.shape, filters=filter_table)
            cluster_size_total_out[:] = cluster_size_total


if __name__ == "__main__":
    print 'run analysis as main'
