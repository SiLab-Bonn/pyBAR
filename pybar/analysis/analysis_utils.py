"""This class provides often needed analysis functions, for analysis that is done with python.
"""
from __future__ import division

import logging
import re
import os
import time
import glob
import collections
from operator import itemgetter

import numpy as np
import tables as tb
import numexpr as ne
from scipy.interpolate import interp1d
from scipy.interpolate import splrep, splev

import progressbar

from pybar_fei4_interpreter import analysis_utils
from pybar.daq.fei4_record import FEI4Record
from pybar.analysis.plotting import plotting
from pybar.daq.readout_utils import is_fe_word, is_data_header, is_trigger_word, logical_and


class AnalysisError(Exception):

    """Base class for exceptions in this module.
    """


class IncompleteInputError(AnalysisError):

    """Exception raised for errors in the input.
    """


class InvalidInputError(AnalysisError):

    """Exception raised for errors in the input.
    """


class NotSupportedError(AnalysisError):

    """Exception raised for not supported actions.
    """


def generate_threshold_mask(hist):
    '''Masking array elements when equal 0.0 or greater than 10 times the median

    Parameters
    ----------
    hist : array_like
        Input data.

    Returns
    -------
    masked array
        Returns copy of the array with masked elements.
    '''
    masked_array = np.ma.masked_values(hist, 0)
    masked_array = np.ma.masked_greater(masked_array, 10 * np.ma.median(hist))
    logging.info('Masking %d pixel(s)', np.ma.count_masked(masked_array))
    return np.ma.getmaskarray(masked_array)


def unique_row(array, use_columns=None, selected_columns_only=False):
    '''Takes a numpy array and returns the array reduced to unique rows. If columns are defined only these columns are taken to define a unique row.
    The returned array can have all columns of the original array or only the columns defined in use_columns.
    Parameters
    ----------
    array : numpy.ndarray
    use_columns : list
        Index of columns to be used to define a unique row
    selected_columns_only : bool
        If true only the columns defined in use_columns are returned

    Returns
    -------
    numpy.ndarray
    '''
    if array.dtype.names is None:  # normal array has no named dtype
        if use_columns is not None:
            a_cut = array[:, use_columns]
        else:
            a_cut = array
        if len(use_columns) > 1:
            b = np.ascontiguousarray(a_cut).view(np.dtype((np.void, a_cut.dtype.itemsize * a_cut.shape[1])))
        else:
            b = np.ascontiguousarray(a_cut)
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


def get_ranges_from_array(arr, append_last=True):
    '''Takes an array and calculates ranges [start, stop[. The last range end is none to keep the same length.

    Parameters
    ----------
    arr : array like
    append_last: bool
        If True, append item with a pair of last array item and None.

    Returns
    -------
    numpy.array
        The array formed by pairs of values by the given array.

    Example
    -------
    >>> a = np.array((1,2,3,4))
    >>> get_ranges_from_array(a, append_last=True)
    array([[1, 2],
           [2, 3],
           [3, 4],
           [4, None]])
    >>> get_ranges_from_array(a, append_last=False)
    array([[1, 2],
           [2, 3],
           [3, 4]])
    '''
    right = arr[1:]
    if append_last:
        left = arr[:]
        right = np.append(right, None)
    else:
        left = arr[:-1]
    return np.column_stack((left, right))


def get_mean_from_histogram(counts, bin_positions, axis=0):
    return np.average(counts, axis=axis, weights=bin_positions) * bin_positions.sum() / np.nansum(counts, axis=axis)


def get_median_from_histogram(counts, bin_positions):
    return np.median(np.repeat(bin_positions, counts))


def get_rms_from_histogram(counts, bin_positions):
    return np.std(np.repeat(bin_positions, counts))


def in1d_sorted(ar1, ar2):
    """
    Does the same than np.in1d but uses the fact that ar1 and ar2 are sorted. Is therefore much faster.

    """
    if ar1.shape[0] == 0 or ar2.shape[0] == 0:  # check for empty arrays to avoid crash
        return []
    inds = ar2.searchsorted(ar1)
    inds[inds == len(ar2)] = 0
    return ar2[inds] == ar1


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
    y = y.astype(np.float32)
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


def get_rate_normalization(hit_file, parameter, reference='event', cluster_file=None, plot=False, chunk_size=500000):
    ''' Takes different hit files (hit_files), extracts the number of events or the scan time (reference) per scan parameter (parameter)
    and returns an array with a normalization factor. This normalization factor has the length of the number of different parameters.
    If a cluster_file is specified also the number of cluster per event are used to create the normalization factor.

    Parameters
    ----------
    hit_files : string
    parameter : string
    reference : string
    plot : bool

    Returns
    -------
    numpy.ndarray
    '''

    logging.info('Calculate the rate normalization')
    with tb.open_file(hit_file, mode="r+") as in_hit_file_h5:  # open the hit file
        meta_data = in_hit_file_h5.root.meta_data[:]
        scan_parameter = get_scan_parameter(meta_data)[parameter]
        event_numbers = get_meta_data_at_scan_parameter(meta_data, parameter)['event_number']  # get the event numbers in meta_data where the scan parameter changes
        event_range = get_ranges_from_array(event_numbers)
        normalization_rate = []
        normalization_multiplicity = []
        try:
            event_range[-1, 1] = in_hit_file_h5.root.Hits[-1]['event_number'] + 1
        except tb.NoSuchNodeError:
            logging.error('Cannot find hits table')
            return

        # calculate rate normalization from the event rate for triggered data / measurement time for self triggered data for each scan parameter
        if reference == 'event':
            n_events = event_range[:, 1] - event_range[:, 0]  # number of events for every parameter setting
            normalization_rate.extend(n_events)
        elif reference == 'time':
            time_start = get_meta_data_at_scan_parameter(meta_data, parameter)['timestamp_start']
            time_spend = np.diff(time_start)
            time_spend = np.append(time_spend, meta_data[-1]['timestamp_stop'] - time_start[-1])  # TODO: needs check, add last missing entry
            normalization_rate.extend(time_spend)
        else:
            raise NotImplementedError('The normalization reference ' + reference + ' is not implemented')

        if cluster_file:  # calculate the rate normalization from the mean number of hits per event per scan parameter, needed for beam data since a beam since the multiplicity is rarely constant
            cluster_table = in_hit_file_h5.root.Cluster
            index_event_number(cluster_table)
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping, variable for read speed up
            best_chunk_size = chunk_size  # variable for read speed up
            total_cluster = 0
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA(smoothing=0.8)], maxval=cluster_table.shape[0], term_width=80)
            progress_bar.start()
            for start_event, stop_event in event_range:  # loop over the selected events
                readout_cluster_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                n_cluster_per_event = None
                for clusters, index in data_aligned_at_events(cluster_table, start_event_number=start_event, stop_event_number=stop_event, start_index=index, chunk_size=best_chunk_size):
                    if n_cluster_per_event is None:
                        n_cluster_per_event = analysis_utils.get_n_cluster_in_events(clusters['event_number'])[:, 1]  # array with the number of cluster per event, cluster per event are at least 1
                    else:
                        n_cluster_per_event = np.append(n_cluster_per_event, analysis_utils.get_n_cluster_in_events(clusters['event_number'])[:, 1])
                    readout_cluster_len += clusters.shape[0]
                    total_cluster += clusters.shape[0]
                    progress_bar.update(index)
                best_chunk_size = int(1.5 * readout_cluster_len) if int(1.05 * readout_cluster_len) < chunk_size else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                normalization_multiplicity.append(np.mean(n_cluster_per_event))
            progress_bar.finish()
            if total_cluster != cluster_table.shape[0]:
                logging.warning('Analysis shows inconsistent number of cluster (%d != %d). Check needed!', total_cluster, cluster_table.shape[0])

    if plot:
        x = scan_parameter
        if reference == 'event':
            plotting.plot_scatter(x, normalization_rate, title='Events per ' + parameter + ' setting', x_label=parameter, y_label='# events', log_x=True, filename=os.path.splitext(hit_file)[0] + '_n_event_normalization.pdf')
        elif reference == 'time':
            plotting.plot_scatter(x, normalization_rate, title='Measuring time per GDAC setting', x_label=parameter, y_label='time [s]', log_x=True, filename=os.path.splitext(hit_file)[0] + '_time_normalization.pdf')
        if cluster_file:
            plotting.plot_scatter(x, normalization_multiplicity, title='Mean number of particles per event', x_label=parameter, y_label='number of hits per event', log_x=True, filename=os.path.splitext(hit_file)[0] + '_n_particles_normalization.pdf')
    if cluster_file:
        normalization_rate = np.array(normalization_rate)
        normalization_multiplicity = np.array(normalization_multiplicity)
        return np.amax(normalization_rate * normalization_multiplicity).astype('f16') / (normalization_rate * normalization_multiplicity)
    return np.amax(np.array(normalization_rate)).astype('f16') / np.array(normalization_rate)


