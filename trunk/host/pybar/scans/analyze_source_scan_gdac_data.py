''' This script does the full analysis of a source scan where the global threshold setting was changed to reconstruct the charge injected in a sensor pixel 
by a constant source. Several steps are done automatically:
Step 1 Tnterpret the raw data:
    This step interprets the raw data from the FE and creates and plots distributions.
    Everything is summed up, but the occupancy histogram is created per GDAC setting.
Step 2 Analyze selected hits:
    This step just takes the single hit cluster of the interpreted data and analyzes these hits for each GDAC setting.
Step 3 Analyze cluster size:
    In this step the fraction of 1,2,3,4, ... cluster sizes are determined for each GDAC setting.
Step 2.5 Histogram Cluster seeds:
    Instead of using single hit cluster (step 2/3) one can also use the cluster seed hits.
Step 4 Analyze the injected charge:
    Here the data from the previous steps is used to determine the injected charge. Plots of the results are shown.
'''
import logging
import numpy as np
import tables as tb
import os.path
import matplotlib.pyplot as plt

from pybar.analysis import analysis
from pybar.analysis import analysis_utils
from pybar.analysis.plotting import plotting
from pybar.analysis.analyze_raw_data import AnalyzeRawData


analysis_configuration = {
    "scan_name": ['files from scan_ext_trigger_gdac'],
    'input_file_calibration': 'file from calibrate_threshold_scan_parameter',
    "analysis_steps": [1, 2, 2.5, 3, 4],  # the analysis includes the selected steps here. See explanation above.
    "chip_flavor": 'fei4a',
    "n_bcid": 5,
    "max_tot_value": 13,  # maximum tot value to use the hit
    "use_cluster_rate_correction": False,  # corrects the hit rate, because one pixel hit cluster are less likely for low thresholds
    "normalize_rate": False,  # correct the number of GDACs per scan parameter by the number of triggers or scan time
    "normalization_reference": 'time',  # one can normalize the hits per GDAC setting to the number of events ('event') or time ('time')
    "smoothness": 400,  # the smoothness of the spline fit to the data
    "vcal_calibration": 55.,   # calibration electrons/PlsrDAC
    "n_bins": 300,  # number of bins for the profile histogram
    "col_span": [1, 80],  # the column pixel range to use in the analysis
    "row_span": [1, 336],  # the row pixel range to use in the analysis
    "min_cut_threshold": 0.8,  # the minimum cut threshold for the occupancy to define pixel to use in the analysis
    "max_cut_threshold": None,  # the maximum cut threshold for the occupancy to define pixel to use in the analysis
    "min_gdac": 0,  # minimum threshold position in gdac setting to be used for the analysis
    "max_gdac": 999999,  # maximum threshold position in gdac setting to be used for the analysis
    "min_thr": 1600,  # minimum threshold position in gdac setting to be used for the analysis
    "max_thr": 35000,  # maximum threshold position in gdac setting to be used for the analysis
    "plot_normalization": True,  # active the output of the normalization
    "plot_cluster_sizes": True,
    "interpreter_warnings": False,
    "overwrite_output_files": False
}


