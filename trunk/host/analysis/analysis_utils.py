"""This class provides often needed analysis functions, for analysis that is done with python.
"""

import logging
import re
import os
import time
import collections
import numpy as np
import progressbar
import glob
import tables as tb
import numexpr as ne
from plotting import plotting
from scipy.interpolate import interp1d
from operator import itemgetter
from scipy.interpolate import splrep, splev
from RawDataConverter import analysis_functions

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def get_data_statistics(interpreted_files):
    '''Quick and dirty function to give as redmine compatible iverview table
    '''
    print '| *File Name* | *File Size* | *Times Stamp* | *Events* | *Bad Events* | *Measurement time* | *# SR* | *Hits* |'  # Mean Tot | Mean rel. BCID'
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
#             if int(n_events) < 7800000 or n_sr > 4200 or n_bad_events > 40:
#                 print '| %{color:red}', os.path.basename(interpreted_file) + '%', '|', int(os.path.getsize(interpreted_file) / (1024 * 1024.)), 'Mb |', time.ctime(os.path.getctime(interpreted_file)), '|',  n_events, '|', n_bad_events, '|', measurement_time, 's |', n_sr, '|', n_hits, '|'#, mean_tot, '|', mean_bcid, '|'
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


def get_rate_normalization(hit_file, parameter, reference='event', cluster_file=None, sort=False, plot=False, chunk_size=5000000):
    ''' Takes different hit files (hit_files), extracts the number of events or the scan time (reference) per scan parameter (parameter)
    and returns an array with a normalization factor. This normalization factor has the length of the number of different parameters.
    One can also sort the normalization by the parameter values.
    If a cluster_file is specified.

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
    with tb.openFile(hit_file, mode="r+") as in_hit_file_h5:  # open the hit file
        meta_data = in_hit_file_h5.root.meta_data[:]
        scan_parameter = get_scan_parameter(meta_data)[parameter]
        event_numbers = get_meta_data_at_scan_parameter(meta_data, parameter)['event_number']  # get the event numbers in meta_data where the scan parameter changes
        event_range = get_ranges_from_array(event_numbers)
        normalization_rate = []
        normalization_multiplicity = []
        try:
            event_range[-1, 1] = in_hit_file_h5.root.Hits[-1]['event_number']
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

        if cluster_file:
            # calculate the rate normalization from the mean number of hits per event per scan parameter, needed for beam data since a beam since the multiplicity is rarely constant
            cluster_table = in_hit_file_h5.root.Cluster
            index_event_number(cluster_table)
            index = 0  # index where to start the read out, 0 at the beginning, increased during looping, variable for read speed up
            best_chunk_size = chunk_size  # variable for read speed up
            total_cluster = 0
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA(smoothing=0.8)], maxval=cluster_table.shape[0])
            progress_bar.start()
            for start_event, stop_event in event_range:  # loop over the selected events
                readout_cluster_len = 0  # variable to calculate a optimal chunk size value from the number of hits for speed up
                n_cluster_per_event = None
                for clusters, index in data_aligned_at_events(cluster_table, start_event_number=start_event, stop_event_number=stop_event, start=index, chunk_size=best_chunk_size):
                    if n_cluster_per_event is None:
                        n_cluster_per_event = get_n_cluster_in_events(clusters['event_number'])[:, 1]  # array with the number of cluster per event, cluster per event are at least 1
                    else:
                        n_cluster_per_event = np.append(n_cluster_per_event, get_n_cluster_in_events(clusters['event_number'])[:, 1])
                    readout_cluster_len += clusters.shape[0]
                    total_cluster += len(clusters)
                    progress_bar.update(index)
                best_chunk_size = int(1.5 * readout_cluster_len) if int(1.05 * readout_cluster_len) < chunk_size else chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                normalization_multiplicity.append(np.mean(n_cluster_per_event))
            progress_bar.finish()
            if total_cluster != cluster_table.shape[0]:
                logging.warning('Analysis shows inconsistent number of cluster. Check needed!')

    if plot:
        x = scan_parameter
        if reference == 'event':
            plotting.plot_scatter(x, normalization_rate, title='Events per ' + parameter + ' setting', x_label=parameter, y_label='# events', log_x=True)
        elif reference == 'time':
            plotting.plot_scatter(x, normalization_rate, title='Measuring time per GDAC setting', x_label=parameter, y_label='time [s]', log_x=True)
        if cluster_file:
            plotting.plot_scatter(x, normalization_multiplicity, title='Mean number of hits per event', x_label=parameter, y_label='number of hits per event', log_x=True)
    print len(normalization_rate), len(normalization_multiplicity)
    if cluster_file:
        normalization_rate = np.array(normalization_rate)
        normalization_multiplicity = np.array(normalization_multiplicity)
        return np.amax(normalization_rate * normalization_multiplicity).astype('f16') / (normalization_rate * normalization_multiplicity)
    return np.amax(np.array(normalization_rate)).astype('f16') / np.array(normalization_rate)


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


def get_total_n_data_words(files_dict, precise=False):
    n_words = 0
    if precise:  # open all files and determine the total number of words precicely, can take some time
        if len(files_dict) > 10:
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA()], maxval=len(files_dict))
            progress_bar.start()
        for index, file_name in enumerate(files_dict.iterkeys()):
            with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual file
                n_words += in_file_h5.root.raw_data.shape[0]
            if len(files_dict) > 10:
                progress_bar.update(index)
        if len(files_dict) > 10:
            progress_bar.finish()
        return n_words
    else:  # open just first an last file and take the mean to estimate the total numbe rof words
        with tb.openFile(files_dict.keys()[0], mode="r") as in_file_h5:  # open the actual file
            n_words += in_file_h5.root.raw_data.shape[0]
        with tb.openFile(files_dict.keys()[-1], mode="r") as in_file_h5:  # open the actual file
            n_words += in_file_h5.root.raw_data.shape[0]
        return n_words * len(files_dict) / 2


def create_parameter_table(files_dict):
    if not check_parameter_similarity(files_dict):
        raise RuntimeError('Cannot create table from file with different scan parameters.')
    # create the parameter names / format for the parameter table
    try:
        names = ','.join([name for name in files_dict.itervalues().next().keys()])
        formats = ','.join(['uint32' for name in files_dict.itervalues().next().keys()])
        arrayList = [l for l in files_dict.itervalues().next().values()]
    except AttributeError:  # no parameters given, return None
        return
    parameter_table = None
    # create a parameter list for every read out
    for file_name, parameters in files_dict.iteritems():
        with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual file
            n_parameter_settings = len(files_dict[file_name].values()[0])  # determine the number of different parameter settings from the list length of parameter values of the first parameter
            if n_parameter_settings == 1:  # only one parameter setting used, therefore create a temporary parameter table with these parameter setting and append it to the final parameter table
                read_out = in_file_h5.root.meta_data.shape[0]
                if parameter_table is None:  # final parameter_table does not exists, so create is
                    parameter_table = np.rec.fromarrays(arrayList, names=names, formats=formats)  # create recarray
                    parameter_table.resize(read_out)
                    parameter_table[-read_out:] = np.rec.fromarrays(arrayList, names=names, formats=formats)
                else:  # final parameter table already exist, so append to existing
                    parameter_table.resize(parameter_table.shape[0] + read_out)  # fastest way to append, http://stackoverflow.com/questions/1730080/append-rows-to-a-numpy-record-array
                    parameter_table[-read_out:] = np.rec.fromarrays([l for l in parameters.values()], names=names, formats=formats)
            else:  # more than one parameter setting used, therefore the info has to be taken from the parameter table in the file. Append this table to the final parameter_table
                if parameter_table is None:  # final parameter_table does not exists, so create is
                    parameter_table = in_file_h5.root.scan_parameters[:]
                else:  # final parameter table already exist, so append to existing
                    parameter_table.resize(parameter_table.shape[0] + in_file_h5.root.scan_parameters.shape[0])  # fastest way to append, http://stackoverflow.com/questions/1730080/append-rows-to-a-numpy-record-array
                    parameter_table[-in_file_h5.root.scan_parameters.shape[0]:] = in_file_h5.root.scan_parameters[:]  # set table
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
        search_string += r'_(\d+)'
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


def get_data_file_names_from_scan_base(scan_base, filter_file_words=None, parameter=False):
    """
    Takes a list of scan base names and returns all file names that have this scan base within their name. File names that have a word of filter_file_words
    in their name are excluded.

    Parameters
    ----------
    scan_base : list of strings
    filter_file_words : list of strings
        Return only file names without a filter_file_word. Deactivate feature by setting filter_file_words to None.
    Returns
    -------
    list of strings

    """
    raw_data_files = []
    if isinstance(scan_base, basestring):
        scan_base = (scan_base, )
    for scan_name in scan_base:
        if parameter:
            data_files = glob.glob(scan_name + '_*.h5')
        else:
            data_files = glob.glob(scan_name + '*.h5')
        if not data_files:
            raise RuntimeError('Cannot find any data files, please check data file names.')
        if filter_file_words is not None:
            raw_data_files.extend(filter(lambda data_file: not any(x in data_file for x in filter_file_words), data_files))  # filter out already analyzed data
        else:
            raw_data_files = data_files
    return raw_data_files


def get_parameter_scan_bases_from_scan_base(scan_base):
    """ Takes a list of scan base names and returns all scan base names that have this scan base within their name.

    Parameters
    ----------
    scan_base : list of strings
    filter_file_words : list of strings

    Returns
    -------
    list of strings

    """
    return [scan_bases[:-3] for scan_bases in get_data_file_names_from_scan_base(scan_base, filter_file_words=['interpreted', 'cut_', 'cluster_sizes', 'histograms'])]


def get_scan_parameter_names(scan_parameters):
    ''' Returns the scan parameter names of the scan_paraemeter table.

    Parameters
    ----------
    scan_parameters : numpy.array

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
        with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual file
            scan_parameter_values = {}
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
                        if value[0] != parameter_values_from_file_names_dict[file_name][key][0]:
                            logging.warning('Parameter values in the file name and in the file differ. Take ' + str(key) + ' parameters ' + str(value) + ' found in %s.' % file_name)
                except KeyError:  # parameter does not exists in the file name
                    pass
            if unique:
                existing = False
                for parameter in scan_parameter_values:  # loop to determine if any value of any scan parameter exists already
                    all_par_values = [values[parameter] for values in files_dict.values()]
                    if any(x in [scan_parameter_values[parameter]] for x in all_par_values):
                        existing = True
                        break
                if not existing:
                    files_dict[file_name] = scan_parameter_values
                else:
                    logging.warning('Scan parameter value(s) from %s exists already, do not add to result' % file_name)
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