def get_total_n_data_words(files_dict, precise=False):
    n_words = 0
    if precise:  # open all files and determine the total number of words precicely, can take some time
        if len(files_dict) > 10:
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA()], maxval=len(files_dict), term_width=80)
            progress_bar.start()
        for index, file_name in enumerate(files_dict.iterkeys()):
            with tb.open_file(file_name, mode="r") as in_file_h5:  # open the actual file
                n_words += in_file_h5.root.raw_data.shape[0]
            if len(files_dict) > 10:
                progress_bar.update(index)
        if len(files_dict) > 10:
            progress_bar.finish()
        return n_words
    else:  # open just first an last file and take the mean to estimate the total numbe rof words
        with tb.open_file(files_dict.keys()[0], mode="r") as in_file_h5:  # open the actual file
            n_words += in_file_h5.root.raw_data.shape[0]
        with tb.open_file(files_dict.keys()[-1], mode="r") as in_file_h5:  # open the actual file
            n_words += in_file_h5.root.raw_data.shape[0]
        return n_words * len(files_dict) / 2


def create_parameter_table(files_dict):
    if not check_parameter_similarity(files_dict):
        raise RuntimeError('Cannot create table from file with different scan parameters.')
    # create the parameter names / format for the parameter table
    try:
        names = ','.join([name for name in files_dict.itervalues().next().keys()])
        formats = ','.join(['int32' for name in files_dict.itervalues().next().keys()])
        arrayList = [l for l in files_dict.itervalues().next().values()]
    except AttributeError:  # no parameters given, return None
        return
    parameter_table = None
    # create a parameter table with an entry for every read out
    for file_name, parameters in files_dict.iteritems():
        with tb.open_file(file_name, mode="r") as in_file_h5:  # open the actual file
            n_parameter_settings = max([len(i) for i in files_dict[file_name].values()])  # determine the number of different parameter settings from the list length of parameter values of the first parameter
            if n_parameter_settings == 0:  # no parameter values, first raw data file has only config info and no other data (meta, raw data, parameter data)
                continue
            try:  # try to combine the scan parameter tables
                if parameter_table is None:  # final parameter_table does not exists, so create is
                    parameter_table = in_file_h5.root.scan_parameters[:]
                else:  # final parameter table already exist, so append to existing
                    parameter_table.resize(parameter_table.shape[0] + in_file_h5.root.scan_parameters[:].shape[0], refcheck=False)  # fastest way to append, http://stackoverflow.com/questions/1730080/append-rows-to-a-numpy-record-array
                    parameter_table[-in_file_h5.root.scan_parameters.shape[0]:] = in_file_h5.root.scan_parameters[:]  # set table
            except tb.NoSuchNodeError:  # there is no scan parameter table, so create one
                read_out = in_file_h5.root.meta_data.shape[0]
                if parameter_table is None:  # final parameter_table does not exists, so create is
                    parameter_table = np.rec.fromarrays(arrayList, names=names, formats=formats)  # create recarray
                    parameter_table.resize(read_out, refcheck=False)
                    parameter_table[-read_out:] = np.rec.fromarrays(arrayList, names=names, formats=formats)
                else:  # final parameter table already exist, so append to existing
                    parameter_table.resize(parameter_table.shape[0] + read_out)  # fastest way to append, http://stackoverflow.com/questions/1730080/append-rows-to-a-numpy-record-array
                    parameter_table[-read_out:] = np.rec.fromarrays([l for l in parameters.values()], names=names, formats=formats)

    return parameter_table


def get_parameter_value_from_file_names(files, parameters=None, unique=False, sort=True):
    """
    Takes a list of files, searches for the parameter name in the file name and returns a ordered dict with the file name
    in the first dimension and the corresponding parameter value in the second.
    The file names can be sorted by the parameter value, otherwise the order is kept. If unique is true every parameter is unique and
    mapped to the file name that occurred last in the files list.

    Parameters
    ----------
    files : list of strings
    parameter : string or list of strings
    unique : bool
    sort : bool

    Returns
    -------
    collections.OrderedDict

    """
#     unique=False
    logging.debug('Get the parameter: ' + str(parameters) + ' values from the file names of ' + str(len(files)) + ' files')
    files_dict = collections.OrderedDict()
    if parameters is None:  # special case, no parameter defined
        return files_dict
    if isinstance(parameters, basestring):
        parameters = (parameters, )
    search_string = '_'.join(parameters)
    for _ in parameters:
        search_string += r'_(-?\d+)'
    result = {}
    for one_file in files:
        parameter_values = re.findall(search_string, one_file)
        if parameter_values:
            if isinstance(parameter_values[0], tuple):
                parameter_values = list(reduce(lambda t1, t2: t1 + t2, parameter_values))
            parameter_values = [[int(i), ] for i in parameter_values]  # convert string value to list with int
            files_dict[one_file] = dict(zip(parameters, parameter_values))
            if unique:  # reduce to the files with different scan parameters
                for key, value in files_dict.items():
                    if value not in result.values():
                        result[key] = value
            else:
                result[one_file] = files_dict[one_file]
    return collections.OrderedDict(sorted(result.iteritems(), key=itemgetter(1)) if sort else files_dict)  # with PEP 265 solution of sorting a dict by value


