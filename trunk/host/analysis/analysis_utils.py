"""This class provides often needed analysis functions, for analysis that is done with python.
"""

import logging
import re
import sys
import os
import itertools
import time
import collections
import pandas as pd
import numpy as np
import glob
import tables as tb
import numexpr as ne
from plotting import plotting
from scipy.interpolate import interp1d
from operator import itemgetter
from scipy.sparse import coo_matrix
from scipy.interpolate import splrep, splev

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def get_data_statistics(interpreted_files):
    '''Quick and dirty function to give as redmine compatible iverview table
    '''
    print '| *File Name* | *File Size* | *Times Stamp* | *Events* | *Bad Events* | *Measurement time* | *# SR* | *Hits* |'# Mean Tot | Mean rel. BCID'
    for interpreted_file in interpreted_files:
        with tb.openFile(interpreted_file, mode="r") as in_file_h5:  # open the actual hit file
            event_errors = in_file_h5.root.HistErrorCounter[:]
            n_hits = np.sum(in_file_h5.root.HistOcc[:])
            measurement_time = int(in_file_h5.root.meta_data[-1]['timestamp_stop'] - in_file_h5.root.meta_data[0]['timestamp_start'])
#             mean_tot = np.average(in_file_h5.root.HistTot[:], weights=range(0,16) * np.sum(range(0,16)))# / in_file_h5.root.HistTot[:].shape[0]
#             mean_bcid = np.average(in_file_h5.root.HistRelBcid[:], weights=range(0,16))
            n_sr = np.sum(in_file_h5.root.HistServiceRecord[:])
            n_bad_events = int(np.sum(in_file_h5.root.HistErrorCounter[2:]))
            try:
                n_events = str(in_file_h5.root.Hits[-1]['event_number'] + 1)
            except tb.NoSuchNodeError:
                n_events = '~' + str(in_file_h5.root.meta_data[-1]['event_number'] + (in_file_h5.root.meta_data[-1]['event_number'] - in_file_h5.root.meta_data[-2]['event_number']))
            if int(n_events) < 7800000 or n_sr > 4200 or n_bad_events > 40:
                print '| %{color:red}', os.path.basename(interpreted_file) + '%', '|', int(os.path.getsize(interpreted_file) / (1024 * 1024.)), 'Mb |', time.ctime(os.path.getctime(interpreted_file)), '|',  n_events, '|', n_bad_events, '|', measurement_time, 's |', n_sr, '|', n_hits, '|'#, mean_tot, '|', mean_bcid, '|'
            else:
                print '|', os.path.basename(interpreted_file), '|', int(os.path.getsize(interpreted_file) / (1024 * 1024.)), 'Mb |', time.ctime(os.path.getctime(interpreted_file)), '|',  n_events, '|', n_bad_events, '|', measurement_time, 's |', n_sr, '|', n_hits, '|'#, mean_tot, '|', mean_bcid, '|'


def get_profile_histogram(x, y, n_bins=100):
    '''Takes 2D point data (x,y) and creates a profile histogram similar to the TProfile in ROOT. It calculates
    the y mean for every bin at the bin center and gives the y mean error as error bars.

    Parameters
    ----------
    x : array like
        data x positions
    y : array like
        data y positions
    n_bins : int
        the number of bins used to create the histogram
    '''
    if len(x) != len(y):
        raise ValueError('x and y dimensions have to be the same')
    n, bin_edges = np.histogram(x, bins=n_bins)  # needed to calculate the number of points per bin
    sy = np.histogram(x, bins=n_bins, weights=y)[0]  # the sum of the bin values
    sy2 = np.histogram(x, bins=n_bins, weights=y * y)[0]  # the quadratic sum of the bin values
    bin_centers = (bin_edges[1:] + bin_edges[:-1]) / 2  # calculate the bin center for all bins
    mean = sy / n  # calculate the mean of all bins
    std = np.sqrt((sy2 / n - mean * mean))  # TODO: not understood, need check if this is really the standard deviation
    std_mean = std / np.sqrt((n - 1))
    mean[np.isnan(mean)] = 0.
    std_mean[np.isnan(std_mean)] = 0.
    return bin_centers, mean, std_mean


def get_scan_parameter_from_nodes(parent_node, parameter):
    ''' Takes the hdf5 parent node and searches for child notes that have parameter in the name.'''


def get_normalization(hit_files, parameter, reference='event', sort=False, plot=False):
    ''' Takes different hit files (hit_files), extracts the number of events or the scan time (reference) per scan parameter (parameter)
    and returns an array with a normalization factor. This normalization factor has the length of the number of different parameters.
    One can also sort the normalization by the parameter values.

    Parameters
    ----------
    hit_files : list of strings
    parameter : string
    reference : string
    plot : bool

    Returns
    -------
    numpy.ndarray
    '''

    scan_parameter_values_files_dict = get_parameter_value_from_files(hit_files, parameter, sort=sort)
    normalization = []
    for one_file in scan_parameter_values_files_dict:
        with tb.openFile(one_file, mode="r") as in_hit_file_h5:  # open the actual hit file
            meta_data = in_hit_file_h5.root.meta_data[:]
            if reference == 'event':
                if len(get_meta_data_at_scan_parameter(meta_data, parameter)) < 2:  # if there is only one parameter used take the event number from the last hit
                    hits = in_hit_file_h5.root.Hits
                    n_events = [hits[-1]['event_number']]
                else:
                    try:
                        event_numbers = get_meta_data_at_scan_parameter(meta_data, parameter)['event_number']  # get the event numbers in meta_data where the scan parameter changes
                        event_range = get_event_range(event_numbers)
                        event_range[-1, 1] = event_range[-2, 1]  # hack the last event range not to be None
                        n_events = event_range[:, 1] - event_range[:, 0]  # number of events for every GDAC
                        n_events[-1] = n_events[-2] - (n_events[-3] - n_events[-2])  # FIXME: set the last number of events manually, bad extrapolaton
                    except ValueError:  # there is not necessarily a scan parameter given in the meta_data
                        n_events = [meta_data[-1]['event_number'] + (meta_data[-1]['event_number'] - meta_data[-2]['event_number'])]
                    except IndexError:  # there is maybe just one scan parameter given
                        n_events = [meta_data[-1]['event_number']]
                        logging.warning('Last number of events unknown and extrapolated')
                normalization.extend(n_events)
            elif reference == 'time':
                try:
                    time_start = get_meta_data_at_scan_parameter(meta_data, parameter)['timestamp_start']
                    time_spend = np.diff(time_start)
                    time_spend = np.append(time_spend, meta_data[-1]['timestamp_stop'] - time_start[-1])  # TODO: needs check, add last missing entry
                except ValueError:  # there is not necessarily a scan parameter given in the meta_data
                    time_spend = [meta_data[-1]['timestamp_stop'] - meta_data[0]['timestamp_start']]
                normalization.extend(time_spend)
            else:
                raise NotImplementedError('The normalization reference ' + reference + ' is not implemented')
    if plot:
        x = list(itertools.chain.from_iterable(scan_parameter_values_files_dict.values()))
        if reference == 'event':
            plotting.plot_scatter(x, normalization, title='Events per ' + parameter + ' setting', x_label=parameter, y_label='# events', log_x=True)
        elif reference == 'time':
            plotting.plot_scatter(x, normalization, title='Measuring time per GDAC setting', x_label=parameter, y_label='time [s]', log_x=True)
    return np.amax(np.array(normalization)).astype('f16') / np.array(normalization)


