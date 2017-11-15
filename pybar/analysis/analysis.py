"""This module makes a lot of analysis functions available.
"""
from __future__ import division

import logging
import os
import time
import zlib

import numpy as np
import tables as tb
import re

import progressbar

from pybar_fei4_interpreter import data_struct
from pybar_fei4_interpreter.data_histograming import PyDataHistograming

from pybar.analysis import analysis_utils
from pybar.analysis.plotting import plotting
from pybar.analysis.analyze_raw_data import AnalyzeRawData


def analyze_beam_spot(scan_base, combine_n_readouts=1000, chunk_size=10000000, plot_occupancy_hists=False, output_pdf=None, output_file=None):
    ''' Determines the mean x and y beam spot position as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts'). The occupancy is determined
    for the given combined events and stored into a pdf file. At the end the beam x and y is plotted into a scatter plot with absolute positions in um.

     Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    max_chunk_size: int
        the maximum chunk size used during read, if too big memory error occurs, if too small analysis takes longer
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''
    time_stamp = []
    x = []
    y = []

    for data_file in scan_base:
        with tb.open_file(data_file + '_interpreted.h5', mode="r+") as in_hit_file_h5:
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
            analyze_data.histogram.set_no_scan_parameter()

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            best_chunk_size = chunk_size

            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=hit_table.shape[0], term_width=80)
            progress_bar.start()

            # loop over the selected events
            for parameter_index, parameter_range in enumerate(parameter_ranges):
                logging.debug('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[2]) + ',' + str(parameter_range[3]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.0))) + '%')
                analyze_data.reset()  # resets the data of the last analysis

                # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
                readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=parameter_range[2], stop_event_number=parameter_range[3], start_index=index, chunk_size=best_chunk_size):
                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                    readout_hit_len += hits.shape[0]
                    progress_bar.update(index)
                best_chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < chunk_size else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                # get and store results
                occupancy_array = analyze_data.histogram.get_occupancy()
                projection_x = np.sum(occupancy_array, axis=0).ravel()
                projection_y = np.sum(occupancy_array, axis=1).ravel()
                x.append(analysis_utils.get_mean_from_histogram(projection_x, bin_positions=range(0, 80)))
                y.append(analysis_utils.get_mean_from_histogram(projection_y, bin_positions=range(0, 336)))
                time_stamp.append(parameter_range[0])
                if plot_occupancy_hists:
                    plotting.plot_occupancy(occupancy_array[:, :, 0], title='Occupancy for events between ' + time.strftime('%H:%M:%S', time.localtime(parameter_range[0])) + ' and ' + time.strftime('%H:%M:%S', time.localtime(parameter_range[1])), filename=output_pdf)
            progress_bar.finish()
    plotting.plot_scatter([i * 250 for i in x], [i * 50 for i in y], title='Mean beam position', x_label='x [um]', y_label='y [um]', marker_style='-o', filename=output_pdf)
    if output_file:
        with tb.open_file(output_file, mode="a") as out_file_h5:
            rec_array = np.array(zip(time_stamp, x, y), dtype=[('time_stamp', float), ('x', float), ('y', float)])
            try:
                beam_spot_table = out_file_h5.create_table(out_file_h5.root, name='Beamspot', description=rec_array, title='Beam spot position', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                beam_spot_table[:] = rec_array
            except tb.exceptions.NodeError:
                logging.warning(output_file + ' has already a Beamspot note, do not overwrite existing.')
    return time_stamp, x, y


def analyze_event_rate(scan_base, combine_n_readouts=1000, time_line_absolute=True, output_pdf=None, output_file=None):
    ''' Determines the number of events as a function of time. Therefore the data of a fixed number of read outs are combined ('combine_n_readouts'). The number of events is taken from the meta data info
    and stored into a pdf file.

    Parameters
    ----------
    scan_base: list of str
        scan base names (e.g.:  ['//data//SCC_50_fei4_self_trigger_scan_390', ]
    combine_n_readouts: int
        the number of read outs to combine (e.g. 1000)
    time_line_absolute: bool
        if true the analysis uses absolute time stamps
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''
    time_stamp = []
    rate = []

    start_time_set = False

    for data_file in scan_base:
        with tb.open_file(data_file + '_interpreted.h5', mode="r") as in_file_h5:
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_ranges = np.column_stack((analysis_utils.get_ranges_from_array(meta_data_array['timestamp_start'][::combine_n_readouts]), analysis_utils.get_ranges_from_array(meta_data_array['event_number'][::combine_n_readouts])))

            if time_line_absolute:
                time_stamp.extend(parameter_ranges[:-1, 0])
            else:
                if not start_time_set:
                    start_time = parameter_ranges[0, 0]
                    start_time_set = True
                time_stamp.extend((parameter_ranges[:-1, 0] - start_time) / 60.0)
            rate.extend((parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2]) / (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]))  # d#Events / dt
    if time_line_absolute:
        plotting.plot_scatter_time(time_stamp, rate, title='Event rate [Hz]', marker_style='o', filename=output_pdf)
    else:
        plotting.plot_scatter(time_stamp, rate, title='Events per time', x_label='Progressed time [min.]', y_label='Events rate [Hz]', marker_style='o', filename=output_pdf)
    if output_file:
        with tb.open_file(output_file, mode="a") as out_file_h5:
            rec_array = np.array(zip(time_stamp, rate), dtype=[('time_stamp', float), ('rate', float)]).view(np.recarray)
            try:
                rate_table = out_file_h5.create_table(out_file_h5.root, name='Eventrate', description=rec_array, title='Event rate', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                rate_table[:] = rec_array
            except tb.exceptions.NodeError:
                logging.warning(output_file + ' has already a Eventrate note, do not overwrite existing.')
    return time_stamp, rate


def analyse_n_cluster_per_event(scan_base, include_no_cluster=False, time_line_absolute=True, combine_n_readouts=1000, chunk_size=10000000, plot_n_cluster_hists=False, output_pdf=None, output_file=None):
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
        the maximum chunk size used during read, if too big memory error occurs, if too small analysis takes longer
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen
    '''

    time_stamp = []
    n_cluster = []

    start_time_set = False

    for data_file in scan_base:
        with tb.open_file(data_file + '_interpreted.h5', mode="r+") as in_cluster_file_h5:
            # get data and data pointer
            meta_data_array = in_cluster_file_h5.root.meta_data[:]
            cluster_table = in_cluster_file_h5.root.Cluster

            # determine the event ranges to analyze (timestamp_start, start_event_number, stop_event_number)
            parameter_ranges = np.column_stack((analysis_utils.get_ranges_from_array(meta_data_array['timestamp_start'][::combine_n_readouts]), analysis_utils.get_ranges_from_array(meta_data_array['event_number'][::combine_n_readouts])))

            # create a event_numer index (important for speed)
            analysis_utils.index_event_number(cluster_table)

            # initialize the analysis and set settings
            analyze_data = AnalyzeRawData()
            analyze_data.create_tot_hist = False
            analyze_data.create_bcid_hist = False

            # variables for read speed up
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping
            best_chunk_size = chunk_size

            total_cluster = cluster_table.shape[0]

            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=total_cluster, term_width=80)
            progress_bar.start()

            # loop over the selected events
            for parameter_index, parameter_range in enumerate(parameter_ranges):
                logging.debug('Analyze time stamp ' + str(parameter_range[0]) + ' and data from events = [' + str(parameter_range[2]) + ',' + str(parameter_range[3]) + '[ ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.0))) + '%')
                analyze_data.reset()  # resets the data of the last analysis

                # loop over the cluster in the actual selected events with optimizations: determine best chunk size, start word index given
                readout_cluster_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                hist = None
                for clusters, index in analysis_utils.data_aligned_at_events(cluster_table, start_event_number=parameter_range[2], stop_event_number=parameter_range[3], start_index=index, chunk_size=best_chunk_size):
                    n_cluster_per_event = analysis_utils.get_n_cluster_in_events(clusters['event_number'])[:, 1]  # array with the number of cluster per event, cluster per event are at least 1
                    if hist is None:
                        hist = np.histogram(n_cluster_per_event, bins=10, range=(0, 10))[0]
                    else:
                        hist = np.add(hist, np.histogram(n_cluster_per_event, bins=10, range=(0, 10))[0])
                    if include_no_cluster and parameter_range[3] is not None:  # happend for the last readout
                        hist[0] = (parameter_range[3] - parameter_range[2]) - len(n_cluster_per_event)  # add the events without any cluster
                    readout_cluster_len += clusters.shape[0]
                    total_cluster -= len(clusters)
                    progress_bar.update(index)
                best_chunk_size = int(1.5 * readout_cluster_len) if int(1.05 * readout_cluster_len) < chunk_size else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction

                if plot_n_cluster_hists:
                    plotting.plot_1d_hist(hist, title='Number of cluster per event at ' + str(parameter_range[0]), x_axis_title='Number of cluster', y_axis_title='#', log_y=True, filename=output_pdf)
                hist = hist.astype('f4') / np.sum(hist)  # calculate fraction from total numbers

                if time_line_absolute:
                    time_stamp.append(parameter_range[0])
                else:
                    if not start_time_set:
                        start_time = parameter_ranges[0, 0]
                        start_time_set = True
                    time_stamp.append((parameter_range[0] - start_time) / 60.0)
                n_cluster.append(hist)
            progress_bar.finish()
            if total_cluster != 0:
                logging.warning('Not all clusters were selected during analysis. Analysis is therefore not exact')

    if time_line_absolute:
        plotting.plot_scatter_time(time_stamp, n_cluster, title='Number of cluster per event as a function of time', marker_style='o', filename=output_pdf, legend=('0 cluster', '1 cluster', '2 cluster', '3 cluster') if include_no_cluster else ('0 cluster not plotted', '1 cluster', '2 cluster', '3 cluster'))
    else:
        plotting.plot_scatter(time_stamp, n_cluster, title='Number of cluster per event as a function of time', x_label='time [min.]', marker_style='o', filename=output_pdf, legend=('0 cluster', '1 cluster', '2 cluster', '3 cluster') if include_no_cluster else ('0 cluster not plotted', '1 cluster', '2 cluster', '3 cluster'))
    if output_file:
        with tb.open_file(output_file, mode="a") as out_file_h5:
            cluster_array = np.array(n_cluster)
            rec_array = np.array(zip(time_stamp, cluster_array[:, 0], cluster_array[:, 1], cluster_array[:, 2], cluster_array[:, 3], cluster_array[:, 4], cluster_array[:, 5]), dtype=[('time_stamp', float), ('cluster_0', float), ('cluster_1', float), ('cluster_2', float), ('cluster_3', float), ('cluster_4', float), ('cluster_5', float)]).view(np.recarray)
            try:
                n_cluster_table = out_file_h5.create_table(out_file_h5.root, name='n_cluster', description=rec_array, title='Cluster per event', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                n_cluster_table[:] = rec_array
            except tb.exceptions.NodeError:
                logging.warning(output_file + ' has already a Beamspot note, do not overwrite existing.')
    return time_stamp, n_cluster


def select_hits_from_cluster_info(input_file_hits, output_file_hits, cluster_size_condition, n_cluster_condition, chunk_size=4000000):
    ''' Takes a hit table and stores only selected hits into a new table. The selection is done on an event base and events are selected if they have a certain number of cluster or cluster size.
    To increase the analysis speed a event index for the input hit file is created first. Since a cluster hit table can be created to this way of hit selection is
    not needed anymore.

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
    with tb.open_file(input_file_hits, mode="r+") as in_hit_file_h5:
        analysis_utils.index_event_number(in_hit_file_h5.root.Hits)
        analysis_utils.index_event_number(in_hit_file_h5.root.Cluster)
        with tb.open_file(output_file_hits, mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.create_table(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=cluster_table.shape[0], term_width=80)
            progress_bar.start()
            for data, index in analysis_utils.data_aligned_at_events(cluster_table, chunk_size=chunk_size):
                selected_events_1 = analysis_utils.get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition=cluster_size_condition)  # select the events with clusters of a certain size
                selected_events_2 = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition=n_cluster_condition)  # select the events with a certain cluster number
                selected_events = analysis_utils.get_events_in_both_arrays(selected_events_1, selected_events_2)  # select events with both conditions above
                logging.debug('Selected ' + str(len(selected_events)) + ' events with ' + n_cluster_condition + ' and ' + cluster_size_condition)
                last_word_number = analysis_utils.write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
                progress_bar.update(index)
            progress_bar.finish()
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file