def get_data_file_names_from_scan_base(scan_base, filter_str=['_analyzed.h5', '_interpreted.h5', '_cut.h5', '_result.h5', '_hists.h5'], sort_by_time=True, meta_data_v2=True):
    """
    Generate a list of .h5 files which have a similar file name.

    Parameters
    ----------
    scan_base : list, string
        List of string or string of the scan base names. The scan_base will be used to search for files containing the string. The .h5 file extension will be added automatically.
    filter : list, string
        List of string or string which are used to filter the returned filenames. File names containing filter_str in the file name will not be returned. Use None to disable filter.
    sort_by_time : bool
        If True, return file name list sorted from oldest to newest. The time from meta table will be used to sort the files.
    meta_data_v2 : bool
        True for new (v2) meta data format, False for the old (v1) format.

    Returns
    -------
    data_files : list
        List of file names matching the obove conditions.
    """
    data_files = []
    if scan_base is None:
        return data_files
    if isinstance(scan_base, basestring):
        scan_base = [scan_base]
    for scan_base_str in scan_base:
        if '.h5' == os.path.splitext(scan_base_str)[1]:
            data_files.append(scan_base_str)
        else:
            data_files.extend(glob.glob(scan_base_str + '*.h5'))

    if filter_str:
        if isinstance(filter_str, basestring):
            filter_str = [filter_str]
        data_files = filter(lambda data_file: not any([(True if x in data_file else False) for x in filter_str]), data_files)
    if sort_by_time and len(data_files) > 1:
        f_list = {}
        for data_file in data_files:
            with tb.open_file(data_file, mode="r") as h5_file:
                try:
                    meta_data = h5_file.root.meta_data
                except tb.NoSuchNodeError:
                    logging.warning("File %s is missing meta_data" % h5_file.filename)
                else:
                    try:
                        if meta_data_v2:
                            timestamp = meta_data[0]["timestamp_start"]
                        else:
                            timestamp = meta_data[0]["timestamp"]
                    except IndexError:
                        logging.info("File %s has empty meta_data" % h5_file.filename)
                    else:
                        f_list[data_file] = timestamp

        data_files = list(sorted(f_list, key=f_list.__getitem__, reverse=False))
    return data_files


def get_scan_parameter_names(scan_parameters):
    ''' Returns the scan parameter names of the scan_paraemeter table.

    Parameters
    ----------
    scan_parameters : numpy.array
        Can be None

    Returns
    -------
    list of strings
    '''
    return scan_parameters.dtype.names if scan_parameters is not None else None


def get_parameter_from_files(files, parameters=None, unique=False, sort=True):
    ''' Takes a list of files, searches for the parameter name in the file name and in the file.
    Returns a ordered dict with the file name in the first dimension and the corresponding parameter values in the second.
    If a scan parameter appears in the file name and in the file the first parameter setting has to be in the file name, otherwise a warning is shown.
    The file names can be sorted by the first parameter value of each file.

    Parameters
    ----------
    files : string, list of strings
    parameters : string, list of strings
    unique : boolean
        If set only one file per scan parameter value is used.
    sort : boolean

    Returns
    -------
    collections.OrderedDict

    '''
    logging.debug('Get the parameter ' + str(parameters) + ' values from ' + str(len(files)) + ' files')
    files_dict = collections.OrderedDict()
    if isinstance(files, basestring):
        files = (files, )
    if isinstance(parameters, basestring):
        parameters = (parameters, )
    parameter_values_from_file_names_dict = get_parameter_value_from_file_names(files, parameters, unique=unique, sort=sort)  # get the parameter from the file name
    for file_name in files:
        with tb.open_file(file_name, mode="r") as in_file_h5:  # open the actual file
            scan_parameter_values = collections.OrderedDict()
            try:
                scan_parameters = in_file_h5.root.scan_parameters[:]  # get the scan parameters from the scan parameter table
                if parameters is None:
                    parameters = get_scan_parameter_names(scan_parameters)
                for parameter in parameters:
                    try:
                        scan_parameter_values[parameter] = np.unique(scan_parameters[parameter]).tolist()  # different scan parameter values used
                    except ValueError:  # the scan parameter does not exists
                        pass
            except tb.NoSuchNodeError:  # scan parameter table does not exist
                try:
                    scan_parameters = get_scan_parameter(in_file_h5.root.meta_data[:])  # get the scan parameters from the meta data
                    if scan_parameters:
                        try:
                            scan_parameter_values = np.unique(scan_parameters[parameters]).tolist()  # different scan parameter values used
                        except ValueError:  # the scan parameter does not exists
                            pass
                except tb.NoSuchNodeError:  # meta data table does not exist
                    pass
            if not scan_parameter_values:  # if no scan parameter values could be set from file take the parameter found in the file name
                try:
                    scan_parameter_values = parameter_values_from_file_names_dict[file_name]
                except KeyError:  # no scan parameter found at all, neither in the file name nor in the file
                    scan_parameter_values = None
            else:  # use the parameter given in the file and cross check if it matches the file name parameter if these is given
                try:
                    for key, value in scan_parameter_values.items():
                        if value and value[0] != parameter_values_from_file_names_dict[file_name][key][0]:  # parameter value exists: check if the first value is the file name value
                            logging.warning('Parameter values in the file name and in the file differ. Take ' + str(key) + ' parameters ' + str(value) + ' found in %s.', file_name)
                except KeyError:  # parameter does not exists in the file name
                    pass
                except IndexError:
                    raise IncompleteInputError('Something wrong check!')
            if unique and scan_parameter_values is not None:
                existing = False
                for parameter in scan_parameter_values:  # loop to determine if any value of any scan parameter exists already
                    all_par_values = [values[parameter] for values in files_dict.values()]
                    if any(x in [scan_parameter_values[parameter]] for x in all_par_values):
                        existing = True
                        break
                if not existing:
                    files_dict[file_name] = scan_parameter_values
                else:
                    logging.warning('Scan parameter value(s) from %s exists already, do not add to result', file_name)
            else:
                files_dict[file_name] = scan_parameter_values
    return collections.OrderedDict(sorted(files_dict.iteritems(), key=itemgetter(1)) if sort else files_dict)


def check_parameter_similarity(files_dict):
    """
    Checks if the parameter names of all files are similar. Takes the dictionary from get_parameter_from_files output as input.

    """
    try:
        parameter_names = files_dict.itervalues().next().keys()  # get the parameter names of the first file, to check if these are the same in the other files
    except AttributeError:  # if there is no parameter at all
        if any(i is not None for i in files_dict.itervalues()):  # check if there is also no parameter for the other files
            return False
        else:
            return True
    if any(parameter_names != i.keys() for i in files_dict.itervalues()):
        return False
    return True


def combine_meta_data(files_dict, meta_data_v2=True):
    """
    Takes the dict of hdf5 files and combines their meta data tables into one new numpy record array.

    Parameters
    ----------
    meta_data_v2 : bool
        True for new (v2) meta data format, False for the old (v1) format.
    """
    if len(files_dict) > 10:
        logging.info("Combine the meta data from %d files", len(files_dict))
    # determine total length needed for the new combined array, thats the fastest way to combine arrays
    total_length = 0  # the total length of the new table
    for file_name in files_dict.iterkeys():
        with tb.open_file(file_name, mode="r") as in_file_h5:  # open the actual file
            total_length += in_file_h5.root.meta_data.shape[0]

    if meta_data_v2:
        meta_data_combined = np.empty((total_length, ), dtype=[
            ('index_start', np.uint32),
            ('index_stop', np.uint32),
            ('data_length', np.uint32),
            ('timestamp_start', np.float64),
            ('timestamp_stop', np.float64),
            ('error', np.uint32)])
    else:
        meta_data_combined = np.empty((total_length, ), dtype=[
            ('start_index', np.uint32),
            ('stop_index', np.uint32),
            ('length', np.uint32),
            ('timestamp', np.float64),
            ('error', np.uint32)])

    if len(files_dict) > 10:
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA()], maxval=total_length, term_width=80)
        progress_bar.start()

    index = 0

    # fill actual result array
    for file_name in files_dict.iterkeys():
        with tb.open_file(file_name, mode="r") as in_file_h5:  # open the actual file
            array_length = in_file_h5.root.meta_data.shape[0]
            meta_data_combined[index:index + array_length] = in_file_h5.root.meta_data[:]
            index += array_length
            if len(files_dict) > 10:
                progress_bar.update(index)
    if len(files_dict) > 10:
        progress_bar.finish()
    return meta_data_combined


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