def get_occupancy_per_parameter(hit_analyzed_files, parameter='GDAC'):
    '''Takes the hit files mentioned in hit_analyzed_files, opens the occupancy hist of each file and combines theses occupancy hist to one occupancy hist, where
    the third dimension is the number of scan parameters (col * row * n_parameter).
    Every scan parameter value is checked to have only one corresponding occupancy histogram. The files can have a scan parameter, which is then extracted from the
    meta data. If there is no scan parameter given the scan parameter is extracted from the file name.

    Parameters
    ----------
    hit_analyzed_files : list of strings:
        Absolute paths of the analyzed hit files containing the occupancy histograms.
        data x positions
    parameter : string:
        The name of the scan parameter varied for the different occupancy histograms
    '''
    logging.info('Get and combine the occupancy hists from ' + str(len(hit_analyzed_files)) + ' files')
    occupancy_combined = None
    all_scan_parameters = []  # list with all scan parameters of all files, used to check for parameter values that occurs more than once
    for index in range(0, len(hit_analyzed_files)):  # loop over all hit files
        with tb.openFile(hit_analyzed_files[index], mode="r") as in_hit_analyzed_file_h5:  # open the actual hit file
            scan_parameter = get_scan_parameter(in_hit_analyzed_file_h5.root.meta_data[:])  # get the scan parameters
            if scan_parameter:  # scan parameter is not none, therefore the occupancy hist has more dimensions col*row*n_scan_parameter
                scan_parameter_values = scan_parameter[parameter].tolist()  # get the scan parameters
                if set(scan_parameter_values).intersection(all_scan_parameters):  # check that the scan parameters are unique
                    logging.error('The following settings for ' + parameter + ' appear more than once: ' + str(set(scan_parameter_values).intersection(all_scan_parameters)))
                    raise NotImplementedError('Every scan parameter has to have only one occupancy histogram')
                all_scan_parameters.extend(scan_parameter_values)
            else:  # scan parameter not in meta data, therefore it has to be in the file name
                parameter_value = get_parameter_value_from_file_names([hit_analyzed_files[index]], parameter).values()[0]  # get the parameter value from the file name
                if parameter_value in all_scan_parameters:  # check that the scan parameters are unique
                    logging.error('The setting ' + str(parameter_value) + ' for ' + parameter + ' appears more than once')
                    raise NotImplementedError('Every scan parameter has to have only one occupancy histogram')
                all_scan_parameters.append(long(parameter_value))
            if occupancy_combined is None:
                occupancy_combined = in_hit_analyzed_file_h5.root.HistOcc[:]
            else:
                occupancy_combined = np.append(occupancy_combined, in_hit_analyzed_file_h5.root.HistOcc[:], axis=2)
    return occupancy_combined, all_scan_parameters


def central_difference(x, y):
    '''Returns the dy/dx(x) via central difference method

    Parameters
    ----------
    x : array like
    y : array like

    Returns
    -------
    dy/dx : array like
    '''
    if (len(x) != len(y)):
        raise ValueError("x, y must have the same length")
    z1 = np.hstack((y[0], y[:-1]))
    z2 = np.hstack((y[1:], y[-1]))
    dx1 = np.hstack((0, np.diff(x)))
    dx2 = np.hstack((np.diff(x), 0))
    return (z2 - z1) / (dx2 + dx1)


def get_parameter_value_from_file_names(files, parameter, unique=True, sort=True):
    """
    Takes a list of files, searches for the parameter name in the file name and returns a ordered dict with the file name
    in the first dimension and the corresponding parameter value in the second.
    The file names can be sorted by the parameter value, otherwise the order is kept. If unique is true every parameter is unique and
    mapped to the file name that occurred last in the files list.

    Parameters
    ----------
    files : list of strings
    parameter : string
    unique : bool
    sort : bool

    Returns
    -------
    collections.OrderedDict

    """
#     unique=False
    logging.info('Get the ' + parameter + ' values from the file names of ' + str(len(files)) + ' files')
    files_dict = collections.OrderedDict()
    for one_file in files:
        parameter_value = re.findall(parameter + r'_(\d+)', one_file)
        if parameter_value:
            parameter_value = int(parameter_value[0])
            if unique and parameter_value in files_dict.values():  # check if the value is already there
                for i_file_name, i_parameter_value in files_dict.iteritems():
                    if i_parameter_value == parameter_value:
                        del files_dict[i_file_name]
                        logging.info('File with ' + parameter + ' = ' + str(parameter_value) + ' is not unique. Take ' + one_file)
            files_dict[one_file] = parameter_value
    return collections.OrderedDict(sorted(files_dict.iteritems(), key=itemgetter(1)) if sort else files_dict)  # with PEP 265 solution of sorting a dict by value


