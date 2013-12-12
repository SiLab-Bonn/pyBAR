"""This class provides often needed analysis functions, for analysis that is done with python.
"""

import logging
import pandas as pd
import numpy as np
import numexpr as ne
import tables as tb
from scipy.sparse import coo_matrix
from datetime import datetime

from analysis.RawDataConverter.data_histograming import PyDataHistograming

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
    index = np.empty(len(idx) - 1, dtype={'names': [scan_parameter_name, 'index'], 'formats': ['u4','u4']})
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


# @profile
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
    data_frame_hits = pd.DataFrame({'event_number': hits_table[:]['event_number'], 'column': hits_table[:]['column'], 'row': hits_table[:]['row']})
    data_frame_hits = data_frame_hits.set_index(keys='event_number')
    events_with_n_cluster = get_events_with_n_cluster(cluster_table, condition)
    data_frame_hits = data_frame_hits.reset_index()
    return data_frame_hits.loc[events_with_n_cluster]


def get_hits_in_events(hits_array, events):
    '''Selects the hits that occurred in events.

    Parameters
    ----------
    hits_array : numpy.array
    events : array

    Returns
    -------
    numpy.array
        hit array with the hits in events.
    '''

    logging.info("Calculate hits that exists in the given %d events." % len(events))
    try:
        hits_in_events = hits_array[np.in1d(hits_array['event_number'], events)]
    except MemoryError:
        logging.error('There are too many hits to do in RAM operations. Use the write_hits_in_events function instead.')
        raise MemoryError
    return hits_in_events


def write_hits_in_events(hit_table_in, hit_table_out, events, chunk_size=5000000):  # TODO: speed up: use the fact that the events in hit_table_in are sorted
    '''Selects the hits that occurred in events and write them to a pytable. This function reduces the in RAM operations and has to be used if the get_hits_in_events
        function raises a memory error.

    Parameters
    ----------
    hit_table_in : pytable.table
    hit_table_out : pytable.table
        functions need to be able to write to hit_table_out
    events : array like
        defines the events to be written from hit_table_in to hit_table_out. They do not have to exists at all.
    chunk_size : int
        defines how many hits are analysed in RAM. Bigger numbers increase the speed, to big numbers let the program crash with a memory error.
    '''
    max_event = np.amax(events)
    logging.info("Write hits that exists in the given %d events < event number %d into a new hit table." % (len(events),max_event) )
    table_size = hit_table_in.shape[0]
    for iHit in range(0, table_size, chunk_size):
        hits = hit_table_in.read(iHit, iHit + chunk_size)
        last_event_number = hits[-1]['event_number']
        hit_table_out.append(get_hits_in_events(hits, events=events))
        if last_event_number > max_event:  # small speed up
            break


def get_events_with_n_cluster(cluster_table, condition='n_cluster==1'):
    '''Selects the events with a certain number of cluster.

    Parameters
    ----------
    hits_table : pytables.table
    cluster_table : pytables.table

    Returns
    -------
    numpy.array
    '''

    logging.info("Calculate events with clusters where " + condition)
    n_cluster_in_events = get_n_cluster_in_events(cluster_table)
    n_cluster = n_cluster_in_events[:, 1]
    return n_cluster_in_events[ne.evaluate(condition), 0]


def get_events_with_cluster_size(cluster_table, condition='cluster_size==1'):
    '''Selects the events with cluster of a given cluster size.

    Parameters
    ----------
    cluster_table : pytables.table
    condition : string

    Returns
    -------
    numpy.array
    '''

    logging.info("Calculate events with clusters with " + condition)
    cluster_table = cluster_table[:]
    cluster_size = cluster_table['size']
    return np.unique(cluster_table[ne.evaluate(condition)]['event_number'])


# @profile
def get_n_cluster_in_events(cluster_table):
    '''Calculates the number of cluster in every event.

    Parameters
    ----------
    cluster_table : pytables.table

    Returns
    -------
    numpy.Array
        First dimension is the event number
        Second dimension is the number of cluster of the event
    '''
    logging.info("Calculate the number of cluster in every event")
    event_number_array = cluster_table[:]['event_number']
    event_number_array = event_number_array.astype('<i4')  # BUG in numpy, unint work with 64-bit linux, Windows 32 bit needs reinterpretation
    cluster_in_event = np.bincount(event_number_array)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
    event_number = np.nonzero(cluster_in_event)[0]
    return np.vstack((event_number, cluster_in_event[event_number])).T


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

#     def fast_occupancy_histograming(self, hits): TODO bring this to work
#         hit_histograming = PyDataHistograming()
#         hit_histograming.set_info_output(True)
#         hit_histograming.set_debug_output(True)
#         hit_histograming.create_occupancy_hist(True)
# 
#         hit_histograming.add_hits(hits, hits.shape[0])
#         occupancy_hist = np.zeros(80 * 336 * hit_histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
#         hit_histograming.get_occupancy(occupancy_hist)
#         occupancy_hist = np.reshape(a=occupancy.view(), newshape=(80, 336, hit_histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
#         occupancy_hist = np.swapaxes(occupancy_hist, 0, 1)
#         return occupancy_hist


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
