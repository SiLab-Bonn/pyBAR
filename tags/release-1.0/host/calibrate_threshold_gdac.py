"""A script that runs a threshold scan for different GDAC settings to get a calibration. To save time the PlsrDAC start position is the start position determined from the previous threshold scan.
After the data taking the data is analyzed and the calibration is written to h5 files.
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
    "gdacs": [66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,232,233,234,235,236,237,238,239,240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255,263,280,299,320,344,369,398,429,464,502,544,591,643,700,763,833,910,995,1089,1193,1308,1435,1576,1731,1903,2093,2302,2534,2790,3073,3385,3731,4113,4535,5002,5517,6000,6500,7000,7500,8000,8500,9000,9500,10000,10500,11000,11500,12000,12500,13000,13500,14000,14500,15000,15500,16000,16500,17000,17500,18000,18500,19000,19500,20000],
    "ignore_columns": (1, 78, 79, 80),
    "ignore_gdacs": None,  # do not use data for these GDACs
    "create_plots": False,
    "create_result_plots": True,
    "scan_name": "K:\data\FE-I4\ChargeRecoMethod\source_SR90\calibration_new\calibrate_threshold_gdac_SCC_99",
    "configuration_file": "K:\data\FE-I4\ChargeRecoMethod\source_SR90\calibration_new\calibrate_threshold_gdac_skipped_gdacs",
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
    mean_threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='MeanThresholdCalibration', description=data_struct.MeanThresholdCalibrationTable, title='mean_threshold_calibration', filters=filter_table)
    threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='ThresholdCalibration', description=data_struct.ThresholdCalibrationTable, title='threshold_calibration', filters=filter_table)
    for column in range(0, 80):
        for row in range(0, 336):
            for gdac_index, gdac in enumerate(calibration_configuration['gdacs']):
                threshold_calib_table.row['column'] = column
                threshold_calib_table.row['row'] = row
                threshold_calib_table.row['gdac'] = gdac
                threshold_calib_table.row['threshold'] = threshold_calibration[column, row, gdac_index]
                threshold_calib_table.row.append()
    for gdac_index, gdac in enumerate(calibration_configuration['gdacs']):
        mean_threshold_calib_table.row['gdac'] = gdac
        mean_threshold_calib_table.row['mean_threshold'] = mean_threshold_calibration[gdac_index]
        mean_threshold_calib_table.row['threshold_rms'] = mean_threshold_rms_calibration[gdac_index]
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
    output_h5_filename = calibration_configuration['configuration_file'] + '.h5'
    logging.info('Saving calibration in: %s' % output_h5_filename)

    if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
        output_pdf_filename = calibration_configuration['configuration_file'] + '.pdf'
        logging.info('Saving plot in: %s' % output_pdf_filename)
        output_pdf = PdfPages(output_pdf_filename)

    mean_threshold_calibration = np.empty(shape=(len(calibration_configuration['gdacs']),), dtype='<f8')  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration = np.empty(shape=(len(calibration_configuration['gdacs']),), dtype='<f8')  # array to hold the analyzed data in ram
    threshold_calibration = np.empty(shape=(80, 336, len(calibration_configuration['gdacs'])), dtype='<f8')  # array to hold the analyzed data in ram

    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=len(calibration_configuration['gdacs']))
    progress_bar.start()

    for gdac_index, gdac in enumerate(calibration_configuration['gdacs']):
        if calibration_configuration['ignore_gdacs'] is not None and gdac in calibration_configuration['ignore_gdacs']:
            continue

        raw_data_file = scan_data_filenames[gdac]
        analyzed_data_file = raw_data_file[:-3] + '_interpreted.h5'
        analyze(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file, fei4b=fei4b)

        with tb.openFile(analyzed_data_file, mode="r") as in_file_h5:
            # mask the not scanned columns for analysis and plotting
            occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)
            thresholds_masked = mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns)
            # plot the threshold distribution and the s curves
            if calibration_configuration['create_plots']:
                plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for GDAC = ' + str(gdac), filename=output_pdf)
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_parameters = parameter_settings['PlsrDAC']
            if calibration_configuration['create_plots']:
                plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[gdac_index] = np.ma.mean(thresholds_masked)
            mean_threshold_rms_calibration[gdac_index] = np.ma.std(thresholds_masked)
            threshold_calibration[:, :, gdac_index] = thresholds_masked.T
        progress_bar.update(gdac_index)
    progress_bar.finish()

    if calibration_configuration['create_result_plots']:
        plot_scatter(x=calibration_configuration['gdacs'], y=mean_threshold_calibration, title='Threshold calibration', x_label='GDAC', y_label='Mean threshold', log_x=False, filename=output_pdf)
        plot_scatter(x=calibration_configuration['gdacs'], y=mean_threshold_calibration, title='Threshold calibration', x_label='GDAC', y_label='Mean threshold', log_x=True, filename=output_pdf)
        plot_scatter(x=calibration_configuration['gdacs'], y=mean_threshold_rms_calibration, title='Threshold calibration', x_label='GDAC', y_label='Threshold RMS', log_x=False, filename=output_pdf)
        plot_scatter(x=calibration_configuration['gdacs'], y=mean_threshold_rms_calibration, title='Threshold calibration', x_label='GDAC', y_label='Threshold RMS', log_x=True, filename=output_pdf)

    if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
        output_pdf.close()

    # store the calibration data into a hdf5 file as an easy to read table and as an array for quick data access
    with tb.openFile(output_h5_filename, mode="w") as out_file_h5:
        store_calibration_data_as_array(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)
        store_calibration_data_as_table(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)


def reanalyze(fei4b=False):
    data_files = analysis_utils.get_data_file_names_from_scan_base(calibration_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=True)
    data_files_par = analysis_utils.get_parameter_from_files(data_files, parameters='GDAC', unique=True, sort=True)
    scan_data_filenames = {}
    for file_name, parameter in data_files_par.items():
        scan_data_filenames[parameter['GDAC'][0]] = file_name
    calibration_configuration['gdacs'] = sorted(scan_data_filenames.keys())
    create_calibration(scan_data_filenames=scan_data_filenames, ignore_columns=calibration_configuration['ignore_columns'], fei4b=fei4b)


def mask_columns(pixel_array, ignore_columns):
    idx = np.array(ignore_columns) - 1  # from FE to Array columns
    m = np.zeros_like(pixel_array)
    m[:, idx] = 1
    return np.ma.masked_array(pixel_array, m)


if __name__ == "__main__":
    scan_id = 'calibrate_threshold_gdac'
    startTime = datetime.now()
#     reanalyze()
    logging.info('Taking threshold data at following GDACs: %s' % str(calibration_configuration['gdacs']))
    scan_data_filenames = {}
    scan_threshold_fast = FastThresholdScan(**configuration.default_configuration)
    for i, gdac_value in enumerate(calibration_configuration['gdac_range']):
        scan_threshold_fast.register_utils.set_gdac(gdac_value)
        scan_threshold_fast.scan_id = calibration_configuration['scan_id'] + '_' + str(gdac_value)
        scan_threshold_fast.start(configure=True, scan_parameter_range=(scan_threshold_fast.scan_parameter_start, 800), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=scan_threshold_fast.data_points - 2, ignore_columns=calibration_configuration['ignore_columns'])
        scan_threshold_fast.stop()
        scan_data_filenames[gdac_value] = scan_threshold_fast.scan_data_filename

    logging.info("Calibration finished in " + str(datetime.now() - startTime))

#     analyze and plot the data from all scans
    create_calibration(calibration_configuration['scan_id'], scan_data_filenames=scan_data_filenames, ignore_columns=calibration_configuration['ignore_columns'], fei4b=scan_threshold_fast.register.fei4b)

    logging.info("Finished!")