def select_hits(hits_array, condition=None):
    '''Selects the hits with condition.
    E.g.: condition = 'rel_BCID == 7 & event_number < 1000'

    Parameters
    ----------
    hits_array : numpy.array
    condition : string
        A condition that is applied to the hits in numexpr. Only if the expression evaluates to True the hit is taken.

    Returns
    -------
    numpy.array
        hit array with the selceted hits
    '''
    if condition is None:
        return hits_array

    for variable in set(re.findall(r'[a-zA-Z_]+', condition)):
        exec(variable + ' = hits_array[\'' + variable + '\']')

    return hits_array[ne.evaluate(condition)]


def get_hits_in_events(hits_array, events, assume_sorted=True, condition=None):
    '''Selects the hits that occurred in events and optional selection criterion.
        If a event range can be defined use the get_data_in_event_range function. It is much faster.

    Parameters
    ----------
    hits_array : numpy.array
    events : array
    assume_sorted : bool
        Is true if the events to select are sorted from low to high value. Increases speed by 35%.
    condition : string
        A condition that is applied to the hits in numexpr. Only if the expression evaluates to True the hit is taken.

    Returns
    -------
    numpy.array
        hit array with the hits in events.
    '''

    logging.debug("Calculate hits that exists in the given %d events." % len(events))
    if assume_sorted:
        events, _ = reduce_sorted_to_intersect(events, hits_array['event_number'])  # reduce the event number range to the max min event number of the given hits to save time
        if events.shape[0] == 0:  # if there is not a single selected hit
            return hits_array[0:0]
    try:
        if assume_sorted:
            selection = analysis_utils.in1d_events(hits_array['event_number'], events)
        else:
            logging.warning('Events are usually sorted. Are you sure you want this?')
            selection = np.in1d(hits_array['event_number'], events)
        if condition is None:
            hits_in_events = hits_array[selection]
        else:
            # bad hack to be able to use numexpr
            for variable in set(re.findall(r'[a-zA-Z_]+', condition)):
                exec(variable + ' = hits_array[\'' + variable + '\']')

            hits_in_events = hits_array[ne.evaluate(condition + ' & selection')]
    except MemoryError:
        logging.error('There are too many hits to do in RAM operations. Consider decreasing chunk size and use the write_hits_in_events function instead.')
        raise MemoryError
    return hits_in_events


def get_hits_of_scan_parameter(input_file_hits, scan_parameters=None, try_speedup=False, chunk_size=10000000):
    '''Takes the hit table of a hdf5 file and returns hits in chunks for each unique combination of scan_parameters.
    Yields the hits in chunks, since they usually do not fit into memory.

    Parameters
    ----------
    input_file_hits : pytable hdf5 file
        Has to include a hits node
    scan_parameters : iterable with strings
    try_speedup : bool
        If true a speed up by searching for the event numbers in the data is done. If the event numbers are not in the data
        this slows down the search.
    chunk_size : int
        How many rows of data are read into ram.

    Returns
    -------
    Yields tuple, numpy.array
        Actual scan parameter tuple, hit array with the hits of a chunk of the given scan parameter tuple
    '''

    with tb.open_file(input_file_hits, mode="r+") as in_file_h5:
        hit_table = in_file_h5.root.Hits
        meta_data = in_file_h5.root.meta_data[:]
        meta_data_table_at_scan_parameter = get_unique_scan_parameter_combinations(meta_data, scan_parameters=scan_parameters)
        parameter_values = get_scan_parameters_table_from_meta_data(meta_data_table_at_scan_parameter, scan_parameters)
        event_number_ranges = get_ranges_from_array(meta_data_table_at_scan_parameter['event_number'])  # get the event number ranges for the different scan parameter settings
        index_event_number(hit_table)  # create a event_numer index to select the hits by their event number fast, no needed but important for speed up
#
        # variables for read speed up
        index = 0  # index where to start the read out of the hit table, 0 at the beginning, increased during looping
        best_chunk_size = chunk_size  # number of hits to copy to RAM during looping, the optimal chunk size is determined during looping

        # loop over the selected events
        for parameter_index, (start_event_number, stop_event_number) in enumerate(event_number_ranges):
            logging.debug('Read hits for ' + str(scan_parameters) + ' = ' + str(parameter_values[parameter_index]))

            readout_hit_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
            # loop over the hits in the actual selected events with optimizations: determine best chunk size, start word index given
            for hits, index in data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start_index=index, try_speedup=try_speedup, chunk_size=best_chunk_size):
                yield parameter_values[parameter_index], hits
                readout_hit_len += hits.shape[0]
            best_chunk_size = int(1.5 * readout_hit_len) if int(1.05 * readout_hit_len) < chunk_size and int(1.05 * readout_hit_len) > 1e3 else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction


def get_data_in_event_range(array, event_start=None, event_stop=None, assume_sorted=True):
    '''Selects the data (rows of a table) that occurred in the given event range [event_start, event_stop[

    Parameters
    ----------
    array : numpy.array
    event_start : int, None
    event_stop : int, None
    assume_sorted : bool
        Set to true if the hits are sorted by the event_number. Increases speed.

    Returns
    -------
    numpy.array
        hit array with the hits in the event range.
    '''
    logging.debug("Calculate data of the the given event range [" + str(event_start) + ", " + str(event_stop) + "[")
    event_number = array['event_number']
    if assume_sorted:
        data_event_start = event_number[0]
        data_event_stop = event_number[-1]
        if (event_start is not None and event_stop is not None) and (data_event_stop < event_start or data_event_start > event_stop or event_start == event_stop):  # special case, no intersection at all
            return array[0:0]

        # get min/max indices with values that are also in the other array
        if event_start is None:
            min_index_data = 0
        else:
            min_index_data = np.argmin(event_number < event_start)

        if event_stop is None:
            max_index_data = event_number.shape[0]
        else:
            max_index_data = np.argmax(event_number >= event_stop)

        if min_index_data < 0:
            min_index_data = 0
        if max_index_data == 0 or max_index_data > event_number.shape[0]:
            max_index_data = event_number.shape[0]
        return array[min_index_data:max_index_data]
    else:
        return array[ne.evaluate('event_number >= event_start & event_number < event_stop')]


def write_hits_in_events(hit_table_in, hit_table_out, events, start_hit_word=0, chunk_size=5000000, condition=None):
    '''Selects the hits that occurred in events and writes them to a pytable. This function reduces the in RAM operations and has to be
    used if the get_hits_in_events function raises a memory error. Also a condition can be set to select hits.

    Parameters
    ----------
    hit_table_in : pytable.table
    hit_table_out : pytable.table
        functions need to be able to write to hit_table_out
    events : array like
        defines the events to be written from hit_table_in to hit_table_out. They do not have to exists at all.
    start_hit_word: int
        Index of the first hit word to be analyzed. Used for speed up.
    chunk_size : int
        defines how many hits are analyzed in RAM. Bigger numbers increase the speed, too big numbers let the program crash with a memory error.
    condition : string
        A condition that is applied to the hits in numexpr style. Only if the expression evaluates to True the hit is taken.

    Returns
    -------
    start_hit_word: int
        Index of the last hit word analyzed. Used to speed up the next call of write_hits_in_events.
    '''
    if len(events) > 0:  # needed to avoid crash
        min_event = np.amin(events)
        max_event = np.amax(events)
        logging.debug("Write hits from hit number >= %d that exists in the selected %d events with %d <= event number <= %d into a new hit table." % (start_hit_word, len(events), min_event, max_event))
        table_size = hit_table_in.shape[0]
        iHit = 0
        for iHit in range(start_hit_word, table_size, chunk_size):
            hits = hit_table_in.read(iHit, iHit + chunk_size)
            last_event_number = hits[-1]['event_number']
            hit_table_out.append(get_hits_in_events(hits, events=events, condition=condition))
            if last_event_number > max_event:  # speed up, use the fact that the hits are sorted by event_number
                return iHit
    return start_hit_word