def get_data_file_names_from_scan_base(scan_base, filter_file_words=['interpreted', 'cut_', 'cluster_sizes']):
    """
    Takes a list of scan base names and returns all file names that have this scan base within their name. File names that have a word of filter_file_words
    in their name are excluded.

    Parameters
    ----------
    scan_base : list of strings
    filter_file_words : list of strings

    Returns
    -------
    list of strings

    """
    raw_data_files = []
    for scan_name in scan_base:
        data_files = glob.glob(scan_name + '_*.h5')
        if not data_files:
            raise RuntimeError('Cannot find any files for ' + scan_name)
        raw_data_files.extend(filter(lambda data_file: not any(x in data_file for x in filter_file_words), data_files))  # filter out already analyzed data
    return raw_data_files


def get_parameter_value_from_files(files, parameter, sort=True):
    '''
    Takes a list of files, searches for the parameter name in the file name and in the file and returns a ordered dict with the parameter values
    in the first dimension and the corresponding file name in the second.
    If a scan parameter appears in the file name and in the file the first parameter setting has to be in the file name, otherwise a warning is shown.
    The file names can be sorted by the first parameter value of each file.

    Parameters
    ----------
    files : list of strings
    parameter : string
    sort : bool

    Returns
    -------
    collections.OrderedDict

    '''
    logging.info('Get the ' + parameter + ' values from ' + str(len(files)) + ' files')
    files_dict = collections.OrderedDict()
    parameter_values_from_file_names_dict = get_parameter_value_from_file_names(files, parameter, sort=sort)
    for file_name, parameter_value_from_file_name in parameter_values_from_file_names_dict.iteritems():
        with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual hit file
            try:
                scan_parameters = get_scan_parameter(in_file_h5.root.meta_data[:])  # get the scan parameters from the meta data
                if scan_parameters:
                    scan_parameter_values = scan_parameters[parameter].tolist()  # scan parameter settings used
                else:
                    scan_parameter_values = None
            except tb.NoSuchNodeError:  # no meta data array and therefore no scan parameter used
                scan_parameter_values = None
            if scan_parameter_values is None:
                scan_parameter_values = [parameter_value_from_file_name]
            elif parameter_value_from_file_name != scan_parameter_values[0]:
                logging.warning(parameter + ' = ' + str(parameter_value_from_file_name) + ' info in file name differs from the ' + parameter + ' info = ' + str(scan_parameter_values) + ' in the meta data')
            files_dict[file_name] = scan_parameter_values
    return collections.OrderedDict(files_dict)


def in1d_sorted(ar1, ar2):
    """
    Does the same than np.in1d but uses the fact that ar1 and ar2 are sorted. Is therefore much faster.

    """
    if ar1.shape[0] == 0 or ar2.shape[0] == 0:  # check for empty arrays to avoid crash
        return []
    inds = ar2.searchsorted(ar1)
    inds[inds == len(ar2)] = 0
    return ar2[inds] == ar1


def smooth_differentiation(x, y, weigths=None, order=5, smoothness=3, derivation=1):
    '''Returns the dy/dx(x) with the fit and differentiation of a spline curve

    Parameters
    ----------
    x : array like
    y : array like

    Returns
    -------
    dy/dx : array like
    '''
    if (len(x) != len(y)):
        raise ValueError("x, y must have the same length")
    f = splrep(x, y, w=weigths, k=order, s=smoothness)  # spline function
    return splev(x, f, der=derivation)


def reduce_sorted_to_intersect(ar1, ar2):
    """
    Takes two sorted arrays and return the intersection ar1 in ar2, ar2 in ar1.

    Parameters
    ----------
    ar1 : (M,) array_like
        Input array.
    ar2 : array_like
         Input array.

    Returns
    -------
    ar1, ar1 : ndarray, ndarray
        The intersection values.

    """
    # Ravel both arrays, behavior for the first array could be different
    ar1 = np.asarray(ar1).ravel()
    ar2 = np.asarray(ar2).ravel()

    # get min max values of the arrays
    ar1_biggest_value = ar1[-1]
    ar1_smallest_value = ar1[0]
    ar2_biggest_value = ar2[-1]
    ar2_smallest_value = ar2[0]

    if ar1_biggest_value < ar2_smallest_value or ar1_smallest_value > ar2_biggest_value:  # special case, no intersection at all
        return ar1[0:0], ar2[0:0]

    # get min/max indices with values that are also in the other array
    min_index_ar1 = np.argmin(ar1 < ar2_smallest_value)
    max_index_ar1 = np.argmax(ar1 > ar2_biggest_value)
    min_index_ar2 = np.argmin(ar2 < ar1_smallest_value)
    max_index_ar2 = np.argmax(ar2 > ar1_biggest_value)

    if min_index_ar1 < 0:
        min_index_ar1 = 0
    if min_index_ar2 < 0:
        min_index_ar2 = 0
    if max_index_ar1 == 0 or max_index_ar1 > ar1.shape[0]:
        max_index_ar1 = ar1.shape[0]
    if max_index_ar2 == 0 or max_index_ar2 > ar2.shape[0]:
        max_index_ar2 = ar2.shape[0]

    # reduce the data
    return ar1[min_index_ar1:max_index_ar1], ar2[min_index_ar2:max_index_ar2]


def get_not_unique_values(array):
    '''Returns the values that appear at least twice in array.

    Parameters
    ----------
    array : array like

    Returns
    -------
    numpy.array
    '''
    s = np.sort(array, axis=None)
    s = s[s[1:] == s[:-1]]
    return np.unique(s)