def select_hits(input_file_hits, output_file_hits, condition=None, cluster_size_condition=None, n_cluster_condition=None, chunk_size=5000000):
    ''' Takes a hit table and stores only selected hits into a new table. The selection of hits is done with a numexp string. Only if
    this expression evaluates to true the hit is taken. One can also select hits from cluster conditions. This selection is done
    on an event basis, meaning events are selected where the cluster condition is true and then hits of these events are taken.

     Parameters
    ----------
    input_file_hits: str
        the input file name with hits
    output_file_hits: str
        the output file name for the hits
    condition: str
        Numexpr string to select hits (e.g.: '(relative_BCID == 6) & (column == row)')
        All hit infos can be used (column, row, ...)
    cluster_size_condition: int
        Hit of events with the given cluster size are selected.
    n_cluster_condition: int
        Hit of events with the given cluster number are selected.
    '''
    logging.info('Write hits with ' + condition + ' into ' + str(output_file_hits))
    if cluster_size_condition is None and n_cluster_condition is None:  # no cluster cuts are done
        with tb.open_file(input_file_hits, mode="r+") as in_hit_file_h5:
            analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create event index for faster selection
            with tb.open_file(output_file_hits, mode="w") as out_hit_file_h5:
                hit_table_out = out_hit_file_h5.create_table(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                analysis_utils.write_hits_in_event_range(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, condition=condition)  # write the hits of the selected events into a new table
                in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file
    else:
        with tb.open_file(input_file_hits, mode="r+") as in_hit_file_h5:  # open file with hit/cluster data with r+ to be able to create index
            analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create event index for faster selection
            analysis_utils.index_event_number(in_hit_file_h5.root.Cluster)  # create event index for faster selection
            with tb.open_file(output_file_hits, mode="w") as out_hit_file_h5:
                hit_table_out = out_hit_file_h5.create_table(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                cluster_table = in_hit_file_h5.root.Cluster
                last_word_number = 0
                progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=cluster_table.shape[0], term_width=80)
                progress_bar.start()
                for data, index in analysis_utils.data_aligned_at_events(cluster_table, chunk_size=chunk_size):
                    if cluster_size_condition is not None:
                        selected_events = analysis_utils.get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition='cluster_size == ' + str(cluster_size_condition))  # select the events with only 1 hit cluster
                        if n_cluster_condition is not None:
                            selected_events_2 = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition='n_cluster == ' + str(n_cluster_condition))  # select the events with only 1 cluster
                            selected_events = selected_events[analysis_utils.in1d_events(selected_events, selected_events_2)]  # select events with the first two conditions above
                    elif n_cluster_condition is not None:
                        selected_events = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition='n_cluster == ' + str(n_cluster_condition))
                    else:
                        raise RuntimeError('Cannot understand cluster selection criterion')
                    last_word_number = analysis_utils.write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number, condition=condition, chunk_size=chunk_size)  # write the hits of the selected events into a new table
                    progress_bar.update(index)
                progress_bar.finish()
                in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file