def write_hits_in_event_range(hit_table_in, hit_table_out, event_start=None, event_stop=None, start_hit_word=0, chunk_size=5000000, condition=None):
    '''Selects the hits that occurred in given event range [event_start, event_stop[ and write them to a pytable. This function reduces the in RAM
       operations and has to be used if the get_data_in_event_range function raises a memory error. Also a condition can be set to select hits.

    Parameters
    ----------
    hit_table_in : pytable.table
    hit_table_out : pytable.table
        functions need to be able to write to hit_table_out
    event_start, event_stop : int, None
        start/stop event numbers. Stop event number is excluded. If None start/stop is set automatically.
    chunk_size : int
        defines how many hits are analyzed in RAM. Bigger numbers increase the speed, too big numbers let the program crash with a memory error.
    condition : string
        A condition that is applied to the hits in numexpr style. Only if the expression evaluates to True the hit is taken.
    Returns
    -------
    start_hit_word: int
        Index of the last hit word analyzed. Used to speed up the next call of write_hits_in_events.
    '''

    logging.debug('Write hits that exists in the given event range from + ' + str(event_start) + ' to ' + str(event_stop) + ' into a new hit table')
    table_size = hit_table_in.shape[0]
    for iHit in range(0, table_size, chunk_size):
        hits = hit_table_in.read(iHit, iHit + chunk_size)
        last_event_number = hits[-1]['event_number']
        selected_hits = get_data_in_event_range(hits, event_start=event_start, event_stop=event_stop)
        if condition is not None:
            # bad hack to be able to use numexpr
            for variable in set(re.findall(r'[a-zA-Z_]+', condition)):
                exec(variable + ' = hits[\'' + variable + '\']')
            selected_hits = selected_hits[ne.evaluate(condition)]
        hit_table_out.append(selected_hits)
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

    logging.debug("Calculate events with clusters where " + condition)
    n_cluster_in_events = analysis_utils.get_n_cluster_in_events(event_number)
    n_cluster = n_cluster_in_events[:, 1]
#    return np.take(n_cluster_in_events, ne.evaluate(condition), axis=0)  # does not return 1d, bug?
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

    logging.debug("Calculate events with clusters with " + condition)
    return np.unique(event_number[ne.evaluate(condition)])


def get_events_with_error_code(event_number, event_status, select_mask=0b1111111111111111, condition=0b0000000000000000):
    '''Selects the events with a certain error code.

    Parameters
    ----------
    event_number : numpy.array
    event_status : numpy.array
    select_mask : int
        The mask that selects the event error code to check.
    condition : int
        The value the selected event error code should have.

    Returns
    -------
    numpy.array
    '''

    logging.debug("Calculate events with certain error code")
    return np.unique(event_number[event_status & select_mask == condition])


def get_scan_parameter(meta_data_array, unique=True):
    '''Takes the numpy meta data array and returns the different scan parameter settings and the name aligned in a dictionary

    Parameters
    ----------
    meta_data_array : numpy.ndarray
    unique: boolean
        If true only unique values for each scan parameter are returned

    Returns
    -------
    python.dict{string, numpy.Histogram}:
        A dictionary with the scan parameter name/values pairs
    '''

    try:
        last_not_parameter_column = meta_data_array.dtype.names.index('error_code')  # for interpreted meta_data
    except ValueError:
        last_not_parameter_column = meta_data_array.dtype.names.index('error')  # for raw data file meta_data
    if last_not_parameter_column == len(meta_data_array.dtype.names) - 1:  # no meta_data found
        return
    scan_parameters = collections.OrderedDict()
    for scan_par_name in meta_data_array.dtype.names[4:]:  # scan parameters are in columns 5 (= index 4) and above
        scan_parameters[scan_par_name] = np.unique(meta_data_array[scan_par_name]) if unique else meta_data_array[scan_par_name]
    return scan_parameters


def get_scan_parameters_table_from_meta_data(meta_data_array, scan_parameters=None):
    '''Takes the meta data array and returns the scan parameter values as a view of a numpy array only containing the parameter data .
    Parameters
    ----------
    meta_data_array : numpy.ndarray
        The array with the scan parameters.
    scan_parameters : list of strings
        The name of the scan parameters to take. If none all are used.

    Returns
    -------
    numpy.Histogram
    '''

    if scan_parameters is None:
        try:
            last_not_parameter_column = meta_data_array.dtype.names.index('error_code')  # for interpreted meta_data
        except ValueError:
            return
        if last_not_parameter_column == len(meta_data_array.dtype.names) - 1:  # no meta_data found
            return
        # http://stackoverflow.com/questions/15182381/how-to-return-a-view-of-several-columns-in-numpy-structured-array
        scan_par_data = {name: meta_data_array.dtype.fields[name] for name in meta_data_array.dtype.names[last_not_parameter_column + 1:]}
    else:
        scan_par_data = collections.OrderedDict()
        for name in scan_parameters:
            scan_par_data[name] = meta_data_array.dtype.fields[name]

    return np.ndarray(meta_data_array.shape, np.dtype(scan_par_data), meta_data_array, 0, meta_data_array.strides)


def get_scan_parameters_index(scan_parameter):
    '''Takes the scan parameter array and creates a scan parameter index labeling the unique scan parameter combinations.
    Parameters
    ----------
    scan_parameter : numpy.ndarray
        The table with the scan parameters.

    Returns
    -------
    numpy.Histogram
    '''
    _, index = np.unique(scan_parameter, return_index=True)
    index = np.sort(index)
    values = np.array(range(0, len(index)), dtype='i4')
    index = np.append(index, len(scan_parameter))
    counts = np.diff(index)
    return np.repeat(values, counts)


def get_unique_scan_parameter_combinations(meta_data_array, scan_parameters=None, scan_parameter_columns_only=False):
    '''Takes the numpy meta data array and returns the first rows with unique combinations of different scan parameter values for selected scan parameters.
        If selected columns only is true, the returned histogram only contains the selected columns.

    Parameters
    ----------
    meta_data_array : numpy.ndarray
    scan_parameters : list of string, None
        Scan parameter names taken. If None all are used.
    selected_columns_only : bool

    Returns
    -------
    numpy.Histogram
    '''

    try:
        last_not_parameter_column = meta_data_array.dtype.names.index('error_code')  # for interpreted meta_data
    except ValueError:
        last_not_parameter_column = meta_data_array.dtype.names.index('error')  # for raw data file meta_data
    if last_not_parameter_column == len(meta_data_array.dtype.names) - 1:  # no meta_data found
        return
    if scan_parameters is None:
        return unique_row(meta_data_array, use_columns=range(4, len(meta_data_array.dtype.names)), selected_columns_only=scan_parameter_columns_only)
    else:
        use_columns = []
        for scan_parameter in scan_parameters:
            try:
                use_columns.append(meta_data_array.dtype.names.index(scan_parameter))
            except ValueError:
                logging.error('No scan parameter ' + scan_parameter + ' found')
                raise RuntimeError('Scan parameter not found')
        return unique_row(meta_data_array, use_columns=use_columns, selected_columns_only=scan_parameter_columns_only)


