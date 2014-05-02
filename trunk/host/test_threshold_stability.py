"""A script that runs a threshold scan for different command string send to the FE. Can be used to determine if there is a threshold shift if the LVL1/CAL is send.
Command sequence:
    arbitrary FE command + delay + CAL + fixed delay + LVL1
"""
from datetime import datetime
import configuration
import progressbar
import tables as tb
import numpy as np
import logging
import os

from scan_threshold_fast import FastThresholdScan
from analysis import analysis_utils
from analysis.RawDataConverter import data_struct

from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting.plotting import plotThreeWay, plot_scurves, plot_scatter
from analysis.analyze_raw_data import AnalyzeRawData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

calibration_configuration = {
    "delays": range(100, 2000, 100),  # the delay between the arbitrary command and the CAL command
    "data_file": 'data//scc_30_elsa//2_trigger_data//6//CAL DELAY CAL fixedDelay LVL1 DELAY',
    "ignore_columns": (1, 78, 79, 80),
    "create_plots": True,
    "scan_identifier": 'data//scc_30_elsa//2_trigger_data//6//scc_30_elsa_test_threshold_stability',
    "create_result_plots": True,
    "overwrite_output_files": False
}


def analyze(raw_data_file, analyzed_data_file, fei4b=False):
    if not os.path.isfile(analyzed_data_file) or calibration_configuration['overwrite_output_files']:
        with AnalyzeRawData(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(fei4b=fei4b)
    #         analyze_raw_data.interpreter.print_summary()
    else:
        logging.debug(analyzed_data_file + ' exists already, skip analysis.')


def store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration):
    logging.info("Storing calibration data in a table...")
    filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    mean_threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='MeanThreshold', description=data_struct.MeanThresholdTable, title='mean_threshold_calibration', filters=filter_table)
    threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='Threshold', description=data_struct.ThresholdTable, title='threshold_calibration', filters=filter_table)
    for column in range(0, 80):
        for row in range(0, 336):
            for delay_index, delay_value in enumerate(calibration_configuration['delays']):
                threshold_calib_table.row['column'] = column
                threshold_calib_table.row['row'] = row
                threshold_calib_table.row['parameter'] = delay_value
                threshold_calib_table.row['threshold'] = threshold_calibration[column, row, delay_index]
                threshold_calib_table.row.append()
    for delay_index, delay_value in enumerate(calibration_configuration['delays']):
        mean_threshold_calib_table.row['parameter'] = delay_value
        mean_threshold_calib_table.row['mean_threshold'] = mean_threshold_calibration[delay_index]
        mean_threshold_calib_table.row['threshold_rms'] = mean_threshold_rms_calibration[delay_index]
        mean_threshold_calib_table.row.append()

    threshold_calib_table.flush()
    mean_threshold_calib_table.flush()
    logging.info("done")


def store_calibration_data_as_array(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration):
    logging.info("Storing calibration data in an array...")
    filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    mean_threshold_calib_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdMeanCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_calibration', filters=filter_table)
    mean_threshold_calib_rms_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdRMSCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_rms_calibration', filters=filter_table)
    threshold_calib_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdCalibration', atom=tb.Atom.from_dtype(threshold_calibration.dtype), shape=threshold_calibration.shape, title='threshold_calibration', filters=filter_table)
    mean_threshold_calib_array[:] = mean_threshold_calibration
    mean_threshold_calib_rms_array[:] = mean_threshold_rms_calibration
    threshold_calib_array[:] = threshold_calibration
    logging.info("done")


