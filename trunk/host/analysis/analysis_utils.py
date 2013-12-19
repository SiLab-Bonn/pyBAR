"""This class provides often needed analysis functions, for analysis that is done with python.
"""

import logging
import pandas as pd
import numpy as np
import numexpr as ne
from scipy.sparse import coo_matrix
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def central_difference(x, y):
    '''Returns the dy/dx(x) visa central difference method

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


def in1d_sorted(ar1, ar2):
    """
    Does the same than np.in1d but uses the fact that ar1 and ar2 are sorted. Is therefore much faster.

    """
    inds = ar2.searchsorted(ar1)
    inds[inds == len(ar2)] = 0
    return ar2[inds] == ar1


def reduce_sorted_to_intersect(ar1, ar2):
    """
    Takes two sorted arrays and return the intersection ar1 in ar2 and ar2 in ar1.

    Parameters
    ----------
    ar1 : (M,) array_like
        Input array.
    ar2 : array_like
         Input array.

    Returns
    -------
    ar1, ar1 : ndarray, ndarray
        The interesction values.

    """
    # Ravel both arrays, behavior for the first array could be different
    ar1 = np.asarray(ar1).ravel()
    ar2 = np.asarray(ar2).ravel()

    # get min max values of the arrays
    ar1_biggest_value = ar1[-1]
    ar1_smallest_value = ar1[0]
    ar2_biggest_value = ar2[-1]
    ar2_smallest_value = ar2[0]

    if ar1_biggest_value < ar2_smallest_value or ar1_smallest_value > ar2_biggest_value or ar1_smallest_value == ar1_biggest_value or ar2_smallest_value == ar2_biggest_value:  # special case, no intersection at all
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
    logging.info("Calculate hits that exists in the given event range [%d,%d[." % (event_start, event_stop))
    event_number = hits_array['event_number']
    if assume_sorted:
        hits_event_start = hits_array['event_number'][0]
        hits_event_stop = hits_array['event_number'][-1]
        if hits_event_stop < event_start or hits_event_start > event_stop or event_start == event_stop:  # special case, no intersection at all
            print 'return NADA'
            return hits_array[0:0]

        # get min/max indices with values that are also in the other array
        min_index_hits = np.argmin(hits_array['event_number'] < event_start)
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
    max_event = np.amax(events)
    logging.info("Write hits from hit number >= %d that exists in the selected %d events with event number < %d into a new hit table." % (start_hit_word, len(events), max_event))
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


def get_n_cluster_in_events(event_number):
    '''Calculates the number of cluster in every event.

    Parameters
    ----------
    event_number : numpy.array

    Returns
    -------
    numpy.Array
        First dimension is the event number
        Second dimension is the number of cluster of the event
    '''
    logging.info("Calculate the number of cluster in every given event")
    if (sys.maxint < 3000000000):  # on 32- bit operation systems max int is 2147483647 leading to numpy bugs that need workarounds
        event_number_array = event_number.astype('<i4')  # BUG in numpy, unint works with 64-bit, 32 bit needs reinterpretation
        offset = np.amin(event_number_array)
        event_number_array = np.subtract(event_number_array, offset)  # BUG #225 for values > int32
        cluster_in_event = np.bincount(event_number_array)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
        selected_event_number_index = np.nonzero(cluster_in_event)[0]
        selected_event_number = np.add(selected_event_number_index, offset)
        return np.vstack((selected_event_number, cluster_in_event[selected_event_number_index])).T
    else:
        cluster_in_event = np.bincount(event_number)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
        selected_event_number = np.nonzero(cluster_in_event)[0]
        return np.vstack((selected_event_number, cluster_in_event[selected_event_number])).T


# @profile
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


# @profile
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
    for scan_par_name in meta_data_array.dtype.names[len(meta_data_array.dtype.names) - 1:len(meta_data_array.dtype.names)]:
        scan_parameters[scan_par_name] = np.unique(meta_data_array[scan_par_name])
    return scan_parameters


def data_aligned_at_events(table, start_event_number=None, stop_event_number=None, start=None, stop=None, chunk_size=10000000):
    '''Takes the table with a event_number column and returns chunks with the size up to chunk_size. The chunks are chosen in a way that the events are not splitted. Additional
    parameters can be set to increase the readout speed. If only events between a certain event range are used one can specify this. Also the start and the
    stop indices for the reading of the table can be specified for speed up.

    Parameters
    ----------
    table : pytables.table
    start_event_number : int
        The data read is corrected that only data starting from the start_event number is returned. Lower event numbers are discarded.
    stop_event_number : int
        The data read is corrected that only data up to the stop_event number is returned. The stop_event number is not included.
    Returns
    -------
    numpy.histogram
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
    last_event_start_index = 0
    start_index = 0 if start == None else start
    stop_index = table.nrows if stop == None else stop

    # set start stop indices from the event numbers for fast read if possible, not possible if the given event number does not exist
    if start_event_number != None:
        condition_1 = 'event_number==' + str(start_event_number)
        start_indeces = table.get_where_list(condition_1)
        if len(start_indeces) != 0:  # set start index if possible
            start_index = start_indeces[0]
            start_index_known = True
    else:
        start_event_number = 0

    if stop_event_number != None:
        condition_2 = 'event_number==' + str(stop_event_number)
        stop_indeces = table.get_where_list(condition_2)
        if len(stop_indeces) != 0:  # set the stop index if possible, stop index is excluded
            stop_index = stop_indeces[0]

    if start_index_known and start_index + chunk_size >= stop_index:  # special case, one read is enough, data not bigger than one chunk and the indices are known
            yield table.read(start=start_index, stop=stop_index), stop_index
            start_index = stop_index
    else:  # read data in chunks, chunks do not devide events, abort if maximum event number is reached
        while(start_index < stop_index):
            src_array = table.read(start=start_index, stop=start_index + chunk_size + 1)  # stop index is exclusive, so add 1
            if start_index + src_array.shape[0] == table.nrows:
                nrows = src_array.shape[0]
            else:
                first_event = src_array["event_number"][0]
                last_event = src_array["event_number"][-1]
                last_event_start_index = np.argmax(src_array["event_number"] == last_event)  # speedup
                if last_event_start_index == 0:
                    nrows = src_array.shape[0]
                    logging.warning("Buffer too small to fit event. Possible loss of data. Increase chunk size.")
                else:
                    nrows = last_event_start_index

            if stop_event_number != None and last_event > stop_event_number or first_event < start_event_number:
                yield get_hits_in_event_range(src_array[0:nrows], event_start=start_event_number, event_stop=stop_event_number, assume_sorted=True), start_index
                break
            else:
                yield src_array[0:nrows], start_index + nrows
            start_index = start_index + nrows


class AnalysisUtils(object):
    """A class to analyze FE-I4 data with Python"""
    def __init__(self, raw_data_file=None, analyzed_data_file=None):
        self.set_standard_settings()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def set_standard_settings(self):
        pass

if __name__ == "__main__":
    pass