def index_event_number(table_with_event_numer):
    if not table_with_event_numer.cols.event_number.is_indexed:  # index event_number column to speed up everything
        logging.info('Create event_number index, this takes some time')
        table_with_event_numer.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
    else:
        logging.debug('Event_number index exists already, omit creation')


def data_aligned_at_events(table, start_event_number=None, stop_event_number=None, start_index=None, stop_index=None, chunk_size=10000000, try_speedup=False, first_event_aligned=True, fail_on_missing_events=True):
    '''Takes the table with a event_number column and returns chunks with the size up to chunk_size. The chunks are chosen in a way that the events are not splitted.
    Additional parameters can be set to increase the readout speed. Events between a certain range can be selected.
    Also the start and the stop indices limiting the table size can be specified to improve performance.
    The event_number column must be sorted.
    In case of try_speedup is True, it is important to create an index of event_number column with pytables before using this function. Otherwise the queries are slowed down.

    Parameters
    ----------
    table : pytables.table
        The data.
    start_event_number : int
        The retruned data contains events with event number >= start_event_number. If None, no limit is set.
    stop_event_number : int
        The retruned data contains events with event number < stop_event_number. If None, no limit is set.
    start_index : int
        Start index of data. If None, no limit is set.
    stop_index : int
        Stop index of data. If None, no limit is set.
    chunk_size : int
        Maximum chunk size per read.
    try_speedup : bool
        If True, try to reduce the index range to read by searching for the indices of start and stop event number. If these event numbers are usually
        not in the data this speedup can even slow down the function!

    The following parameters are not used when try_speedup is True:

    first_event_aligned : bool
        If True, assuming that the first event is aligned to the data chunk and will be added. If False, the lowest event number of the first chunk will not be read out.
    fail_on_missing_events : bool
        If True, an error is given when start_event_number or stop_event_number is not part of the data.

    Returns
    -------
    Iterator of tuples
        Data of the actual data chunk and start index for the next chunk.

    Example
    -------
    start_index = 0
    for scan_parameter in scan_parameter_range:
        start_event_number, stop_event_number = event_select_function(scan_parameter)
        for data, start_index in data_aligned_at_events(table, start_event_number=start_event_number, stop_event_number=stop_event_number, start_index=start_index):
            do_something(data)

    for data, index in data_aligned_at_events(table):
        do_something(data)
    '''
    # initialize variables
    start_index_known = False
    stop_index_known = False
    start_index = 0 if start_index is None else start_index
    stop_index = table.nrows if stop_index is None else stop_index
    if stop_index < start_index:
        raise InvalidInputError('Invalid start/stop index')
    table_max_rows = table.nrows
    if stop_event_number is not None and start_event_number is not None and stop_event_number < start_event_number:
        raise InvalidInputError('Invalid start/stop event number')

    # set start stop indices from the event numbers for fast read if possible; not possible if the given event number does not exist in the data stream
    if try_speedup and table.colindexed["event_number"]:
        if start_event_number is not None:
            start_condition = 'event_number==' + str(start_event_number)
            start_indices = table.get_where_list(start_condition, start=start_index, stop=stop_index)
            if start_indices.shape[0] != 0:  # set start index if possible
                start_index = start_indices[0]
                start_index_known = True

        if stop_event_number is not None:
            stop_condition = 'event_number==' + str(stop_event_number)
            stop_indices = table.get_where_list(stop_condition, start=start_index, stop=stop_index)
            if stop_indices.shape[0] != 0:  # set the stop index if possible, stop index is excluded
                stop_index = stop_indices[0]
                stop_index_known = True

    if start_index_known and stop_index_known and start_index + chunk_size >= stop_index:  # special case, one read is enough, data not bigger than one chunk and the indices are known
        yield table.read(start=start_index, stop=stop_index), stop_index
    else:  # read data in chunks, chunks do not divide events, abort if stop_event_number is reached

        # search for begin
        current_start_index = start_index
        if start_event_number is not None:
            while current_start_index < stop_index:
                current_stop_index = min(current_start_index + chunk_size, stop_index)
                array_chunk = table.read(start=current_start_index, stop=current_stop_index)  # stop index is exclusive, so add 1
                last_event_in_chunk = array_chunk["event_number"][-1]

                if last_event_in_chunk < start_event_number:
                    current_start_index = current_start_index + chunk_size  # not there yet, continue to next read (assuming sorted events)
                else:
                    first_event_in_chunk = array_chunk["event_number"][0]
#                     if stop_event_number is not None and first_event_in_chunk >= stop_event_number and start_index != 0 and start_index == current_start_index:
#                         raise InvalidInputError('The stop event %d is missing. Change stop_event_number.' % stop_event_number)
                    if array_chunk.shape[0] == chunk_size and first_event_in_chunk == last_event_in_chunk:
                        raise InvalidInputError('Chunk size too small. Increase chunk size to fit full event.')

                    if not first_event_aligned and first_event_in_chunk == start_event_number and start_index != 0 and start_index == current_start_index:  # first event in first chunk not aligned at index 0, so take next event
                        if fail_on_missing_events:
                            raise InvalidInputError('The start event %d is missing. Change start_event_number.' % start_event_number)
                        chunk_start_index = np.searchsorted(array_chunk["event_number"], start_event_number + 1, side='left')
                    elif fail_on_missing_events and first_event_in_chunk > start_event_number and start_index == current_start_index:
                        raise InvalidInputError('The start event %d is missing. Change start_event_number.' % start_event_number)
                    elif first_event_aligned and first_event_in_chunk == start_event_number and start_index == current_start_index:
                        chunk_start_index = 0
                    else:
                        chunk_start_index = np.searchsorted(array_chunk["event_number"], start_event_number, side='left')
                        if fail_on_missing_events and array_chunk["event_number"][chunk_start_index] != start_event_number and start_index == current_start_index:
                            raise InvalidInputError('The start event %d is missing. Change start_event_number.' % start_event_number)
#                     if fail_on_missing_events and ((start_index == current_start_index and chunk_start_index == 0 and start_index != 0 and not first_event_aligned) or array_chunk["event_number"][chunk_start_index] != start_event_number):
#                         raise InvalidInputError('The start event %d is missing. Change start_event_number.' % start_event_number)
                    current_start_index = current_start_index + chunk_start_index  # calculate index for next loop
                    break
        elif not first_event_aligned and start_index != 0:
            while current_start_index < stop_index:
                current_stop_index = min(current_start_index + chunk_size, stop_index)
                array_chunk = table.read(start=current_start_index, stop=current_stop_index)  # stop index is exclusive, so add 1
                first_event_in_chunk = array_chunk["event_number"][0]
                last_event_in_chunk = array_chunk["event_number"][-1]

                if array_chunk.shape[0] == chunk_size and first_event_in_chunk == last_event_in_chunk:
                    raise InvalidInputError('Chunk size too small. Increase chunk size to fit full event.')

                chunk_start_index = np.searchsorted(array_chunk["event_number"], first_event_in_chunk + 1, side='left')
                current_start_index = current_start_index + chunk_start_index
                if not first_event_in_chunk == last_event_in_chunk:
                    break

        # data loop
        while current_start_index < stop_index:
            current_stop_index = min(current_start_index + chunk_size, stop_index)
            array_chunk = table.read(start=current_start_index, stop=current_stop_index)  # stop index is exclusive, so add 1
            first_event_in_chunk = array_chunk["event_number"][0]
            last_event_in_chunk = array_chunk["event_number"][-1]

            chunk_start_index = 0

            if stop_event_number is None:
                if current_stop_index == table_max_rows:
                    chunk_stop_index = array_chunk.shape[0]
                else:
                    chunk_stop_index = np.searchsorted(array_chunk["event_number"], last_event_in_chunk, side='left')
            else:
                if last_event_in_chunk >= stop_event_number:
                    chunk_stop_index = np.searchsorted(array_chunk["event_number"], stop_event_number, side='left')
                elif current_stop_index == table_max_rows:  # this will also add the last event of the table
                    chunk_stop_index = array_chunk.shape[0]
                else:
                    chunk_stop_index = np.searchsorted(array_chunk["event_number"], last_event_in_chunk, side='left')

            nrows = chunk_stop_index - chunk_start_index
            if nrows == 0:
                if array_chunk.shape[0] == chunk_size and first_event_in_chunk == last_event_in_chunk:
                    raise InvalidInputError('Chunk size too small to fit event. Data corruption possible. Increase chunk size to read full event.')
                elif chunk_start_index == 0:  # not increasing current_start_index
                    return
                elif stop_event_number is not None and last_event_in_chunk >= stop_event_number:
                    return
            else:
                yield array_chunk[chunk_start_index:chunk_stop_index], current_start_index + nrows + chunk_start_index

            current_start_index = current_start_index + nrows + chunk_start_index  # events fully read, increase start index and continue reading