def plot_cluster_sizes(in_file_cluster_h5, in_file_calibration_h5, gdac_range):
    mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
    hist = in_file_cluster_h5.root.AllHistClusterSize[:]
    hist_sum = np.sum(hist, axis=1)
    hist_rel = hist / hist_sum[:, np.newaxis].astype('f4') * 100
    hist_rel_error = hist_rel / np.sqrt(hist_sum[:, np.newaxis].astype('f4'))  # TODO: check calculation
    x = analysis_utils.get_mean_threshold_from_calibration(gdac_range, mean_threshold_calibration)
    plt.grid(True)
    plt.errorbar(x * analysis_configuration['vcal_calibration'], hist_rel[:, 1], yerr=hist_rel_error[:, 1].tolist(), fmt='-o')
    plt.errorbar(x * analysis_configuration['vcal_calibration'], hist_rel[:, 2], yerr=hist_rel_error[:, 1].tolist(), fmt='-o')
    plt.errorbar(x * analysis_configuration['vcal_calibration'], hist_rel[:, 3], yerr=hist_rel_error[:, 1].tolist(), fmt='-o')
    plt.errorbar(x * analysis_configuration['vcal_calibration'], hist_rel[:, 4], yerr=hist_rel_error[:, 1].tolist(), fmt='-o')
    plt.errorbar(x * analysis_configuration['vcal_calibration'], hist_rel[:, 5], yerr=hist_rel_error[:, 1].tolist(), fmt='-o')
    plt.title('Frequency of different cluster sizes for different thresholds')
    plt.xlabel('threshold [e]')
    plt.ylabel('cluster size frequency [%]')
    plt.legend(["1 hit cluster", "2 hit cluster", "3 hit cluster", "4 hit cluster", "5 hit cluster"], loc='best')
    plt.ylim(0, 100)
    plt.xlim(0, 12000)
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
    logging.info('Plot results')
    plt.close()

    if len(y_p_e[y_p_e == 0]) != 0:
        logging.warning('There are bins without any data, guessing the error bars')
        y_p_e[y_p_e == 0] = np.amin(y_p_e[y_p_e != 0])

    smoothed_data = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=analysis_configuration['smoothness'], derivation=0)
    smoothed_data_diff = analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=analysis_configuration['smoothness'], derivation=1)

    p1 = plt.errorbar(x_p * analysis_configuration['vcal_calibration'], y_p, yerr=y_p_e, fmt='o')  # plot data with error bars
    p2, = plt.plot(x_p * analysis_configuration['vcal_calibration'], smoothed_data, '-r')  # plot smoothed data
    factor = np.amax(y_p) / np.amin(smoothed_data_diff) * 1.1
    p3, = plt.plot(x_p * analysis_configuration['vcal_calibration'], factor * smoothed_data_diff, '-', lw=2)  # plot differentiated data
    mpv_index = np.argmax(-analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=analysis_configuration['smoothness'], derivation=1))
    p4, = plt.plot([x_p[mpv_index] * analysis_configuration['vcal_calibration'], x_p[mpv_index] * analysis_configuration['vcal_calibration']], [0, factor * smoothed_data_diff[mpv_index]], 'k-', lw=2)
    text = 'MPV ' + str(int(x_p[mpv_index] * analysis_configuration['vcal_calibration'])) + ' e'
    plt.text(1.01 * x_p[mpv_index] * analysis_configuration['vcal_calibration'], -10. * smoothed_data_diff[mpv_index], text, ha='left')
    plt.legend([p1, p2, p3, p4], ['data', 'smoothed spline', 'spline differentiation', text], prop={'size': 12}, loc=0)
    plt.title('\'Single hit cluster\'-occupancy for different pixel thresholds')
    plt.xlabel('Pixel threshold [e]')
    plt.ylabel('Single hit cluster occupancy [a.u.]')
    plt.ylim(0, np.amax(y_p) * 1.15)
    plt.show()
    plt.close()


