import numpy as np
import tables as tb
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from analysis.plotting import plotting
from analysis import analysis_utils
from analysis.RawDataConverter import data_struct
from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def get_mean_threshold(gdac, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['gdac'], mean_threshold_calibration['mean_threshold'], kind='slinear', bounds_error=True)
    return interpolation(gdac)


def get_pixel_thresholds_from_table(column, row, gdacs, threshold_calibration_table):
    pixel_gdacs = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['gdac']
    pixel_thresholds = threshold_calibration_table[np.logical_and(threshold_calibration_table['column'] == column, threshold_calibration_table['row'] == row)]['threshold']
    interpolation = interp1d(x=pixel_gdacs, y=pixel_thresholds, kind='slinear', bounds_error=True)
    return interpolation(gdacs)


def get_pixel_thresholds(gdacs, calibration_gdacs, threshold_calibration_array):
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
    hist_sum = np.sum(cluster_size_histogram, axis=1)
    hist_rel = cluster_size_histogram / hist_sum[:, np.newaxis] * 100
    maximum_rate = np.amax(hist_rel[:, 1])
    correction_factor = maximum_rate / hist_rel[:, 1]
    interpolation = interp1d(calibration_gdacs, correction_factor, kind='cubic', bounds_error=True)
    return interpolation(gdacs)


def get_normalization(meta_data, reference='event', plot=False):
    gdacs = analysis_utils.get_scan_parameter(meta_data_array=meta_data)['GDAC']
    if reference == 'event':
        event_numbers = analysis_utils.get_meta_data_at_scan_parameter(meta_data, 'GDAC')['event_number']  # get the event numbers in meta_data where the scan parameter changes
        event_range = analysis_utils.get_event_range(event_numbers)
        event_range[-1, 1] = event_range[-2, 1]  # hack the last event range not to be None
        n_events = event_range[:, 1] - event_range[:, 0]  # number of events for every GDAC
        n_events[-1] = n_events[-2]  # FIXME: set the last number of events manually, bad extrapolaton
        logging.warning('Last number of events unknown and extrapolated')
        if plot:
            plotting.plot_scatter(gdacs, n_events, title='Events per GDAC setting', x_label='GDAC', y_label='# events', log_x=True)
        return n_events.astype('f64') / np.amax(n_events)
    else:
        time_start = analysis_utils.get_meta_data_at_scan_parameter(meta_data, 'GDAC')['timestamp_start']
        time_spend = np.diff(time_start)
        time_spend = np.append(time_spend, meta_data[-1]['timestamp_stop'] - time_start[-1])  # TODO: needs check, add last missing entry
        if plot:
            plotting.plot_scatter(gdacs, time_spend, title='Measuring time per GDAC setting', x_label='GDAC', y_label='time [s]', log_x=True)
        return time_spend.astype('f64') / np.amax(time_spend)


def plot_cluster_sizes(in_file_cluster_h5, in_file_calibration_h5, gdac_range, vcal_calibration):
    mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
    hist = in_file_cluster_h5.root.AllHistClusterSize[:]
    hist_sum = np.sum(hist, axis=1)
    hist_rel = hist / hist_sum[:, np.newaxis] * 100
    x = get_mean_threshold(gdac_range, mean_threshold_calibration)
    plt.grid(True)
    plt.plot(x * vcal_calibration, hist_rel[:, 1], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 2], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 3], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 4], '-o')
    plt.plot(x * vcal_calibration, hist_rel[:, 5], '-o')
    plt.title('Frequency of different cluster sizes for different thresholds')
    plt.xlabel('threshold [e]')
    plt.ylabel('cluster size frequency [%]')
    plt.legend(["1 hit cluster", "2 hit cluster", "3 hit cluster", "4 hit cluster", "5 hit cluster"], loc='best')
#             plt.ylim(0, 100)
#             plt.xlim(0, 12000)
    fig = plt.gca()
    fig.patch.set_facecolor('white')
    plt.show()
    plt.close()