def combine_meta_data(files_dict):
    """
    Takes the dict of hdf5 files and combines their meta data tables into one new numpy record array.

    """
    if len(files_dict) > 10:
        logging.info("Combine the meta data from %d files" % len(files_dict))
    # determine total length needed for the new combined array, thats the fastest way to combine arrays
    total_length = 0  # the total length of the new table
    meta_data_v2 = True
    for file_name in files_dict.iterkeys():
        with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual file
            total_length += in_file_h5.root.meta_data.shape[0]
            try:
                in_file_h5.root.meta_data[0]['timestamp_stop']  # this only exists in the new data format, https://silab-redmine.physik.uni-bonn.de/news/7
            except KeyError:
                meta_data_v2 = False
            except IndexError:
                return None

    if meta_data_v2:
        meta_data_combined = np.empty((total_length, ), dtype=[('index_start', np.uint32),
             ('index_stop', np.uint32),
             ('data_length', np.uint32),
             ('timestamp_start', np.float64),
             ('timestamp_stop', np.float64),
             ('error', np.uint32)
             ])
    else:
        meta_data_combined = np.empty((total_length, ), dtype=[('index_start', np.uint32),
             ('index_stop', np.uint32),
             ('data_length', np.uint32),
             ('timestamp', np.float64),
             ('error', np.uint32)
             ])

    if len(files_dict) > 10:
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA()], maxval=total_length)
        progress_bar.start()

    index = 0

    # fill actual result array
    for file_name in files_dict.iterkeys():
        with tb.openFile(file_name, mode="r") as in_file_h5:  # open the actual file
            array_length = in_file_h5.root.meta_data.shape[0]
            meta_data_combined[index:index + array_length] = in_file_h5.root.meta_data[:]
            index += array_length
            if len(files_dict) > 10:
                progress_bar.update(index)
    if len(files_dict) > 10:
        progress_bar.finish()
    return meta_data_combined