def analyze_cluster_size_per_scan_parameter(input_file_hits, output_file_cluster_size, parameter='GDAC', max_chunk_size=10000000, overwrite_output_files=False, output_pdf=None):
    ''' This method takes multiple hit files and determines the cluster size for different scan parameter values of

     Parameters
    ----------
    input_files_hits: string
    output_file_cluster_size: string
        The data file with the results
    parameter: string
        The name of the parameter to separate the data into (e.g.: PlsrDAC)
    max_chunk_size: int
        the maximum chunk size used during read, if too big memory error occurs, if too small analysis takes longer
    overwrite_output_files: bool
        Set to true to overwrite the output file if it already exists
    output_pdf: PdfPages
        PdfPages file object, if none the plot is printed to screen, if False nothing is printed
    '''
    logging.info('Analyze the cluster sizes for different ' + parameter + ' settings for ' + input_file_hits)
    if os.path.isfile(output_file_cluster_size) and not overwrite_output_files:  # skip analysis if already done
        logging.info('Analyzed cluster size file ' + output_file_cluster_size + ' already exists. Skip cluster size analysis.')
    else:
        with tb.open_file(output_file_cluster_size, mode="w") as out_file_h5:  # file to write the data into
            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)  # compression of the written data
            parameter_goup = out_file_h5.create_group(out_file_h5.root, parameter, title=parameter)  # note to store the data
            cluster_size_total = None  # final array for the cluster size per GDAC
            with tb.open_file(input_file_hits, mode="r+") as in_hit_file_h5:  # open the actual hit file
                meta_data_array = in_hit_file_h5.root.meta_data[:]
                scan_parameter = analysis_utils.get_scan_parameter(meta_data_array)  # get the scan parameters
                if scan_parameter:  # if a GDAC scan parameter was used analyze the cluster size per GDAC setting
                    scan_parameter_values = scan_parameter[parameter]  # scan parameter settings used
                    if len(scan_parameter_values) == 1:  # only analyze per scan step if there are more than one scan step
                        logging.warning('The file ' + str(input_file_hits) + ' has no different ' + str(parameter) + ' parameter values. Omit analysis.')
                    else:
                        logging.info('Analyze ' + input_file_hits + ' per scan parameter ' + parameter + ' for ' + str(len(scan_parameter_values)) + ' values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
                        event_numbers = analysis_utils.get_meta_data_at_scan_parameter(meta_data_array, parameter)['event_number']  # get the event numbers in meta_data where the scan parameter changes
                        parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_ranges_from_array(event_numbers)))
                        hit_table = in_hit_file_h5.root.Hits
                        analysis_utils.index_event_number(hit_table)
                        total_hits, total_hits_2, index = 0, 0, 0
                        chunk_size = max_chunk_size
                        # initialize the analysis and set settings
                        analyze_data = AnalyzeRawData()
                        analyze_data.create_cluster_size_hist = True
                        analyze_data.create_cluster_tot_hist = True
                        analyze_data.histogram.set_no_scan_parameter()  # one has to tell histogram the # of scan parameters for correct occupancy hist allocation
                        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=hit_table.shape[0], term_width=80)
                        progress_bar.start()
                        for parameter_index, parameter_range in enumerate(parameter_ranges):  # loop over the selected events
                            analyze_data.reset()  # resets the data of the last analysis
                            logging.debug('Analyze GDAC = ' + str(parameter_range[0]) + ' ' + str(int(float(float(parameter_index) / float(len(parameter_ranges)) * 100.0))) + '%')
                            start_event_number = parameter_range[1]
                            stop_event_number = parameter_range[2]
                            logging.debug('Data from events = [' + str(start_event_number) + ',' + str(stop_event_number) + '[')
                            actual_parameter_group = out_file_h5.create_group(parameter_goup, name=parameter + '_' + str(parameter_range[0]), title=parameter + '_' + str(parameter_range[0]))
                            # loop over the hits in the actual selected events with optimizations: variable chunk size, start word index given
                            readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                            for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start_index=index, chunk_size=chunk_size):
                                total_hits += hits.shape[0]
                                analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks
                                readout_hit_len += hits.shape[0]
                                progress_bar.update(index)
                            chunk_size = int(1.05 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                            if chunk_size < 50:  # limit the lower chunk size, there can always be a crazy event with more than 20 hits
                                chunk_size = 50
                            # get occupancy hist
                            occupancy = analyze_data.histogram.get_occupancy()  # just check here if histogram is consistent

                            # store and plot cluster size hist
                            cluster_size_hist = analyze_data.clusterizer.get_cluster_size_hist()
                            cluster_size_hist_table = out_file_h5.create_carray(actual_parameter_group, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(cluster_size_hist.dtype), shape=cluster_size_hist.shape, filters=filter_table)
                            cluster_size_hist_table[:] = cluster_size_hist
                            if output_pdf is not False:
                                plotting.plot_cluster_size(hist=cluster_size_hist, title='Cluster size (' + str(np.sum(cluster_size_hist)) + ' entries) for ' + parameter + ' = ' + str(scan_parameter_values[parameter_index]), filename=output_pdf)
                            if cluster_size_total is None:  # true if no data was appended to the array yet
                                cluster_size_total = cluster_size_hist
                            else:
                                cluster_size_total = np.vstack([cluster_size_total, cluster_size_hist])

                            total_hits_2 += np.sum(occupancy)
                        progress_bar.finish()
                        if total_hits != total_hits_2:
                            logging.warning('Analysis shows inconsistent number of hits. Check needed!')
                        logging.info('Analyzed %d hits!', total_hits)
            cluster_size_total_out = out_file_h5.create_carray(out_file_h5.root, name='AllHistClusterSize', title='All Cluster Size Histograms', atom=tb.Atom.from_dtype(cluster_size_total.dtype), shape=cluster_size_total.shape, filters=filter_table)
            cluster_size_total_out[:] = cluster_size_total


def histogram_cluster_table(analyzed_data_file, output_file, chunk_size=10000000):
    '''Reads in the cluster info table in chunks and histograms the seed pixels into one occupancy array.
    The 3rd dimension of the occupancy array is the number of different scan parameters used

    Parameters
    ----------
    analyzed_data_file : string
        HDF5 filename of the file containing the cluster table. If a scan parameter is given in the meta data, the occupancy histogramming is done per scan parameter step.

    Returns
    -------
    occupancy_array: numpy.array with dimensions (col, row, #scan_parameter)
    '''

    with tb.open_file(analyzed_data_file, mode="r") as in_file_h5:
        with tb.open_file(output_file, mode="w") as out_file_h5:
            histogram = PyDataHistograming()
            histogram.create_occupancy_hist(True)
            scan_parameters = None
            event_number_indices = None
            scan_parameter_indices = None
            try:
                meta_data = in_file_h5.root.meta_data[:]
                scan_parameters = analysis_utils.get_unique_scan_parameter_combinations(meta_data)
                if scan_parameters is not None:
                    scan_parameter_indices = np.array(range(0, len(scan_parameters)), dtype='u4')
                    event_number_indices = np.ascontiguousarray(scan_parameters['event_number']).astype(np.uint64)
                    histogram.add_meta_event_index(event_number_indices, array_length=len(scan_parameters['event_number']))
                    histogram.add_scan_parameter(scan_parameter_indices)
                    logging.info("Add %d different scan parameter(s) for analysis", len(scan_parameters))
                else:
                    logging.info("No scan parameter data provided")
                    histogram.set_no_scan_parameter()
            except tb.exceptions.NoSuchNodeError:
                logging.info("No meta data provided, use no scan parameter")
                histogram.set_no_scan_parameter()

            logging.info('Histogram cluster seeds...')
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=in_file_h5.root.Cluster.shape[0], term_width=80)
            progress_bar.start()
            total_cluster = 0  # to check analysis
            for cluster, index in analysis_utils.data_aligned_at_events(in_file_h5.root.Cluster, chunk_size=chunk_size):
                total_cluster += len(cluster)
                histogram.add_cluster_seed_hits(cluster, len(cluster))
                progress_bar.update(index)
            progress_bar.finish()

            filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)  # compression of the written data
            occupancy_array = histogram.get_occupancy().T
            occupancy_array_table = out_file_h5.create_carray(out_file_h5.root, name='HistOcc', title='Occupancy Histogram', atom=tb.Atom.from_dtype(occupancy_array.dtype), shape=occupancy_array.shape, filters=filter_table)
            occupancy_array_table[:] = occupancy_array

            if total_cluster != np.sum(occupancy_array):
                logging.warning('Analysis shows inconsistent number of cluster used. Check needed!')
            in_file_h5.root.meta_data.copy(out_file_h5.root)  # copy meta_data note to new file