def plot_result(x_p, y_p, y_p_e):
    ''' Fit spline to the profile histogramed data, differentiate, determine MPV and plot.
     Parameters
    ----------
        x_p, y_p : array like
            data points (x,y)
        y_p_e : array like
            error bars in y
    '''

    if len(y_p_e[y_p_e == 0]) != 0:
        logging.warning('There are bins without any data, guessing the error bars')
        y_p_e[y_p_e == 0] = np.amin(y_p_e[y_p_e != 0])

    smoothed_data = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=0)
    smoothed_data_diff = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=1)

    p1 = plt.errorbar(x_p * vcal_calibration, y_p, yerr=y_p_e, fmt='o')  # plot differentiated data with error bars of data
    p2, = plt.plot(x_p * vcal_calibration, smoothed_data, '-r')  # plot smoothed data
    p3, = plt.plot(x_p * vcal_calibration, -100. * smoothed_data_diff, '-', lw=2)  # plot differentiated data
    mpv_index = np.argmax(-analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=smoothness, derivation=1))
    p4, = plt.plot([x_p[mpv_index] * vcal_calibration, x_p[mpv_index] * vcal_calibration], [0, -100. * smoothed_data_diff[mpv_index]], 'k-', lw=2)
    text = 'MPV ' + str(int(x_p[mpv_index] * vcal_calibration)) + ' e'
    plt.text(1.01 * x_p[mpv_index] * vcal_calibration, -10. * smoothed_data_diff[mpv_index], text, ha='left')
    plt.legend([p1, p2, p3, p4], ['data', 'smoothed spline', 'spline differentiation', text], prop={'size': 12})
    plt.title('\'Single hit cluster\'-occupancy for different pixel thresholds')
    plt.xlabel('Pixel threshold [e]')
    plt.ylabel('Single hit cluster occupancy [a.u.]')
    plt.ylim((0, 1.02 * np.amax(np.append(y_p, -100. * smoothed_data_diff))))
    plt.show()