def in1d_sorted(ar1, ar2):
    """
    Does the same than np.in1d but uses the fact that ar1 and ar2 are sorted. Is therefore much faster.

    """
    if ar1.shape[0] == 0 or ar2.shape[0] == 0:  # check for empty arrays to avoid crash
        return []
    inds = ar2.searchsorted(ar1)
    inds[inds == len(ar2)] = 0
    return ar2[inds] == ar1


def in1d_events(ar1, ar2):
    """
    Does the same than np.in1d but uses the fact that ar1 and ar2 are sorted and the c++ library. Is therefore much much faster.

    """
    ar1 = np.ascontiguousarray(ar1)  # change memory alignement for c++ library
    ar2 = np.ascontiguousarray(ar2)  # change memory alignement for c++ library
    tmp = np.empty_like(ar1, dtype=np.uint8)  # temporary result array filled by c++ library, bool type is not supported with cython/numpy
    return analysis_functions.get_in1d_sorted(ar1, ar2, tmp)


def get_events_in_both_arrays(events_one, events_two):
    """
    Calculates the events that exist in both arrays.

    """
    events_one = np.ascontiguousarray(events_one)  # change memory alignement for c++ library
    events_two = np.ascontiguousarray(events_two)  # change memory alignement for c++ library
    event_result = np.empty_like(events_one)
    count = analysis_functions.get_events_in_both_arrays(events_one, events_two, event_result)
    return event_result[:count]


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