def create_calibration(scan_data_filenames, ignore_columns, fei4b=False):
    logging.info("Analyzing and plotting results...")
    output_h5_filename = calibration_configuration['data_file'] + '.h5'
    logging.info('Saving calibration in: %s' % output_h5_filename)

    if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
        output_pdf_filename = calibration_configuration['data_file'] + '.pdf'
        logging.info('Saving plot in: %s' % output_pdf_filename)
        output_pdf = PdfPages(output_pdf_filename)

    mean_threshold_calibration = np.empty(shape=(len(calibration_configuration['delays']),), dtype='<f8')  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration = np.empty(shape=(len(calibration_configuration['delays']),), dtype='<f8')  # array to hold the analyzed data in ram
    threshold_calibration = np.empty(shape=(80, 336, len(calibration_configuration['delays'])), dtype='<f8')  # array to hold the analyzed data in ram

    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=len(calibration_configuration['delays']))
    progress_bar.start()

    for delay_index, delay_value in enumerate(calibration_configuration['delays']):
        raw_data_file = scan_data_filenames[delay_value]
        analyzed_data_file = raw_data_file[:-3] + '_interpreted.h5'
        analyze(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file, fei4b=fei4b)

        with tb.openFile(analyzed_data_file, mode="r") as in_file_h5:
            # mask the not scanned columns for analysis and plotting
            occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)
            thresholds_masked = mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns)
            # plot the threshold distribution and the s curves
            if calibration_configuration['create_plots']:
                plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for delay = ' + str(delay_value), filename=output_pdf)
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_parameters = parameter_settings['PlsrDAC']
            if calibration_configuration['create_plots']:
                plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[delay_index] = np.ma.mean(thresholds_masked)
            mean_threshold_rms_calibration[delay_index] = np.ma.std(thresholds_masked)
            threshold_calibration[:, :, delay_index] = thresholds_masked.T
        progress_bar.update(delay_index)
    progress_bar.finish()

    if calibration_configuration['create_result_plots']:
        plot_scatter(x=calibration_configuration['delays'], y=mean_threshold_calibration, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Mean threshold', log_x=False, filename=output_pdf)
        plot_scatter(x=calibration_configuration['delays'], y=mean_threshold_calibration, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Mean threshold', log_x=True, filename=output_pdf)
        plot_scatter(x=calibration_configuration['delays'], y=mean_threshold_rms_calibration, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Threshold RMS', log_x=False, filename=output_pdf)
        plot_scatter(x=calibration_configuration['delays'], y=mean_threshold_rms_calibration, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Threshold RMS', log_x=True, filename=output_pdf)

    if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
        output_pdf.close()

    # store the calibration data into a hdf5 file as an easy to read table and as an array for quick data access
    with tb.openFile(output_h5_filename, mode="w") as out_file_h5:
        store_calibration_data_as_array(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)
        store_calibration_data_as_table(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)


def reanalyze(fei4b=False):
    data_files = analysis_utils.get_data_file_names_from_scan_base(calibration_configuration['scan_identifier'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=True)
    import pprint
    data_files_par = analysis_utils.get_parameter_value_from_file_names(data_files, parameters='stability')
    pprint.pprint(data_files_par)
    scan_data_filenames = {}
    calibration_configuration['delays'] = []
    for file_name, parameter in data_files_par.items():
        scan_data_filenames[parameter['stability'][0]] = file_name
        calibration_configuration['delays'].append(parameter['stability'][0])
    calibration_configuration['stability'] = sorted(scan_data_filenames.keys())
    create_calibration(scan_data_filenames=scan_data_filenames, ignore_columns=calibration_configuration['ignore_columns'], fei4b=fei4b)


def mask_columns(pixel_array, ignore_columns):
    idx = np.array(ignore_columns) - 1  # from FE to Array columns
    m = np.zeros_like(pixel_array)
    m[:, idx] = 1
    return np.ma.masked_array(pixel_array, m)


if __name__ == "__main__":
    startTime = datetime.now()
#     reanalyze()
    logging.info('Taking threshold data for following delay: %s' % str(calibration_configuration['delays']))
    scan_data_filenames = {}
    scan_threshold_fast = FastThresholdScan(**configuration.scc_30_elsa_configuration)
    for i, delay_value in enumerate(calibration_configuration['delays']):
        command = scan_threshold_fast.register.get_commands("cal")[0] + scan_threshold_fast.register.get_commands("zeros", length=40)[0] + scan_threshold_fast.register.get_commands("zeros", length=delay_value)[0] + scan_threshold_fast.register.get_commands("cal")[0] + scan_threshold_fast.register.get_commands("zeros", length=40)[0] + scan_threshold_fast.register.get_commands("lv1")[0] + scan_threshold_fast.register.get_commands("zeros", length=delay_value)[0]
        scan_threshold_fast.scan_identifier = calibration_configuration['scan_identifier'] + '_' + str(delay_value)
        scan_threshold_fast.start(configure=True, scan_parameter_range=(0, 70), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=10, ignore_columns=calibration_configuration['ignore_columns'], command=command)
        scan_threshold_fast.stop()
        scan_data_filenames[delay_value] = scan_threshold_fast.scan_data_filename

    logging.info("Measurement finished in " + str(datetime.now() - startTime))

#     analyze and plot the data from all scans
    create_calibration(scan_data_filenames=scan_data_filenames, ignore_columns=calibration_configuration['ignore_columns'], fei4b=scan_threshold_fast.register.fei4b)

    logging.info("Finished!")