def select_good_pixel_region(hits, col_span, row_span, min_cut_threshold=0.2, max_cut_threshold=2.0):
    '''Takes the hit array and masks all pixels with a certain occupancy.

    Parameters
    ----------
    hits : array like
        If dim > 2 the additional dimensions are summed up.
    min_cut_threshold : float
        A number to specify the minimum threshold, which pixel to take. Pixels are masked if
        occupancy < min_cut_threshold * np.ma.median(occupancy)
        0 means that no pixels are masked
    max_cut_threshold : float
        A number to specify the maximum threshold, which pixel to take. Pixels are masked if
        occupancy > max_cut_threshold * np.ma.median(occupancy)
        Can be set to None that no pixels are masked by max_cut_threshold

    Returns
    -------
    numpy.ma.array, shape=(80,336)
        The hits array with masked pixels.
    '''
    hits = np.sum(hits, axis=(-1)).astype('u8')
    mask = np.ones(shape=(80, 336), dtype=np.uint8)

    mask[min(col_span):max(col_span) + 1, min(row_span):max(row_span) + 1] = 0

    ma = np.ma.masked_where(mask, hits)
    if max_cut_threshold is not None:
        return np.ma.masked_where(np.logical_or(ma < min_cut_threshold * np.ma.median(ma), ma > max_cut_threshold * np.ma.median(ma)), ma)
    else:
        return np.ma.masked_where(ma < min_cut_threshold * np.ma.median(ma), ma)


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
    logging.info('Calculate the correction factor for the single hit cluster rate at %d given GDAC settings', len(gdacs))
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
    interpolation = interp1d(mean_threshold_calibration['parameter_value'], mean_threshold_calibration['mean_threshold'], kind='slinear', bounds_error=True)
    return interpolation(gdac)


def get_pixel_thresholds_from_calibration_array(gdacs, calibration_gdacs, threshold_calibration_array, bounds_error=True):
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
    interpolation = interp1d(x=calibration_gdacs, y=threshold_calibration_array, kind='slinear', bounds_error=bounds_error)
    return interpolation(gdacs)


class ETA(progressbar.Timer):

    'Widget which estimate the time of arrival for the progress bar via exponential moving average.'
    TIME_SENSITIVE = True

    def __init__(self, smoothing=0.1):
        self.speed_smooth = None
        self.SMOOTHING = smoothing
        self.old_eta = None
        self.n_refresh = 0

    def update(self, pbar):
        'Updates the widget to show the ETA or total time when finished.'
        self.n_refresh += 1
        if pbar.currval == 0:
            return 'ETA:  --:--:--'
        elif pbar.finished:
            return 'Time: %s' % self.format_time(pbar.seconds_elapsed)
        else:
            elapsed = pbar.seconds_elapsed
            try:
                speed = pbar.currval / elapsed
                if self.speed_smooth is not None:
                    self.speed_smooth = (self.speed_smooth * (1 - self.SMOOTHING)) + (speed * self.SMOOTHING)
                else:
                    self.speed_smooth = speed
                eta = float(pbar.maxval) / self.speed_smooth - elapsed + 1 if float(pbar.maxval) / self.speed_smooth - elapsed + 1 > 0 else 0

                if float(pbar.currval) / pbar.maxval > 0.30 or self.n_refresh > 10:  # ETA only rather precise if > 30% is already finished or more than 10 times updated
                    return 'ETA:  %s' % self.format_time(eta)
                if self.old_eta is not None and self.old_eta < eta:  # do not show jumping ETA if non precise mode is active
                    return 'ETA: ~%s' % self.format_time(self.old_eta)
                else:
                    self.old_eta = eta
                    return 'ETA: ~%s' % self.format_time(eta)
            except ZeroDivisionError:
                speed = 0


# old, maybe not needed functions
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
    cluster_in_events = analysis_utils.get_n_cluster_in_events(cluster_table)[:, 1]  # get the number of cluster for every event
    return np.histogram(cluster_in_events, bins=range(0, np.max(cluster_in_events) + 2))  # histogram the occurrence of n cluster per event


def get_data_statistics(interpreted_files):
    '''Quick and dirty function to give as redmine compatible iverview table
    '''
    print('| *File Name* | *File Size* | *Times Stamp* | *Events* | *Bad Events* | *Measurement time* | *# SR* | *Hits* |')  # Mean ToT | Mean rel. BCID'
    for interpreted_file in interpreted_files:
        with tb.open_file(interpreted_file, mode="r") as in_file_h5:  # open the actual hit file
            n_hits = np.sum(in_file_h5.root.HistOcc[:])
            measurement_time = int(in_file_h5.root.meta_data[-1]['timestamp_stop'] - in_file_h5.root.meta_data[0]['timestamp_start'])
#             mean_tot = np.average(in_file_h5.root.HistTot[:], weights=range(0,16) * np.sum(range(0,16)))# / in_file_h5.root.HistTot[:].shape[0]
#             mean_bcid = np.average(in_file_h5.root.HistRelBcid[:], weights=range(0,16))
            n_sr = np.sum(in_file_h5.root.HistServiceRecord[:])
            n_bad_events = int(np.sum(in_file_h5.root.HistEventStatusCounter[2:]))
            try:
                n_events = str(in_file_h5.root.Hits[-1]['event_number'] + 1)
            except tb.NoSuchNodeError:
                n_events = '~' + str(in_file_h5.root.meta_data[-1]['event_number'] + (in_file_h5.root.meta_data[-1]['event_number'] - in_file_h5.root.meta_data[-2]['event_number']))
            else:
                print('| {} | {}Mb | {} | {} | {} | {}s | {} | {} |'.format(os.path.basename(interpreted_file), int(os.path.getsize(interpreted_file) / (1024.0 * 1024.0)), time.ctime(os.path.getctime(interpreted_file)), n_events, n_bad_events, measurement_time, n_sr, n_hits))  # , mean_tot, mean_bcid, '|'