def get_hits_in_events(hits_array, events, assume_sorted=True, condition=None):
    '''Selects the hits that occurred in events. If a event range can be defined use the get_data_in_event_range function. It is much faster.

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
            selection = in1d_events(hits_array['event_number'], events)
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
        if (event_start != None and event_stop != None) and (data_event_stop < event_start or data_event_start > event_stop or event_start == event_stop):  # special case, no intersection at all
            return array[0:0]

        # get min/max indices with values that are also in the other array
        if event_start == None:
            min_index_data = 0
        else:
            min_index_data = np.argmin(event_number < event_start)

        if event_stop == None:
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
        if not condition is None:
            # bad hack to be able to use numexpr
            for variable in set(re.findall(r'[a-zA-Z_]+', condition)):
                exec(variable + ' = hits[\'' + variable + '\']')
            selected_hits = selected_hits[ne.evaluate(condition)]
        hit_table_out.append(selected_hits)
        if last_event_number > event_stop:  # speed up, use the fact that the hits are sorted by event_number
            return iHit + chunk_size
    return start_hit_word


def get_mean_from_histogram(counts, bin_positions):
    return np.dot(counts, np.array(bin_positions)) / np.sum(counts).astype('f4')


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

    logging.debug("Calculate events with clusters where " + condition)
    n_cluster_in_events = get_n_cluster_in_events(event_number)
    n_cluster = n_cluster_in_events[:, 1]
#     return np.take(n_cluster_in_events, ne.evaluate(condition), axis=0)  # does not return only one dimension, Bug?
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


def get_n_cluster_in_events(event_numbers):
    '''Calculates the number of cluster in every given event. 
    An external C++ library is used since there is no sufficient solution in python possible.
    Because of np.bincount # BUG #225 for values > int32 and the different handling under 32/64 bit operating systems.

    Parameters
    ----------
    event_numbers : numpy.array
        List of event numbers to be checked.

    Returns
    -------
    numpy.array
        First dimension is the event number.
        Second dimension is the number of cluster of the event.
    '''
    logging.debug("Calculate the number of cluster in every given event")
    event_numbers = np.ascontiguousarray(event_numbers)  # change memory alignement for c++ library
    result_event_numbers = np.empty_like(event_numbers)
    result_count = np.empty_like(event_numbers, dtype=np.uint32)
    result_size = analysis_functions.get_n_cluster_in_events(event_numbers, result_event_numbers, result_count)
    return np.vstack((result_event_numbers[:result_size], result_count[:result_size])).T

# old python solution
#     if (sys.maxint < 3000000000):  # on 32- bit operation systems max int is 2147483647 leading to numpy bugs that need workarounds
#         event_number_array = event_numbers.astype('<i4')  # BUG in numpy, unint works with 64-bit, 32 bit needs reinterpretation
#         event_number_array = event_numbers
#         offset = np.amin(event_numbers)
#         event_numbers = np.subtract(event_numbers, offset)  # BUG #225 for values > int32
#         cluster_in_event = np.bincount(event_numbers)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
#         selected_event_number_index = np.nonzero(cluster_in_event)[0]
#         selected_event_number = np.add(selected_event_number_index, offset)
#         return np.vstack((selected_event_number, cluster_in_event[selected_event_number_index])).T
#     else:
#         cluster_in_event = np.bincount(event_numbers)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
#         selected_event_number = np.nonzero(cluster_in_event)[0]
#         return np.vstack((selected_event_number, cluster_in_event[selected_event_number])).T


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
    occupancy = np.histogram2d(x=array[labels[0]], y=array[labels[1]], bins=(80, 336), range=[[0, 80], [0, 336]])
    if mask_no_hit:
        return np.ma.array(occupancy[0], mask=(occupancy[0] == 0)), occupancy[1], occupancy[2]
    else:
        return occupancy


def get_scan_parameter(meta_data_array, unique=True):
    '''Takes the numpy meta data array and returns the different scan parameter settings and the name aligned in a dictionary

    Parameters
    ----------
    meta_data_array : numpy.ndarray
    unique: boolean
        If true only unique values for each scan parameter are returned

    Returns
    -------
    python.dict{string, numpy.Histogram}
    '''

    try:
        last_not_parameter_column = meta_data_array.dtype.names.index('error_code')  # for interpreted meta_data
    except ValueError:
        last_not_parameter_column = meta_data_array.dtype.names.index('error')  # for raw data file meta_data
    if last_not_parameter_column == len(meta_data_array.dtype.names) - 1:  # no meta_data found
        return
    scan_parameters = {}
    for scan_par_name in meta_data_array.dtype.names[4:]:  # scan parameters are in columns 5 (= index 4) and above
        scan_parameters[scan_par_name] = np.unique(meta_data_array[scan_par_name]) if unique else meta_data_array[scan_par_name]
    return scan_parameters


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
    values = np.array(range(0, len(index)), dtype='u4')
    index = np.append(index, len(scan_parameter))
    counts = np.diff(index)
    return np.repeat(values, counts)


def get_scan_parameters_table_from_meta_data(meta_data_array):
    '''Takes the meta data array and creates a scan parameter index labeling the unique scan parameter combinations.
    Parameters
    ----------
    scan_parameter : numpy.ndarray
        The table with the scan parameters.

    Returns
    -------
    numpy.Histogram
    '''

    try:
        last_not_parameter_column = meta_data_array.dtype.names.index('error_code')  # for interpreted meta_data
    except ValueError:
        return
    if last_not_parameter_column == len(meta_data_array.dtype.names) - 1:  # no meta_data found
        return

    # http://stackoverflow.com/questions/15182381/how-to-return-a-view-of-several-columns-in-numpy-structured-array
    dtype2 = np.dtype({name: meta_data_array.dtype.fields[name] for name in meta_data_array.dtype.names[last_not_parameter_column + 1:]})
    return np.ndarray(meta_data_array.shape, dtype2, meta_data_array, 0, meta_data_array.strides)


def get_unique_scan_parameter_combinations(meta_data_array, scan_parameter_columns_only=False):
    '''Takes the numpy meta data array and returns the rows with unique combinations of different scan parameter values for all scan parameters.
        If selected columns only is true, the returned histogram only contains the selected columns.

    Parameters
    ----------
    meta_data_array : numpy.ndarray

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
    return unique_row(meta_data_array, use_columns=range(4, len(meta_data_array.dtype.names)), selected_columns_only=scan_parameter_columns_only)


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