def get_meta_data_index_at_scan_parameter(meta_data_array, scan_parameter_name):
    '''Takes the analyzed meta_data table and returns the indices where the scan parameter changes

    Parameters
    ----------
    meta_data_array : numpy.recordarray
    scan_parameter_name : string

    Returns
    -------
    numpy.ndarray:
        first dimension: scan parameter value
        second dimension: index where scan parameter value was used first
    '''
    scan_parameter_values = meta_data_array[scan_parameter_name]
    diff = np.concatenate(([1], np.diff(scan_parameter_values)))
    idx = np.concatenate((np.where(diff)[0], [len(scan_parameter_values)]))
    index = np.empty(len(idx) - 1, dtype={'names': [scan_parameter_name, 'index'], 'formats': ['u4', 'u4']})
    index[scan_parameter_name] = scan_parameter_values[idx[:-1]]
    index['index'] = idx[:-1]
    return index


def get_meta_data_at_scan_parameter(meta_data_array, scan_parameter_name):
    '''Takes the analyzed meta_data table and returns the entries where the scan parameter changes

    Parameters
    ----------
    meta_data_array : numpy.recordarray
    scan_parameter_name : string

    Returns
    -------
    numpy.ndarray:
        reduced meta_data_array
    '''
    return meta_data_array[get_meta_data_index_at_scan_parameter(meta_data_array, scan_parameter_name)['index']]


def correlate_events(data_frame_fe_1, data_frame_fe_2):
    '''Correlates events from different Fe by the event number

    Parameters
    ----------
    data_frame_fe_1 : pandas.dataframe
    data_frame_fe_2 : pandas.dataframe

    Returns
    -------
    Merged pandas dataframe.
    '''
    logging.info("Correlating events")
    return data_frame_fe_1.merge(data_frame_fe_2, how='left', on='event_number')  # join in the events that the triggered fe sees, only these are interessting


def remove_duplicate_hits(data_frame):
    '''Removes duplicate hits, possible due to FE error or ToT = 14 hits.

    Parameters
    ----------
    data_frame : pandas.dataframe

    Returns
    -------
    pandas dataframe.
    '''
    # remove duplicate hits from ToT = 14 hits or FE data error and count how many have been removed
    df_length = len(data_frame.index)
    data_frame = data_frame.drop_duplicates(cols=['event_number', 'col', 'row'])
    logging.info("Removed %d duplicates in trigger FE data" % (df_length - len(data_frame.index)))
    return data_frame


def get_hits_with_n_cluster_per_event(hits_table, cluster_table, condition='n_cluster==1'):
    '''Selects the hits with a certain number of cluster.

    Parameters
    ----------
    hits_table : pytables.table
    cluster_table : pytables.table

    Returns
    -------
    pandas.DataFrame
    '''

    logging.info("Calculate hits with clusters where " + condition)
    data_frame_hits = pd.DataFrame({'event_number': hits_table.cols.event_number, 'column': hits_table.cols.column, 'row': hits_table.cols.row})
    data_frame_hits = data_frame_hits.set_index(keys='event_number')
    events_with_n_cluster = get_events_with_n_cluster(cluster_table, condition)
    data_frame_hits = data_frame_hits.reset_index()
    return data_frame_hits.loc[events_with_n_cluster]


def get_hits_in_events(hits_array, events, assume_sorted=True):
    '''Selects the hits that occurred in events. If a event range can be defined use the get_hits_in_event_range function. It is much faster.

    Parameters
    ----------
    hits_array : numpy.array
    events : array
    assume_sorted : bool
        Is true if the events to select are sorted from low to high value. Increases speed by 35%.

    Returns
    -------
    numpy.array
        hit array with the hits in events.
    '''

    logging.info("Calculate hits that exists in the given %d events." % len(events))
    if assume_sorted:
        events, _ = reduce_sorted_to_intersect(events, hits_array['event_number'])  # reduce the event number range to the max min event number of the given hits to save time
        if events.shape[0] == 0:  # if there is not a single selected hit
            return hits_array[0:0]
    try:
        if assume_sorted:
            hits_in_events = hits_array[in1d_sorted(hits_array['event_number'], events)]
        else:
            hits_in_events = hits_array[np.in1d(hits_array['event_number'], events)]
    except MemoryError:
        logging.error('There are too many hits to do in RAM operations. Use the write_hits_in_events function instead.')
        raise MemoryError
    return hits_in_events


def get_hits_in_event_range(hits_array, event_start, event_stop, assume_sorted=True):
    '''Selects the hits that occurred in the given event range [event_start, event_stop[

    Parameters
    ----------
    hits_array : numpy.array
    event_start : int
    event_stop : int
    assume_sorted : bool
        Set to true if the hits are sorted by the event_number. Increases speed.

    Returns
    -------
    numpy.array
        hit array with the hits in the event range.
    '''
    logging.info("Calculate hits that exists in the given event range [" + str(event_start) + ", " + str(event_stop) + "[")
    event_number = hits_array['event_number']
    if assume_sorted:
        hits_event_start = hits_array['event_number'][0]
        hits_event_stop = hits_array['event_number'][-1]
        if (event_start != None and event_stop != None) and (hits_event_stop < event_start or hits_event_start > event_stop or event_start == event_stop):  # special case, no intersection at all
            return hits_array[0:0]

        # get min/max indices with values that are also in the other array
        if event_start == None:
            min_index_hits = 0
        else:
            min_index_hits = np.argmin(hits_array['event_number'] < event_start)

        if event_stop == None:
            max_index_hits = hits_array['event_number'].shape[0]
        else:
            max_index_hits = np.argmax(hits_array['event_number'] >= event_stop)

        if min_index_hits < 0:
            min_index_hits = 0
        if max_index_hits == 0 or max_index_hits > hits_array['event_number'].shape[0]:
            max_index_hits = hits_array['event_number'].shape[0]
        return hits_array[min_index_hits:max_index_hits]
    else:
        return hits_array[np.logical_and(event_number >= event_start, event_number < event_stop)]