def analyze_hits_per_scan_parameter(analyze_data, scan_parameters=None, chunk_size=50000):
    '''Takes the hit table and analyzes the hits per scan parameter

    Parameters
    ----------
    analyze_data : analysis.analyze_raw_data.AnalyzeRawData object with an opened hit file (AnalyzeRawData.out_file_h5) or a
    file name with the hit data given (AnalyzeRawData._analyzed_data_file)
    scan_parameters : list of strings:
        The names of the scan parameters to use
    chunk_size : int:
        The chunk size of one hit table read. The bigger the faster. Too big causes memory errors.
    Returns
    -------
    yields the analysis.analyze_raw_data.AnalyzeRawData for each scan parameter
    '''

    if analyze_data.out_file_h5 is None or analyze_data.out_file_h5.isopen == 0:
        in_hit_file_h5 = tb.open_file(analyze_data._analyzed_data_file, 'r+')
        close_file = True
    else:
        in_hit_file_h5 = analyze_data.out_file_h5
        close_file = False

    meta_data = in_hit_file_h5.root.meta_data[:]  # get the meta data table
    try:
        hit_table = in_hit_file_h5.root.Hits  # get the hit table
    except tb.NoSuchNodeError:
        logging.error('analyze_hits_per_scan_parameter needs a hit table, but no hit table found.')
        return

    meta_data_table_at_scan_parameter = analysis_utils.get_unique_scan_parameter_combinations(meta_data, scan_parameters=scan_parameters)
    parameter_values = analysis_utils.get_scan_parameters_table_from_meta_data(meta_data_table_at_scan_parameter, scan_parameters)
    event_number_ranges = analysis_utils.get_ranges_from_array(meta_data_table_at_scan_parameter['event_number'])  # get the event number ranges for the different scan parameter settings

    analysis_utils.index_event_number(hit_table)  # create a event_numer index to select the hits by their event number fast, no needed but important for speed up

    # variables for read speed up
    index = 0  # index where to start the read out of the hit table, 0 at the beginning, increased during looping
    best_chunk_size = chunk_size  # number of hits to copy to RAM during looping, the optimal chunk size is determined during looping

    # loop over the selected events
    for parameter_index, (start_event_number, stop_event_number) in enumerate(event_number_ranges):
        logging.info('Analyze hits for ' + str(scan_parameters) + ' = ' + str(parameter_values[parameter_index]))
        analyze_data.reset()  # resets the front end data of the last analysis step but not the options
        readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
        # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
        for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start_index=index, chunk_size=best_chunk_size):
            analyze_data.analyze_hits(hits, scan_parameter=False)  # analyze the selected hits in chunks
            readout_hit_len += hits.shape[0]
        best_chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < chunk_size and int(1.05 * readout_hit_len) > 1e3 else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
        file_name = " ".join(re.findall("[a-zA-Z0-9]+", str(scan_parameters))) + '_' + " ".join(re.findall("[a-zA-Z0-9]+", str(parameter_values[parameter_index])))
        analyze_data._create_additional_hit_data(safe_to_file=False)
        analyze_data._create_additional_cluster_data(safe_to_file=False)
        yield analyze_data, file_name

    if close_file:
        in_hit_file_h5.close()

if __name__ == "__main__":
    print 'run analysis as main'