def select_hot_region(hits, col_span, row_span, cut_threshold=0.8):
    '''Takes the hit array and masks all pixels with occupancy < (max_occupancy-min_occupancy) * cut_threshold.

    Parameters
    ----------
    hits : array like
        If dim > 2 the additional dimensions are summed up.
    cut_threshold : float, [0, 1]
        A number to specify the threshold, which pixel to take. Pixels are masked if
        occupancy < (max_occupancy-min_occupancy) * cut_threshold
        1 means that all pixels are masked
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
    return np.ma.masked_where(ma < cut_threshold * (np.amax(ma) - np.amin(ma)), ma)


def analyze_raw_data(input_file, output_file_hits, chip_flavor, scan_data_filename):
    logging.info('Analyze the raw FE data and store the needed data')
    with AnalyzeRawData(raw_data_file=input_file, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_cluster_hit_table = False  # adds the cluster id and seed info to each hit, std. setting is false
        analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false

        analyze_raw_data.create_occupancy_hist = True  # creates a colxrow histogram with accumulated hits for each scan parameter
        analyze_raw_data.create_source_scan_hist = True  # create source scan hists
        analyze_raw_data.create_tot_hist = True  # creates a ToT histogram
        analyze_raw_data.create_rel_bcid_hist = True  # creates a histogram with the relative BCID of the hits
        analyze_raw_data.create_service_record_hist = True  # creates a histogram with all SR send out from the FE
        analyze_raw_data.create_error_hist = True  # creates a histogram summing up the event errors that occurred
        analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
        analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
        analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false

        analyze_raw_data.create_meta_word_index = False  # stores the start and stop raw data word index for every event, std. setting is false
        analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False

        analyze_raw_data.n_bcid = n_bcid  # set the number of BCIDs per event, needed to judge the event structure
        analyze_raw_data.max_tot_value = max_tot_value  # set the maximum ToT value considered to be a hit, 14 is a late hit

        analyze_raw_data.interpreter.set_warning_output(True)  # std. setting is True
        analyze_raw_data.interpreter.debug_events(0, 10, False)  # events to be printed onto the console for debugging, usually deactivated
        analyze_raw_data.interpret_word_table(fei4b=True if(chip_flavor == 'fei4b') else False)  # the actual start conversion command
        analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
        analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filename)  # plots all activated histograms into one pdf


def analyze_cluster_size(input_file_hits, output_file, output_file_pdf):
    logging.info('Analyze the cluster sizes for different threshold settings')
    with tb.openFile(input_file_hits, mode="r+") as in_hit_file_h5:
        meta_data_array = in_hit_file_h5.root.meta_data[:]
        scan_parameter_values = analysis_utils.get_scan_parameter(meta_data_array).itervalues().next()
        scan_parameter_name = analysis_utils.get_scan_parameter(meta_data_array).keys()[0]
        logging.info('Analyze per scan parameter ' + scan_parameter_name + ' for ' + str(len(scan_parameter_values)) + ' different values from ' + str(np.amin(scan_parameter_values)) + ' to ' + str(np.amax(scan_parameter_values)))
        event_numbers = analysis_utils.get_meta_data_at_scan_parameter(meta_data_array, scan_parameter_name)['event_number']  # get the event numbers in meta_data where the scan parameter changes
        parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_event_range(event_numbers)))
        hit_table = in_hit_file_h5.root.Hits

        if not hit_table.cols.event_number.is_indexed:  # index event_number column to speed up everything
            logging.info('Create event_number index, this takes about a minute')
            hit_table.cols.event_number.create_csindex(filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))  # this takes time (1 min. ~ 150. Mio entries) but immediately pays off
            logging.info('Done')
        else:
            logging.info('Event_number index exists already')

        output_pdf = PdfPages(output_file_pdf)
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
                for hits, index in analysis_utils.data_aligned_at_events(hit_table, start_event_number=start_event_number, stop_event_number=stop_event_number, start=index, chunk_size=chunk_size):
                    total_hits += hits.shape[0]
                    analyze_data.analyze_hits(hits)  # analyze the selected hits in chunks

                    readout_hit_len += hits.shape[0]
                chunk_size = int(1.05 * readout_hit_len) if int(1.05 * readout_hit_len) < max_chunk_size else max_chunk_size  # to increase the readout speed, estimated the number of hits for one read instruction
                if chunk_size < 50:  # limit the lower chunk size, there can always be a crazy event with more than 20 hits
                    chunk_size = 50
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


def analyse_selected_hits(input_file_hits, output_file_hits, output_file_hits_analyzed, scan_data_filename, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1'):
    logging.info('Select hits with ' + cluster_size_condition + ' and ' + n_cluster_condition)
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
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
    logging.info('Analyze hits with ' + cluster_size_condition + ' and ' + n_cluster_condition)
    with AnalyzeRawData(raw_data_file=None, analyzed_data_file=output_file_hits) as analyze_raw_data:
        analyze_raw_data.create_source_scan_hist = True
        analyze_raw_data.create_tot_hist = False
        analyze_raw_data.create_cluster_size_hist = True
        analyze_raw_data.create_cluster_tot_hist = True
        analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
        analyze_raw_data.plot_histograms(scan_data_filename=output_file_hits_analyzed, analyzed_data_file=output_file_hits_analyzed)
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:  # copy meta data to the new analyzed file
        with tb.openFile(output_file_hits_analyzed, mode="r+") as output_hit_file_h5:
            in_hit_file_h5.root.meta_data.copy(output_hit_file_h5.root)  # copy meta_data note to new file


def analyze_injected_charge():
    logging.info('Analyze the injected charge')
    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        with tb.openFile(hit_analyzed_file, mode="r") as in_file_hits_h5:  # read scan data file from scan_fei4_trigger_gdac scan
            occupancy = in_file_hits_h5.root.HistOcc[:]
            meta_data = in_file_hits_h5.root.meta_data[:]
            mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
            threshold_calibration_array = in_file_calibration_h5.root.HistThresholdCalibration[:]

            gdac_range_calibration = mean_threshold_calibration['gdac']
            gdac_range_source_scan = analysis_utils.get_scan_parameter(meta_data_array=meta_data)['GDAC']

            normalization = get_normalization(meta_data, reference='event')  # normalize the number of hits for each GDAC setting, can be different due to different scan time

            correction_factors = 1
            if use_cluster_rate_correction:
                correction_h5 = tb.openFile(cluster_size_file, mode="r")
                cluster_size_histogram = correction_h5.root.AllHistClusterSize[:]
                correction_factors = get_hit_rate_correction(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_source_scan, cluster_size_histogram=cluster_size_histogram)
                plot_cluster_sizes(correction_h5, in_file_calibration_h5, gdac_range=gdac_range_source_scan, vcal_calibration=vcal_calibration)

            logging.info('Analyzing source scan data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_source_scan), np.min(gdac_range_source_scan), np.max(gdac_range_source_scan), np.min(np.gradient(gdac_range_source_scan)), np.max(np.gradient(gdac_range_source_scan))))
            logging.info('Use calibration data with %d different GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_calibration), np.min(gdac_range_calibration), np.max(gdac_range_calibration), np.min(np.gradient(gdac_range_calibration)), np.max(np.gradient(gdac_range_calibration))))

            pixel_thresholds = get_pixel_thresholds(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_calibration, threshold_calibration_array=threshold_calibration_array)  # interpolates the threshold at the source scan GDAC setting from the calibration
            pixel_hits = np.swapaxes(occupancy, 0, 1)  # create hit array with shape (col, row, ...)

            pixel_hits = pixel_hits * correction_factors * normalization

            # choose region with pixels that have a sufficient occupancy
            hot_pixel = select_hot_region(pixel_hits, col_span=col_span, row_span=row_span, cut_threshold=cut_threshold)
            pixel_mask = ~np.ma.getmaskarray(hot_pixel)
            selected_pixel_hits = pixel_hits[pixel_mask, :]  # reduce the data to pixels that are in the hot pixel region
            selected_pixel_thresholds = pixel_thresholds[pixel_mask, :]  # reduce the data to pixels that are in the hot pixel region
            plotting.plot_occupancy(hot_pixel.T, title='Select ' + str(len(selected_pixel_hits)) + ' pixels for analysis')

            # reshape to one dimension
            x = selected_pixel_thresholds.flatten()
            y = selected_pixel_hits.flatten()

            #nothing should be NAN, NAN is not supported yet
            if np.isfinite(x).shape != x.shape or np.isfinite(y).shape != y.shape:
                logging.warning('There are pixels with NaN or INF threshold or hit values, analysis will fail')

            # calculated profile histogram
            x_p, y_p, y_p_e = analysis_utils.get_profile_histogram(x, y, n_bins=n_bins)  # profile histogram data

            # select only the data point where the calibration worked
            selected_data = np.logical_and(x_p > min_thr / vcal_calibration, x_p < max_thr / vcal_calibration)
            x_p = x_p[selected_data]
            y_p = y_p[selected_data]
            y_p_e = y_p_e[selected_data]

            plot_result(x_p, y_p, y_p_e)

#             #  calculate and plot mean results
            x_mean = get_mean_threshold(gdac_range_source_scan, mean_threshold_calibration)
            y_mean = selected_pixel_hits.mean(axis=(0))

            plotting.plot_scatter(x_mean * 55, y_mean, title='Mean single pixel cluster rate at different thresholds', x_label='mean threshold [e]', y_label='mean single pixel cluster rate')

    if use_cluster_rate_correction:
        correction_h5.close()


if __name__ == "__main__":
    # input data names
    scan_name = 'scan_ext_trigger_gdac_0'
    folder = 'data\\dia_data\\'
    input_file_calibration = folder + 'calibrate_threshold_gdac_MDBM30.h5'

    # analysis options
    chip_flavor = 'fei4a'
    n_bcid = 4
    max_tot_value = 13
    use_cluster_rate_correction = True  # corrects the hit rate, because one pixel hit cluster are less likely for low thresholds
    smoothness = 20  # the smoothness of the spline fit to the data
    vcal_calibration = 55.  # calibration electrons/PlsrDAC
    n_bins = 100  # number of bins for the profile histogram
    col_span = [20, 60]  # the column pixel range to use in the analysis
    row_span = [20, 150]  # the row pixel range to use in the analysis
    cut_threshold = 0.01  # the cut threshold for the occupancy to define pixel to use in the analysis
    min_thr = 600  # minimum threshold position in electrons to be used for the analysis
    max_thr = 25000  # maximum threshold position in electrons to be used for the analysis

    # names of data files
    raw_data_file = folder + scan_name + '.h5'
    hit_file = folder + scan_name + '_interpreted.h5'
    cluster_size_file = folder + scan_name + '_cluster_sizes.h5'
    hit_cut = folder + scan_name + '_cut_hits.h5'
    hit_analyzed_file = folder + scan_name + '_cut_hits_analyzed.h5'

    analyze_raw_data(input_file=raw_data_file, output_file_hits=hit_file, chip_flavor=chip_flavor, scan_data_filename=folder + scan_name)
    analyse_selected_hits(input_file_hits=hit_file, output_file_hits=hit_cut, output_file_hits_analyzed=hit_analyzed_file, scan_data_filename=folder + scan_name)
    analyze_cluster_size(input_file_hits=hit_file, output_file=cluster_size_file, output_file_pdf=folder + scan_name + '_cluster_sizes.pdf')
    analyze_injected_charge()