def write_hits_in_events(hit_table_in, hit_table_out, events, start_hit_word=0, chunk_size=5000000):
    '''Selects the hits that occurred in events and writes them to a pytable. This function reduces the in RAM operations and has to be used if the get_hits_in_events function raises a memory error.

    Parameters
    ----------
    hit_table_in : pytable.table
    hit_table_out : pytable.table
        functions need to be able to write to hit_table_out
    events : array like
        defines the events to be written from hit_table_in to hit_table_out. They do not have to exists at all.
    chunk_size : int
        defines how many hits are analyzed in RAM. Bigger numbers increase the speed, too big numbers let the program crash with a memory error.
    start_hit_word: int
        Index of the first hit word to be analyzed. Used for speed up.

    Returns
    -------
    start_hit_word: int
        Index of the last hit word analyzed. Used to speed up the next call of write_hits_in_events.
    '''
    if len(events) > 0:  # needed to avoid crash
        min_event = np.amin(events)
        max_event = np.amax(events)
        logging.info("Write hits from hit number >= %d that exists in the selected %d events with %d <= event number <= %d into a new hit table." % (start_hit_word, len(events), min_event, max_event))
        table_size = hit_table_in.shape[0]
        iHit = 0
        for iHit in range(start_hit_word, table_size, chunk_size):
            hits = hit_table_in.read(iHit, iHit + chunk_size)
            last_event_number = hits[-1]['event_number']
            hit_table_out.append(get_hits_in_events(hits, events=events))
            if last_event_number > max_event:  # speed up, use the fact that the hits are sorted by event_number
                return iHit
    return start_hit_word


def write_hits_in_event_range(hit_table_in, hit_table_out, event_start, event_stop, start_hit_word=0, chunk_size=5000000):
    '''Selects the hits that occurred in given event range [event_start, event_stop[ and write them to a pytable. This function reduces the in RAM operations and has to be used if the get_hits_in_event_range
        function raises a memory error.

    Parameters
    ----------
    hit_table_in : pytable.table
    hit_table_out : pytable.table
        functions need to be able to write to hit_table_out
    event_start, event_stop : int
        start/stop event numbers
    chunk_size : int
        defines how many hits are analysed in RAM. Bigger numbers increase the speed, too big numbers let the program crash with a memory error.
    Returns
    -------
    start_hit_word: int
        Index of the last hit word analyzed. Used to speed up the next call of write_hits_in_events.
    '''

    logging.info("Write hits that exists in the given event range from %d to %d into a new hit table." % (event_start, event_stop))
    table_size = hit_table_in.shape[0]
    for iHit in range(0, table_size, chunk_size):
        hits = hit_table_in.read(iHit, iHit + chunk_size)
        last_event_number = hits[-1]['event_number']
        hit_table_out.append(get_hits_in_event_range(hits, event_start=event_start, event_stop=event_stop))
        if last_event_number > event_stop:  # speed up, use the fact that the hits are sorted by event_number
            return iHit + chunk_size
    return start_hit_word


def get_mean_from_histogram(counts, bin_positions):
    values = []
    for index, one_bin in enumerate(counts):
        for _ in range(one_bin):
            values.extend([bin_positions[index]])
    return np.mean(values)


def get_median_from_histogram(counts, bin_positions):
    values = []
    for index, one_bin in enumerate(counts):
        for _ in range(one_bin):
            values.extend([bin_positions[index]])
    return np.median(values)


def get_rms_from_histogram(counts, bin_positions):
    values = []
    for index, one_bin in enumerate(counts):
        for _ in range(one_bin):
            values.extend([bin_positions[index]])
    return np.std(values)


def get_events_with_n_cluster(event_number, condition='n_cluster==1'):
    '''Selects the events with a certain number of cluster.

    Parameters
    ----------
    event_number : numpy.array

    Returns
    -------
    numpy.array
    '''

    logging.info("Calculate events with clusters where " + condition)
    n_cluster_in_events = get_n_cluster_in_events(event_number)
    n_cluster = n_cluster_in_events[:, 1]
    return n_cluster_in_events[ne.evaluate(condition), 0]


def get_events_with_cluster_size(event_number, cluster_size, condition='cluster_size==1'):
    '''Selects the events with cluster of a given cluster size.

    Parameters
    ----------
    event_number : numpy.array
    cluster_size : numpy.array
    condition : string

    Returns
    -------
    numpy.array
    '''

    logging.info("Calculate events with clusters with " + condition)
    return np.unique(event_number[ne.evaluate(condition)])


def get_n_cluster_in_events(event_numbers):
    '''Calculates the number of cluster in every given event.

    Parameters
    ----------
    event_numbers : numpy.array

    Returns
    -------
    numpy.Array
        First dimension is the event number
        Second dimension is the number of cluster of the event
    '''
    logging.info("Calculate the number of cluster in every given event")
    if (sys.maxint < 3000000000):  # on 32- bit operation systems max int is 2147483647 leading to numpy bugs that need workarounds
        event_number_array = event_numbers.astype('<i4')  # BUG in numpy, unint works with 64-bit, 32 bit needs reinterpretation
        offset = np.amin(event_number_array)
        event_number_array = np.subtract(event_number_array, offset)  # BUG #225 for values > int32
        cluster_in_event = np.bincount(event_number_array)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
        selected_event_number_index = np.nonzero(cluster_in_event)[0]
        selected_event_number = np.add(selected_event_number_index, offset)
        return np.vstack((selected_event_number, cluster_in_event[selected_event_number_index])).T
    else:
        cluster_in_event = np.bincount(event_numbers)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
        selected_event_number = np.nonzero(cluster_in_event)[0]
        return np.vstack((selected_event_number, cluster_in_event[selected_event_number])).T


def get_n_cluster_per_event_hist(cluster_table):
    '''Calculates the number of cluster in every event.

    Parameters
    ----------
    cluster_table : pytables.table

    Returns
    -------
    numpy.Histogram
    '''
    logging.info("Histogram number of cluster per event")
    cluster_in_events = get_n_cluster_in_events(cluster_table)[:, 1]  # get the number of cluster for every event
    return np.histogram(cluster_in_events, bins=range(0, np.max(cluster_in_events) + 2))  # histogram the occurrence of n cluster per event


