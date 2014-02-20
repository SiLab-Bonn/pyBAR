''' This script does the full analysis of the tdc values taken during a source scan.
Several steps are done automatically:
Step 1 Tnterpret the raw data:
    This step interprets the raw data from the FE, creates and plots distributions for each data file seperately.
    Everything is summed up per data file.
Step 2 Analyze selected hits:
    This step just takes event with one hit and single hit cluster of the interpreted data and histograms these hits TDC for each pixel separately.
Step 3 Takes the calibration and creates a TDC histogram for all chosen pixel.
'''
import numpy as np
import tables as tb
import os.path
import matplotlib.pyplot as plt
from analysis import analysis
from analysis.plotting import plotting
from analysis import analysis_utils
from scipy.sparse import coo_matrix
from analysis.analyze_raw_data import AnalyzeRawData
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


analysis_configuration = {
    'input_file_calibration': None,
    'scan_base_names': ['data//SCC_99//SCC_99_fei4_self_trigger_hit_or_602_col_row'],
    "chip_flavor": 'fei4a',
    "n_bcid": 16,
    "analysis_steps": [3],#, 2, 3, 4],  # the analysis includes the selected steps here. See explanation above.
    "max_tot_value": 13,  # maximum tot value to use the hit
    "vcal_calibration": 55.,   # calibration electrons/PlsrDAC
    "interpreter_plots": True,
    "interpreter_warnings": True,
    "overwrite_output_files": True
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
#     fig = plt.gca()
#     fig.patch.set_facecolor('white')
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

    p1 = plt.errorbar(x_p * analysis_configuration['vcal_calibration'], y_p, yerr=y_p_e, fmt='o')  # plot differentiated data with error bars of data
    p2, = plt.plot(x_p * analysis_configuration['vcal_calibration'], smoothed_data, '-r')  # plot smoothed data
    p3, = plt.plot(x_p * analysis_configuration['vcal_calibration'], -100. * smoothed_data_diff, '-', lw=2)  # plot differentiated data
    mpv_index = np.argmax(-analysis_utils.smooth_differentiation(x_p, y_p, weigths=1 / y_p_e, order=3, smoothness=analysis_configuration['smoothness'], derivation=1))
    p4, = plt.plot([x_p[mpv_index] * analysis_configuration['vcal_calibration'], x_p[mpv_index] * analysis_configuration['vcal_calibration']], [0, -100. * smoothed_data_diff[mpv_index]], 'k-', lw=2)
    text = 'MPV ' + str(int(x_p[mpv_index] * analysis_configuration['vcal_calibration'])) + ' e'
    plt.text(1.01 * x_p[mpv_index] * analysis_configuration['vcal_calibration'], -10. * smoothed_data_diff[mpv_index], text, ha='left')
    plt.legend([p1, p2, p3, p4], ['data', 'smoothed spline', 'spline differentiation', text], prop={'size': 12})
    plt.title('\'Single hit cluster\'-occupancy for different pixel thresholds')
    plt.xlabel('Pixel threshold [e]')
    plt.ylabel('Single hit cluster occupancy [a.u.]')
    plt.ylim((0, 1.02 * np.amax(np.append(y_p, -100. * smoothed_data_diff))))
    plt.show()
    plt.close()


def analyze_raw_data(input_files, output_files_hits, chip_flavor, scan_data_filenames):
    logging.info('Analyze the raw FE data given in ' + str(len(input_files)) + ' files and store the needed data')
    for index in range(0, len(input_files)):  # loop over all raw data files
        if os.path.isfile(output_files_hits[index]) and not analysis_configuration['overwrite_output_files']:  # skip analysis if already done
            logging.info('Analyzed data file ' + output_files_hits[index] + ' already exists. Skip analysis for this file.')
        else:
            with AnalyzeRawData(raw_data_file=input_files[index], analyzed_data_file=output_files_hits[index]) as analyze_raw_data:
                analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
                analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
                analyze_raw_data.create_source_scan_hist = True  # create source scan hists
                analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
                analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
                analyze_raw_data.n_bcid = analysis_configuration['n_bcid']  # set the number of BCIDs per event, needed to judge the event structure
                analyze_raw_data.max_tot_value = analysis_configuration['max_tot_value']  # set the maximum ToT value considered to be a hit, 14 is a late hit
                analyze_raw_data.interpreter.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
                analyze_raw_data.clusterizer.set_warning_output(analysis_configuration['interpreter_warnings'])  # std. setting is True
                analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
                analyze_raw_data.interpret_word_table(fei4b=True if(chip_flavor == 'fei4b') else False)  # the actual start conversion command
                analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
                if analysis_configuration['interpreter_plots']:
                    analyze_raw_data.plot_histograms(scan_data_filename=scan_data_filenames[index])  # plots all activated histograms into one pdf
    analysis_utils.get_data_statistics(output_files_hits)


def analyse_selected_hits(input_files_hits, output_files_hits, output_files_hits_analyzed, scan_data_filenames, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1'):
    logging.info('Analyze selected hits with ' + cluster_size_condition + ' and ' + n_cluster_condition + ' for ' + str(len(input_files_hits)) + ' hit file(s)')
    for index in range(0, len(input_files_hits)):  # loop over all hit files
        if os.path.isfile(output_files_hits[index]) and not analysis_configuration["overwrite_output_files"]:  # skip analysis if already done
            logging.info('Selected hit data file ' + output_files_hits[index] + ' already exists. Skip analysis for this file.')
        else:
            analysis.select_hits_for_tdc_info(input_file_hits=input_files_hits[index], output_file_hits=output_files_hits[index], cluster_size_condition=cluster_size_condition, n_cluster_condition=n_cluster_condition, output_pdf=None)  # select hits and copy the mto new file
#         if os.path.isfile(output_files_hits_analyzed[index]):  # skip analysis if already done
#             logging.info('Analyzed selected hit data file ' + output_files_hits_analyzed[index] + ' already exists. Skip analysis for this file.')
#         else:
#             logging.info('Analyze selected hits in ' + output_files_hits[index])
#             with AnalyzeRawData(raw_data_file=None, analyzed_data_file=output_files_hits[index]) as analyze_raw_data:
#                 analyze_raw_data.create_source_scan_hist = True
#                 analyze_raw_data.create_tot_hist = False
#                 analyze_raw_data.create_tdc_hist = True
#                 analyze_raw_data.create_cluster_size_hist = True
#                 analyze_raw_data.create_cluster_tot_hist = True
#                 analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_files_hits_analyzed[index])
#                 analyze_raw_data.plot_histograms(scan_data_filename=output_files_hits_analyzed[index], analyzed_data_file=output_files_hits_analyzed[index])
#             with tb.openFile(input_files_hits[index], mode="r") as in_hit_file_h5:  # copy meta data to the new analyzed file
#                 with tb.openFile(output_files_hits_analyzed[index], mode="r+") as output_hit_file_h5:
#                     in_hit_file_h5.root.meta_data.copy(output_hit_file_h5.root)  # copy meta_data note to new file


def analyze_tdc(input_files_hits, output_file, output_file_pdf=None):
    logging.info('Analyze the tdc histograms')
    tdc_hist_per_pixel = None
    with tb.openFile(output_file, mode="w") as output_file_h5:
        for input_files_hit in input_files_hits:
            with tb.openFile(input_files_hit, mode="r+") as in_hit_file_h5:
                hit_table = in_hit_file_h5.root.Hits
                analysis_utils.index_event_number(hit_table)
                for hits, _ in analysis_utils.data_aligned_at_events(hit_table):
                    pixel = hits[:]['row'] + hits[:]['column'] * 335  # make 2d -> 1d hist to be able to use the supported 2d sparse matrix
                    if tdc_hist_per_pixel is None:
                        tdc_hist_per_pixel = coo_matrix((np.ones(shape=(len(pixel,)), dtype=np.uint8), (pixel, hits[:]['TDC'])), shape=(80 * 336, 4096)).todense()  # use sparse matrix to keep memory usage decend
                    else:
                        tdc_hist_per_pixel += coo_matrix((np.ones(shape=(len(pixel,)), dtype=np.uint8), (pixel, hits[:]['TDC'])), shape=(80 * 336, 4096)).todense()
        tdc_hist_array = output_file_h5.createCArray(output_file_h5.root, name='HistPixelTdc', title='Pixel TDC Histograms', atom=tb.Atom.from_dtype(tdc_hist_per_pixel.dtype), shape=tdc_hist_per_pixel.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        tdc_hist_array[:] = tdc_hist_per_pixel

if __name__ == "__main__":
    scan_base_names = analysis_utils.get_parameter_scan_bases_from_scan_base(analysis_configuration['scan_base_names'])
    logging.info('Found ' + str(len(scan_base_names)) + ' data files for different pixels')

    raw_data_files = [filename + '.h5' for filename in scan_base_names]
    hit_files = [filename + '_interpreted.h5' for filename in scan_base_names]
    hit_cut_files = [filename + '_cut_hits.h5' for filename in scan_base_names]
    hit_analyzed_files = [filename + '_cut_hits_analyzed.h5' for filename in scan_base_names]

    if 1 in analysis_configuration['analysis_steps']:
        analyze_raw_data(input_files=raw_data_files, output_files_hits=hit_files, chip_flavor=analysis_configuration['chip_flavor'], scan_data_filenames=scan_base_names)
    if 2 in analysis_configuration['analysis_steps']:
        analyse_selected_hits(input_files_hits=hit_files, output_files_hits=hit_cut_files, output_files_hits_analyzed=hit_analyzed_files, scan_data_filenames=scan_base_names)
    if 3 in analysis_configuration['analysis_steps']:
        analyze_tdc(input_files_hits=hit_cut_files, output_file='tdc_histograms.h5', output_file_pdf=None)