def fix_raw_data(raw_data, lsb_byte=None):
    if not lsb_byte:
        lsb_byte = np.right_shift(raw_data[0], 24)
        raw_data = raw_data[1:]

    for i in range(raw_data.shape[0]):
        msb_bytes = np.left_shift(raw_data[i], 8)
        new_word = np.bitwise_or(msb_bytes, lsb_byte)
        lsb_byte = np.right_shift(raw_data[i], 24)
        raw_data[i] = new_word
    return raw_data, lsb_byte


def contiguous_regions(condition):
    """Finds contiguous True regions of the boolean array "condition". Returns
    a 2D array where the first column is the start index of the region and the
    second column is the end index.
    http://stackoverflow.com/questions/4494404/find-large-number-of-consecutive-values-fulfilling-condition-in-a-numpy-array
    """
    # Find the indicies of changes in "condition"
    d = np.diff(condition, n=1)
    idx, = d.nonzero()

    # We need to start things after the change in "condition". Therefore,
    # we'll shift the index by 1 to the right.
    idx += 1

    if condition[0]:
        # If the start of condition is True prepend a 0
        idx = np.r_[0, idx]

    if condition[-1]:
        # If the end of condition is True, append the length of the array
        idx = np.r_[idx, condition.size]

    # Reshape the result into two columns
    idx.shape = (-1, 2)
    return idx


def check_bad_data(raw_data, prepend_data_headers=None, trig_count=None):
    """Checking FEI4 raw data array for corrupted data.
    """
    consecutive_triggers = 16 if trig_count == 0 else trig_count
    is_fe_data_header = logical_and(is_fe_word, is_data_header)
    trigger_idx = np.where(is_trigger_word(raw_data) >= 1)[0]
    fe_dh_idx = np.where(is_fe_data_header(raw_data) >= 1)[0]
    n_triggers = trigger_idx.shape[0]
    n_dh = fe_dh_idx.shape[0]

    # get index of the last trigger
    if n_triggers:
        last_event_data_headers_cnt = np.where(fe_dh_idx > trigger_idx[-1])[0].shape[0]
        if consecutive_triggers and last_event_data_headers_cnt == consecutive_triggers:
            if not np.all(trigger_idx[-1] > fe_dh_idx):
                trigger_idx = np.r_[trigger_idx, raw_data.shape]
            last_event_data_headers_cnt = None
        elif last_event_data_headers_cnt != 0:
            fe_dh_idx = fe_dh_idx[:-last_event_data_headers_cnt]
        elif not np.all(trigger_idx[-1] > fe_dh_idx):
            trigger_idx = np.r_[trigger_idx, raw_data.shape]
    # if any data header, add trigger for histogramming, next readout has to have trigger word
    elif n_dh:
        trigger_idx = np.r_[trigger_idx, raw_data.shape]
        last_event_data_headers_cnt = None
    # no trigger, no data header
    # assuming correct data, return input values
    else:
        return False, prepend_data_headers, n_triggers, n_dh

#     # no triggers, check for the right amount of data headers
#     if consecutive_triggers and prepend_data_headers and prepend_data_headers + n_dh != consecutive_triggers:
#         return True, n_dh, n_triggers, n_dh

    n_triggers_cleaned = trigger_idx.shape[0]
    n_dh_cleaned = fe_dh_idx.shape[0]

    # check that trigger comes before data header
    if prepend_data_headers is None and n_triggers_cleaned and n_dh_cleaned and not trigger_idx[0] < fe_dh_idx[0]:
        return True, last_event_data_headers_cnt, n_triggers, n_dh  # FIXME: 0?
    # check that no trigger comes before the first data header
    elif consecutive_triggers and prepend_data_headers is not None and n_triggers_cleaned and n_dh_cleaned and trigger_idx[0] < fe_dh_idx[0]:
        return True, last_event_data_headers_cnt, n_triggers, n_dh  # FIXME: 0?
    # check for two consecutive triggers
    elif consecutive_triggers is None and prepend_data_headers == 0 and n_triggers_cleaned and n_dh_cleaned and trigger_idx[0] < fe_dh_idx[0]:
        return True, last_event_data_headers_cnt, n_triggers, n_dh  # FIXME: 0?
    elif prepend_data_headers is not None:
        trigger_idx += (prepend_data_headers + 1)
        fe_dh_idx += (prepend_data_headers + 1)
        # for histogramming add trigger at index 0
        trigger_idx = np.r_[0, trigger_idx]
        fe_dh_idx = np.r_[range(1, prepend_data_headers + 1), fe_dh_idx]

    event_hist, bins = np.histogram(fe_dh_idx, trigger_idx)
    if consecutive_triggers is None and np.any(event_hist == 0):
        return True, last_event_data_headers_cnt, n_triggers, n_dh
    elif consecutive_triggers and np.any(event_hist != consecutive_triggers):
        return True, last_event_data_headers_cnt, n_triggers, n_dh

    return False, last_event_data_headers_cnt, n_triggers, n_dh


def consecutive(data, stepsize=1):
    """Converts array into chunks with consecutive elements of given step size.
    http://stackoverflow.com/questions/7352684/how-to-find-the-groups-of-consecutive-elements-from-an-array-in-numpy
    """
    return np.split(data, np.where(np.diff(data) != stepsize)[0] + 1)


def print_raw_data_file(input_file, start_index=0, limit=200, flavor='fei4b', select=None, tdc_trig_dist=False, trigger_data_mode=0, meta_data_v2=True):
    """Printing FEI4 data from raw data file for debugging.
    """
    with tb.open_file(input_file + '.h5', mode="r") as file_h5:
        if meta_data_v2:
            index_start = file_h5.root.meta_data.read(field='index_start')
            index_stop = file_h5.root.meta_data.read(field='index_stop')
        else:
            index_start = file_h5.root.meta_data.read(field='start_index')
            index_stop = file_h5.root.meta_data.read(field='stop_index')
        total_words = 0
        for read_out_index, (index_start, index_stop) in enumerate(np.column_stack((index_start, index_stop))):
            if start_index < index_stop:
                print("\nchunk %d with length %d (from index %d to %d)\n" % (read_out_index, (index_stop - index_start), index_start, index_stop))
                raw_data = file_h5.root.raw_data.read(index_start, index_stop)
                total_words += print_raw_data(raw_data=raw_data, start_index=max(start_index - index_start, 0), limit=limit - total_words, flavor=flavor, index_offset=index_start, select=select, tdc_trig_dist=tdc_trig_dist, trigger_data_mode=trigger_data_mode)
                if limit and total_words >= limit:
                    break


def print_raw_data(raw_data, start_index=0, limit=200, flavor='fei4b', index_offset=0, select=None, tdc_trig_dist=False, trigger_data_mode=0):
    """Printing FEI4 raw data array for debugging.
    """
    if not select:
        select = ['DH', 'TW', "AR", "VR", "SR", "DR", 'TDC', 'UNKNOWN FE WORD', 'UNKNOWN WORD']
    total_words = 0
    for index in range(start_index, raw_data.shape[0]):
        dw = FEI4Record(raw_data[index], chip_flavor=flavor, tdc_trig_dist=tdc_trig_dist, trigger_data_mode=trigger_data_mode)
        if dw in select:
            print('{}: {0:12d} {1:08b} {2:08b} {3:08b} {4:08b}'.format(index + index_offset, raw_data[index], (raw_data[index] & 0xFF000000) >> 24, (raw_data[index] & 0x00FF0000) >> 16, (raw_data[index] & 0x0000FF00) >> 8, (raw_data[index] & 0x000000FF) >> 0), dw)
            total_words += 1
            if limit and total_words >= limit:
                break
    return total_words


if __name__ == "__main__":
    pass