def get_ranges_from_array(array, append_last=True):
    '''Takes an array and calculates ranges [start event, stop event[. The last range end is none to keep the same length.

    Parameters
    ----------
    events : array like
    append_last: bool
        If false the returned array has one entry less

    Returns
    -------
    numpy.array
    '''
    left = array[:len(array)]
    right = array[1:len(array)]
    if append_last:
        right = np.append(right, None)
    return np.column_stack((left, right))


def index_event_number(table_with_event_numer):
    if not table_with_event_numer.cols.event_number.is_indexed:  # index event_number column to speed up everything
        logging.info('Create event_number index, this takes some time')
        table_with_event_numer.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
    else:
        logging.debug('Event_number index exists already, omit creation')


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

    if stop_event_number != None:
        condition_2 = 'event_number==' + str(stop_event_number)
        stop_indeces = table.get_where_list(condition_2)
        if len(stop_indeces) != 0:  # set the stop index if possible, stop index is excluded
            stop_index = stop_indeces[0]
            stop_index_known = True

    if (start_index_known and stop_index_known) and (start_index + chunk_size >= stop_index):  # special case, one read is enough, data not bigger than one chunk and the indices are known
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
                if start_index + chunk_size > stop_index:  # special case for the last chunk read, there read the table until its end
                    nrows = src_array.shape[0]
                else:
                    nrows = last_event_start_index

            if (start_event_number != None or stop_event_number != None) and (last_event > stop_event_number or first_event < start_event_number):  # too many events read, get only the selected ones if specified
                selected_rows = get_data_in_event_range(src_array[0:nrows], event_start=start_event_number, event_stop=stop_event_number, assume_sorted=True)
                if len(selected_rows) != 0:  # only return non empty data
                    yield selected_rows, start_index + len(selected_rows)
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


if __name__ == "__main__":
    print 'Run analysis_utils as main'