def histogram_correlation(data_frame_combined):
    '''Takes a dataframe with combined hit data from two Fe and correlates for each event each hit from one Fe to each hit of the other Fe.

    Parameters
    ----------
    data_frame_combined : pandas.DataFrame

    Returns
    -------
    [numpy.Histogram, numpy.Histogram]
    '''
    logging.info("Histograming correlations")
    corr_row = np.histogram2d(data_frame_combined['row_fe0'], data_frame_combined['row_fe1'], bins=(336, 336), range=[[1, 336], [1, 336]])
    corr_col = np.histogram2d(data_frame_combined['column_fe0'], data_frame_combined['column_fe1'], bins=(80, 80), range=[[1, 80], [1, 80]])
    return corr_col, corr_row


def histogram_tot(array, label='tot'):
    '''Takes the numpy hit/cluster array and histograms the ToT values.

    Parameters
    ----------
    hit_array : numpy.ndarray
    label: string

    Returns
    -------
    numpy.Histogram
    '''
    logging.info("Histograming ToT values")
    return np.histogram(a=array[label], bins=16, range=(0, 16))


def histogram_tot_per_pixel(array, labels=['column', 'row', 'tot']):
    '''Takes the numpy hit/cluster array and histograms the ToT values for each pixel

    Parameters
    ----------
    hit_array : numpy.ndarray
    label: string list

    Returns
    -------
    numpy.Histogram
    '''
    logging.info("Histograming ToT values for each pixel")
    return np.histogramdd(sample=(array[labels[0]], array[labels[1]], array[labels[2]]), bins=(80, 336, 16), range=[[0, 80], [0, 336], [0, 16]])


def histogram_mean_tot_per_pixel(array, labels=['column', 'row', 'tot']):
    '''Takes the numpy hit/cluster array and histograms the mean ToT values for each pixel

    Parameters
    ----------
    hit_array : numpy.ndarray
    label: string list

    Returns
    -------
    numpy.Histogram
    '''
    tot_array = histogram_tot_per_pixel(array=array, labels=labels)[0]
    occupancy = histogram_occupancy_per_pixel(array=array)[0]  # needed for normalization
    tot_avr = np.average(tot_array, axis=2, weights=range(0, 16)) * sum(range(0, 16))
    tot_avr = np.divide(tot_avr, occupancy)
    return np.ma.array(tot_avr, mask=(occupancy == 0))  # return array with masked pixel without any hit


def histogram_occupancy_per_pixel(array, labels=['column', 'row'], mask_no_hit=False, fast=False):
    if fast:
        occupancy = fast_histogram2d(x=array[labels[0]], y=array[labels[1]], bins=(80, 336))
    else:
        occupancy = np.histogram2d(x=array[labels[0]], y=array[labels[1]], bins=(80, 336), range=[[0, 80], [0, 336]])
    if mask_no_hit:
        return np.ma.array(occupancy[0], mask=(occupancy[0] == 0)), occupancy[1], occupancy[2]
    else:
        return occupancy


def fast_histogram2d(x, y, bins):
    logging.warning('fast_histogram2d gives not exact results')
    nx = bins[0] - 1
    ny = bins[1] - 1

    print nx, ny

    xmin, xmax = x.min(), x.max()
    ymin, ymax = y.min(), y.max()
    dx = (xmax - xmin) / (nx - 1.0)
    dy = (ymax - ymin) / (ny - 1.0)

    weights = np.ones(x.size)

    # Basically, this is just doing what np.digitize does with one less copy
    xyi = np.vstack((x, y)).T
    xyi -= [xmin, ymin]
    xyi /= [dx, dy]
    xyi = np.floor(xyi, xyi).T

    # Now, we'll exploit a sparse coo_matrix to build the 2D histogram...
    grid = coo_matrix((weights, xyi), shape=(nx, ny)).toarray()

    return grid, np.linspace(xmin, xmax, nx), np.linspace(ymin, ymax, ny)


def get_scan_parameter(meta_data_array):
    '''Takes the numpy meta data array and returns the different scan parameter settings and the name aligned in a dictionary

    Parameters
    ----------
    meta_data_array : numpy.ndarray

    Returns
    -------
    python.dict{string, numpy.Histogram}
    '''

    if len(meta_data_array.dtype.names) < 5:  # no meta_data found
        return
    scan_parameters = {}
    for scan_par_name in meta_data_array.dtype.names[4:]:  # scan parameters are in columns 5 (= index 4) and above
        scan_parameters[scan_par_name] = np.unique(meta_data_array[scan_par_name])
    return scan_parameters


def get_scan_parameters_index(scan_parameter_array):
    '''Takes the scan parameter array and creates a scan parameter index labeling unique scan parameter combinations.
    Parameters
    ----------
    meta_data_array : numpy.ndarray

    Returns
    -------
    numpy.Histogram
    '''
#     scan_parameter_names = list(meta_data_array.dtype.names)[5:]
#     print scan_parameter_names
    return np.unique(scan_parameter_array, return_inverse=True)[1]


def get_unique_scan_parameter_combinations(meta_data_array, selected_columns_only=False):
    '''Takes the numpy meta data array and returns the rows with unique combinations of different scan parameter values for all scan parameters.
        If selected columns only is true, the returned histogram only contains the selected columns.

    Parameters
    ----------
    meta_data_array : numpy.ndarray

    Returns
    -------
    numpy.Histogram
    '''

    if len(meta_data_array.dtype.names) < 5:  # no meta_data found
        return
    return unique_row(meta_data_array, use_columns=range(4, len(meta_data_array.dtype.names)), selected_columns_only=selected_columns_only)