def analyze_raw_data(input_files, output_file_hits, chip_flavor, scan_parameter):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    if os.path.isfile(output_file_hits) and not analysis_configuration['overwrite_output_files']:  # skip analysis if already done
            logging.info('Analyzed data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        with AnalyzeRawData(raw_data_file=input_files, analyzed_data_file=output_file_hits, scan_parameter_name=scan_parameter) as analyze_raw_data:
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_source_scan_hist = True  # create source scan hists
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.n_bcid = analysis_configuration['n_bcid']  # set the number of BCIDs per event, needed to judge the event structure
            analyze_raw_data.max_tot_value = analysis_configuration['max_tot_value']  # set the maximum ToT value considered to be a hit, 14 is a late hit
            analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
            analyze_raw_data.interpreter.debug_events(0, 10, False)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpret_word_table(fei4b=True if(chip_flavor == 'fei4b') else False)  # the actual start conversion command
            analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
            analyze_raw_data.plot_histograms(scan_data_filename=output_file_hits)  # plots all activated histograms into one pdf


def analyse_selected_hits(input_file_hits, output_file_hits, output_file_hits_analyzed, scan_data_filenames, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1'):
    logging.info('Analyze selected hits with ' + cluster_size_condition + ' and ' + n_cluster_condition + ' in ' + input_file_hits)
    if os.path.isfile(output_file_hits) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
        logging.info('Selected hit data file ' + output_file_hits + ' already exists. Skip analysis for this file.')
    else:
        analysis.select_hits_from_cluster_info(input_file_hits=input_file_hits, output_file_hits=output_file_hits, cluster_size_condition=cluster_size_condition, n_cluster_condition=n_cluster_condition, output_pdf=None)  # select hits and copy the mto new file
    if os.path.isfile(output_file_hits_analyzed) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
        logging.info('Analyzed selected hit data file ' + output_file_hits_analyzed + ' already exists. Skip analysis for this file.')
    else:
        logging.info('Analyze selected hits in ' + output_file_hits)
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


def analyze_injected_charge(data_analyzed_file):
    logging.info('Analyze the injected charge')
    with tb.openFile(data_analyzed_file, mode="r") as in_file_h5:
        occupancy = in_file_h5.root.HistOcc[:]
        gdacs = analysis_utils.get_scan_parameter(in_file_h5.root.meta_data[:])['GDAC']
        with tb.openFile(analysis_configuration['input_file_calibration'], mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
            mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
            threshold_calibration_array = in_file_calibration_h5.root.HistThresholdCalibration[:]

            gdac_range_calibration = mean_threshold_calibration['gdac']
            gdac_range_source_scan = gdacs

            logging.info('Analyzing source scan data with %d GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_source_scan), np.min(gdac_range_source_scan), np.max(gdac_range_source_scan), np.min(np.gradient(gdac_range_source_scan)), np.max(np.gradient(gdac_range_source_scan))))
            logging.info('Use calibration data with %d GDAC settings from %d to %d with minimum step sizes from %d to %d' % (len(gdac_range_calibration), np.min(gdac_range_calibration), np.max(gdac_range_calibration), np.min(np.gradient(gdac_range_calibration)), np.max(np.gradient(gdac_range_calibration))))

            # rate_normalization of the total hit number for each GDAC setting
            rate_normalization = 1.
            if analysis_configuration['normalize_rate']:
                rate_normalization = analysis_utils.get_rate_normalization(hit_file=hit_file, cluster_file=hit_file, parameter='GDAC', reference=analysis_configuration['normalization_reference'], plot=analysis_configuration['plot_normalization'])

            # correcting the hit numbers for the different cluster sizes
            correction_factors = 1.
            if analysis_configuration['use_cluster_rate_correction']:
                correction_h5 = tb.openFile(cluster_sizes_file, mode="r")
                cluster_size_histogram = correction_h5.root.AllHistClusterSize[:]
                correction_factors = analysis_utils.get_hit_rate_correction(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_source_scan, cluster_size_histogram=cluster_size_histogram)
                if analysis_configuration['plot_cluster_sizes']:
                    plot_cluster_sizes(correction_h5, in_file_calibration_h5, gdac_range=gdac_range_source_scan)

            print correction_factors

            pixel_thresholds = analysis_utils.get_pixel_thresholds_from_calibration_array(gdacs=gdac_range_source_scan, calibration_gdacs=gdac_range_calibration, threshold_calibration_array=threshold_calibration_array)  # interpolates the threshold at the source scan GDAC setting from the calibration
            pixel_hits = np.swapaxes(occupancy, 0, 1)  # create hit array with shape (col, row, ...)
            pixel_hits = pixel_hits * correction_factors * rate_normalization

            # choose region with pixels that have a sufficient occupancy but are not too hot
            good_pixel = analysis_utils.select_good_pixel_region(pixel_hits, col_span=analysis_configuration['col_span'], row_span=analysis_configuration['row_span'], min_cut_threshold=analysis_configuration['min_cut_threshold'], max_cut_threshold=analysis_configuration['max_cut_threshold'])
            pixel_mask = ~np.ma.getmaskarray(good_pixel)
            selected_pixel_hits = pixel_hits[pixel_mask, :]  # reduce the data to pixels that are in the good pixel region
            selected_pixel_thresholds = pixel_thresholds[pixel_mask, :]  # reduce the data to pixels that are in the good pixel region
            plotting.plot_occupancy(good_pixel.T, title='Select ' + str(len(selected_pixel_hits)) + ' pixels for analysis')

            # reshape to one dimension
            x = selected_pixel_thresholds.flatten()
            y = selected_pixel_hits.flatten()

            #nothing should be NAN, NAN is not supported yet
            if np.isfinite(x).shape != x.shape or np.isfinite(y).shape != y.shape:
                logging.warning('There are pixels with NaN or INF threshold or hit values, analysis will fail')

            # calculated profile histogram
            x_p, y_p, y_p_e = analysis_utils.get_profile_histogram(x, y, n_bins=analysis_configuration['n_bins'])  # profile histogram data

            # select only the data point where the calibration worked
            selected_data = np.logical_and(x_p > analysis_configuration['min_thr'] / analysis_configuration['vcal_calibration'], x_p < analysis_configuration['max_thr'] / analysis_configuration['vcal_calibration'])
            x_p = x_p[selected_data]
            y_p = y_p[selected_data]
            y_p_e = y_p_e[selected_data]

            plot_result(x_p, y_p, y_p_e)

            #  calculate and plot mean results
            x_mean = analysis_utils.get_mean_threshold_from_calibration(gdac_range_source_scan, mean_threshold_calibration)
            y_mean = selected_pixel_hits.mean(axis=(0))

            plotting.plot_scatter(np.array(gdac_range_source_scan), y_mean, log_x=True, plot_range=None, title='Mean single pixel cluster rate at different thresholds', x_label='threshold setting [GDAC]', y_label='mean single pixel cluster rate')
            plotting.plot_scatter(x_mean * analysis_configuration['vcal_calibration'], y_mean, plot_range=(analysis_configuration['min_thr'], analysis_configuration['max_thr']), title='Mean single pixel cluster rate at different thresholds', x_label='mean threshold [e]', y_label='mean single pixel cluster rate')

        if analysis_configuration['use_cluster_rate_correction']:
            correction_h5.close()

if __name__ == "__main__":
    data_files = analysis_utils.get_data_file_names_from_scan_base(analysis_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=True)
    files_dict = analysis_utils.get_parameter_from_files(data_files, unique=True, parameters='GDAC')  # get a sorted ordered dict with GDAC, raw_data_filename
    logging.info('Found ' + str(len(files_dict)) + ' raw data files.')

    hit_file = analysis_configuration['scan_name'][0] + '_interpreted.h5'
    hit_cut_file = analysis_configuration['scan_name'][0] + '_cut_hits.h5'
    hit_cut_analyzed_file = analysis_configuration['scan_name'][0] + '_cut_hits_analyzed.h5'
    cluster_seed_analyzed_file = analysis_configuration['scan_name'][0] + '_cluster_seeds_analyzed.h5'
    cluster_sizes_file = analysis_configuration['scan_name'][0] + '_ALL_cluster_sizes.h5'

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=files_dict.keys(), output_file_hits=hit_file, chip_flavor=analysis_configuration['chip_flavor'], scan_parameter='GDAC')
    if 2 in analysis_configuration['analysis_steps']:
        analyse_selected_hits(input_file_hits=hit_file, output_file_hits=hit_cut_file, output_file_hits_analyzed=hit_cut_analyzed_file, scan_data_filenames=analysis_configuration['scan_name'][0])
    if 2.5 in analysis_configuration['analysis_steps']:
        if os.path.isfile(cluster_seed_analyzed_file) and not analysis_configuration["overwrite_output_files"]:
            logging.info('Selected cluster hit histogram data file ' + cluster_seed_analyzed_file + ' already exists. Skip analysis for this file.')
        else:
            analysis.histogram_cluster_table(hit_file, cluster_seed_analyzed_file)
    if 3 in analysis_configuration['analysis_steps']:
        analysis.analyze_cluster_size_per_scan_parameter(input_file_hits=hit_file, output_file_cluster_size=cluster_sizes_file, parameter='GDAC', overwrite_output_files=analysis_configuration['overwrite_output_files'], output_pdf=False)
    if 4 in analysis_configuration['analysis_steps']:
        analyze_injected_charge(data_analyzed_file=cluster_seed_analyzed_file)