def unique_row(array, use_columns=None, selected_columns_only=False):
    '''Takes a numpy array and returns the array reduced to unique rows. If columns are defined only these columns are taken to define a unique row.
    Parameters
    ----------
    array : numpy.ndarray
    use_columns : list
        Index of columns to be used to define a unique row

    Returns
    -------
    numpy.ndarray
    '''
    if array.dtype.names is None:  # normal array has no named dtype
        if use_columns is not None:
            a_cut = array[:, use_columns]
        else:
            a_cut = array
        b = np.ascontiguousarray(a_cut).view(np.dtype((np.void, a_cut.dtype.itemsize * a_cut.shape[1])))
        _, index = np.unique(b, return_index=True)
        if not selected_columns_only:
            return array[np.sort(index)]  # sort to preserve order
        else:
            return a_cut[np.sort(index)]  # sort to preserve order
    else:  # names for dtype founnd --> array is recarray
        names = list(array.dtype.names)
        if use_columns is not None:
            new_names = [names[i] for i in use_columns]
        else:
            new_names = names
        a_cut, index = np.unique(array[new_names], return_index=True)
        if not selected_columns_only:
            return array[np.sort(index)]  # sort to preserve order
        else:
            return array[np.sort(index)][new_names]  # sort to preserve order

def get_event_range(events):
    '''Takes the events and calculates event ranges [start event, stop event[. The last range end with none since the last event is unknown.

    Parameters
    ----------
    events : array like

    Returns
    -------
    numpy.array
    '''
    left = events[:len(events)]
    right = events[1:len(events)]
    right = np.append(right, None)
    return np.column_stack((left, right))


def index_event_number(table_with_event_numer):
    if not table_with_event_numer.cols.event_number.is_indexed:  # index event_number column to speed up everything
        logging.info('Create event_number index, this takes some time')
        table_with_event_numer.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
    else:
        logging.info('Event_number index exists already, omit creation')


def data_aligned_at_events(table, start_event_number=None, stop_event_number=None, start=None, stop=None, chunk_size=10000000):
    '''Takes the table with a event_number column and returns chunks with the size up to chunk_size. The chunks are chosen in a way that the events are not splitted. Additional
    parameters can be set to increase the readout speed. If only events between a certain event range are used one can specify this. Also the start and the
    stop indices for the reading of the table can be specified for speed up.
    It is important to index the event_number with pytables before using this function, otherwise the queries are very slow.

    Parameters
    ----------
    table : pytables.table
    start_event_number : int
        The data read is corrected that only data starting from the start_event number is returned. Lower event numbers are discarded.
    stop_event_number : int
        The data read is corrected that only data up to the stop_event number is returned. The stop_event number is not included.
    Returns
    -------
    iterable to numpy.histogram
        The data of the actual chunk.
    last_index: int
        The index of the last table part already used. Can be used if data_aligned_at_events is called in a loop for speed up.
        Example:
        start_index = 0
        for scan_parameter in scan_parameter_range:
            start_event_number, stop_event_number = event_select_function(scan_parameter)
            for data, start_index in data_aligned_at_events(table, start_event_number=start_event_number, stop_event_number=stop_event_number, start=start_index):
                do_something(data)
    Example
    -------
    for data, index in data_aligned_at_events(table):
        do_something(data)
    '''

    # initialize variables
    start_index_known = False
    stop_index_known = False
    last_event_start_index = 0
    start_index = 0 if start == None else start
    stop_index = table.nrows if stop == None else stop

    # set start stop indices from the event numbers for fast read if possible; not possible if the given event number does not exist
    if start_event_number != None:
        condition_1 = 'event_number==' + str(start_event_number)
        start_indeces = table.get_where_list(condition_1)
        if len(start_indeces) != 0:  # set start index if possible
            start_index = start_indeces[0]
            start_index_known = True
#     else:
#         start_event_number = 0

    if stop_event_number != None:
        condition_2 = 'event_number==' + str(stop_event_number)
        stop_indeces = table.get_where_list(condition_2)
        if len(stop_indeces) != 0:  # set the stop index if possible, stop index is excluded
            stop_index = stop_indeces[0]
            stop_index_known = True

    if (start_index_known and stop_index_known) or (start_index + chunk_size >= stop_index):  # special case, one read is enough, data not bigger than one chunk and the indices are known
            yield table.read(start=start_index, stop=stop_index), stop_index
    else:  # read data in chunks, chunks do not divide events, abort if stop_event_number is reached
        while(start_index < stop_index):
            src_array = table.read(start=start_index, stop=start_index + chunk_size + 1)  # stop index is exclusive, so add 1
            first_event = src_array["event_number"][0]
            last_event = src_array["event_number"][-1]
            last_event_start_index = np.argmax(src_array["event_number"] == last_event)  # get first index of last event
            if last_event_start_index == 0:
                nrows = src_array.shape[0]
                if nrows != 1:
                    logging.warning("Depreciated warning?! Buffer too small to fit event. Possible loss of data. Increase chunk size.")
            else:
                nrows = last_event_start_index

            if (start_event_number != None or stop_event_number != None) and (last_event > stop_event_number or first_event < start_event_number):  # too many events read, get only the selected ones if specified
                selected_hits = get_hits_in_event_range(src_array[0:nrows], event_start=start_event_number, event_stop=stop_event_number, assume_sorted=True)
                if len(selected_hits) != 0:  # only return non empty data
                    yield selected_hits, start_index + len(selected_hits)
            else:
                yield src_array[0:nrows], start_index + nrows  # no events specified or selected event range is larger than read chunk, thus return the whole chunk minus the little part for event alignment
            if stop_event_number != None and last_event > stop_event_number:  # events are sorted, thus stop here to save time
                break
            start_index = start_index + nrows  # events fully read, increase start index and continue reading


def select_good_pixel_region(hits, col_span, row_span, min_cut_threshold=0.2, max_cut_threshold=2.0):
    '''Takes the hit array and masks all pixels with a certain occupancy.

    Parameters
    ----------
    hits : array like
        If dim > 2 the additional dimensions are summed up.
    min_cut_threshold : float, [0, 1]
        A number to specify the minimum threshold, which pixel to take. Pixels are masked if
        occupancy < min_cut_threshold * np.ma.median(occupancy)
        0 means that no pixels are masked
    max_cut_threshold : float, [0, 1]
        A number to specify the maximum threshold, which pixel to take. Pixels are masked if
        occupancy > max_cut_threshold * np.ma.median(occupancy)
        0 means that no pixels are masked

    Returns
    -------
    numpy.ma.array, shape=(80,336)
        The hits array with masked pixels.
    '''
    hits = np.sum(hits, axis=(-1)).astype('u8')
    mask = np.ones(shape=(80, 336), dtype=np.uint8)

    mask[min(col_span):max(col_span) + 1, min(row_span):max(row_span) + 1] = 0

    ma = np.ma.masked_where(mask, hits)
    return np.ma.masked_where(np.logical_or(ma < min_cut_threshold * np.ma.median(ma), ma > max_cut_threshold * np.ma.median(ma)), ma)


def get_hit_rate_correction(gdacs, calibration_gdacs, cluster_size_histogram):
    '''Calculates a correction factor for single hit clusters at the given GDACs from the cluster_size_histogram via cubic interpolation.

    Parameters
    ----------
    gdacs : array like
        The GDAC settings where the threshold should be determined from the calibration
    calibration_gdacs : array like
        GDAC settings used during the source scan for the cluster size calibration.
    cluster_size_histogram : numpy.array, shape=(80,336,# of GDACs during calibration)
        The calibration array

    Returns
    -------
    numpy.array, shape=(80,336,# of GDACs during calibration)
        The threshold values for each pixel at gdacs.
    '''
    logging.info('Calculate the correction factor for the single hit cluster rate at %d given GDAC settings' % len(gdacs))
    if len(calibration_gdacs) != cluster_size_histogram.shape[0]:
        raise ValueError('Length of the provided pixel GDACs does not match the dimension of the cluster size array')
    hist_sum = np.sum(cluster_size_histogram, axis=1)
    hist_rel = cluster_size_histogram / hist_sum[:, np.newaxis].astype('f4') * 100.
    maximum_rate = np.amax(hist_rel[:, 1])
    correction_factor = maximum_rate / hist_rel[:, 1]
    # sort arrays since interpolate does not work otherwise
    calibration_gdacs_sorted = np.array(calibration_gdacs)
    correction_factor_sorted = correction_factor[np.argsort(calibration_gdacs_sorted)]
    calibration_gdacs_sorted = np.sort(calibration_gdacs_sorted)
    interpolation = interp1d(calibration_gdacs_sorted.tolist(), correction_factor_sorted.tolist(), kind='cubic', bounds_error=True)
    return interpolation(gdacs)


def get_mean_threshold_from_calibration(gdac, mean_threshold_calibration):
    '''Calculates the mean threshold from the threshold calibration at the given gdac settings. If the given gdac value was not used during caluibration
    the value is determined by interpolation.

    Parameters
    ----------
    gdacs : array like
        The GDAC settings where the threshold should be determined from the calibration
    mean_threshold_calibration : pytable
        The table created during the calibration scan.

    Returns
    -------
    numpy.array, shape=(len(gdac), )
        The mean threshold values at each value in gdacs.
    '''
    interpolation = interp1d(mean_threshold_calibration['gdac'], mean_threshold_calibration['mean_threshold'], kind='slinear', bounds_error=True)
    return interpolation(gdac)


# def get_pixel_thresholds_from_calibration_table(column, row, gdacs, threshold_calibration_table):
#     '''Calculates the pixel threshold from the threshold calibration at the given gdac settings (gdacs). If the given gdac value was not used during caluibration
#     the value is determined by interpolation.
# 
#     Parameters
#     ----------
#     column/row: ndarray
#     gdacs : array like
#         The GDAC settings where the threshold should be determined from the calibration
#     threshold_calibration_table : pytable
#         The table created during the calibration scan.
# 
#     Returns
#     -------
#     numpy.array, shape=(len(column), len(row), len(gdac), )
#         The pixel threshold values at each value in gdacs.
#     '''
#     pixel_gdacs = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['gdac']
#     pixel_thresholds = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['threshold']
#     interpolation = interp1d(x=pixel_gdacs, y=pixel_thresholds, kind='slinear', bounds_error=True)
#     return interpolation(gdacs)


def get_pixel_thresholds_from_calibration_array(gdacs, calibration_gdacs, threshold_calibration_array):
    '''Calculates the threshold for all pixels in threshold_calibration_array at the given GDAC settings via linear interpolation. The GDAC settings used during calibration have to be given.

    Parameters
    ----------
    gdacs : array like
        The GDAC settings where the threshold should be determined from the calibration
    calibration_gdacs : array like
        GDAC settings used during calibration, needed to translate the index of the calibration array to a value.
    threshold_calibration_array : numpy.array, shape=(80,336,# of GDACs during calibration)
        The calibration array

    Returns
    -------
    numpy.array, shape=(80,336,# gdacs given)
        The threshold values for each pixel at gdacs.
    '''
    if len(calibration_gdacs) != threshold_calibration_array.shape[2]:
        raise ValueError('Length of the provided pixel GDACs does not match the third dimension of the calibration array')
    interpolation = interp1d(x=calibration_gdacs, y=threshold_calibration_array, kind='slinear', bounds_error=True)
    return interpolation(gdacs)



if __name__ == "__main__":
    l = [1, 2, 11999, 20000]
    ll = [1, 2, 11998, 11999]
    print reduce_sorted_to_intersect(l, ll)
    print reduce_sorted_to_intersect(ll, l)
 
    lll = [11999]
    print reduce_sorted_to_intersect(l, lll)
    print reduce_sorted_to_intersect(lll, l)
 
    llll = [0]
    print reduce_sorted_to_intersect(ll, llll)
    print reduce_sorted_to_intersect(llll, ll)
