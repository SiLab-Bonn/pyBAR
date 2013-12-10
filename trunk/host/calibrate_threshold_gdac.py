"""A script that runs a threshold scan for different GDAC settings to get a calibration. To save time the PlsrDAC start position is the start position determined from the previous threshold scan.
After the data taking the data is analyzed and the calibration is written to h5 files.
"""
from datetime import datetime
import configuration
import tables as tb
import numpy as np
import logging

from scan_threshold_fast import ThresholdScanFast
from analysis import analysis_utils
from analysis.RawDataConverter import data_struct

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting.plotting import plotThreeWay, plot_scurves, plot_scatter
from analysis.analyze_raw_data import AnalyzeRawData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

gdac_range = range(100, 114, 1)  # has to be from low to high value
gdac_range.extend((np.exp(np.array(range(0, 150)) / 10.) / 10. + 100).astype('<u8')[50:-40].tolist())  # exponential GDAC range to correct for logarithmic threshold(GDAC) function
ignore_columns = (0, 1, 77, 78, 79)  # columns to ignore in analysis and during data taking


def analyze(raw_data_file, analyzed_data_file, FEI4B=False):
    with AnalyzeRawData(raw_data_file=raw_data_file + ".h5", analyzed_data_file=analyzed_data_file) as analyze_raw_data:
        analyze_raw_data.create_tot_hist = False
        analyze_raw_data.create_threshold_hists = True
        analyze_raw_data.create_fitted_threshold_hists = True
        analyze_raw_data.create_threshold_mask = True
        analyze_raw_data.n_injections = 100
        analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
        analyze_raw_data.interpret_word_table(FEI4B=FEI4B)
        analyze_raw_data.interpreter.print_summary()


def store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration):
    logging.info("Storing calibration data in a table...")
    filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    mean_threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='MeanThresholdCalibration', description=data_struct.MeanThresholdCalibrationTable, title='mean_threshold_calibration', filters=filter_table)
    threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='ThresholdCalibration', description=data_struct.ThresholdCalibrationTable, title='threshold_calibration', filters=filter_table)
    for column in range(0, 80):
        for row in range(0, 336):
            for gdac_index, gdac in enumerate(gdac_range):
                threshold_calib_table.row['column'] = column
                threshold_calib_table.row['row'] = row
                threshold_calib_table.row['gdac'] = gdac
                threshold_calib_table.row['threshold'] = threshold_calibration[column, row, gdac_index]
                threshold_calib_table.row.append()
    for gdac_index, gdac in enumerate(gdac_range):
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


def create_calibration(scan_identifier, is_FEI4B=False, create_plots=True):
    logging.info("Analyzing and plotting results...")
    output_h5_filename = 'data/' + scan_identifier + '.h5'
    logging.info('Saving calibration in: %s' % output_h5_filename)

    if create_plots:
        output_pdf_filename = 'data/' + scan_identifier + '.pdf'
        logging.info('Saving plot in: %s' % output_pdf_filename)
        output_pdf = PdfPages(output_pdf_filename)

    mean_threshold_calibration = np.empty(shape=(len(gdac_range),), dtype='<f8')  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration = np.empty(shape=(len(gdac_range),), dtype='<f8')  # array to hold the analyzed data in ram
    threshold_calibration = np.empty(shape=(80, 336, len(gdac_range)), dtype='<f8')  # array to hold the analyzed data in ram

    for gdac_index, gdac in enumerate(gdac_range):
        logging.info("Analyzing GDAC %d, progress %d %%" % (gdac, int(float(float(gdac_index) / float(len(gdac_range)) * 100.))))
        raw_data_file = 'data/' + scan_identifier + '_' + str(gdac) + "_0"
        analyzed_data_file = raw_data_file + '_interpreted.h5'
        analyze(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file, FEI4B=is_FEI4B)
        with tb.openFile(analyzed_data_file, mode="r") as in_file_h5:
            # mask the not scanned columns for analysis and plotting
            occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)
            thresholds_masked = mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns)
            # plot the threshold distribution and the s curves
            if create_plots:
                plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for GDAC = ' + str(gdac), filename=output_pdf)
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_parameters = parameter_settings['PlsrDAC']
            if create_plots:
                plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_paramter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[gdac_index] = np.ma.mean(thresholds_masked)
#             mean_threshold_rms_calibration[gdac_index] = np.ma.sqrt(np.ma.mean((thresholds_masked - mean_threshold_calibration[gdac_index]) ** 2))  # TODO: use numpy.ma.std here?
            mean_threshold_rms_calibration[gdac_index] = np.ma.std(thresholds_masked)
            for column in range(0, 80):
                for row in range(0, 336):
                    threshold_calibration[column, row, gdac_index] = thresholds_masked[row, column]
    if create_plots:
        plot_scurves(occupancy_hist=threshold_calibration, scan_parameters=gdac_range, title='Thresholds', ylabel='Threshold', scan_paramter_name='GDAC', filename=output_pdf)
        plot_scatter(x=gdac_range, y=mean_threshold_calibration, title='Threshold calibration', x_label='GDAC', y_label='Mean threshold', log_x=False, filename=output_pdf)
        plot_scatter(x=gdac_range, y=mean_threshold_calibration, title='Threshold calibration', x_label='GDAC', y_label='Mean threshold', log_x=True, filename=output_pdf)
        plot_scatter(x=gdac_range, y=mean_threshold_rms_calibration, title='Threshold calibration', x_label='GDAC', y_label='Threshold RMS', log_x=False, filename=output_pdf)
        plot_scatter(x=gdac_range, y=mean_threshold_rms_calibration, title='Threshold calibration', x_label='GDAC', y_label='Threshold RMS', log_x=True, filename=output_pdf)
        output_pdf.close()

    # store the calibration data into a hdf5 file as an easy to read table and as an array for quick data access
    with tb.openFile(output_h5_filename, mode="w") as out_file_h5:
        store_calibration_data_as_array(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)
        store_calibration_data_as_table(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)


def mask_columns(pixel_array, ignore_columns):
    idx = np.array(ignore_columns)
    m = np.zeros_like(pixel_array)
    m[:, idx] = 1
    return np.ma.masked_array(pixel_array, m)


def set_gdac(value, register, register_utils):
    commands = []
    commands.extend(register.get_commands("confmode"))
    register.set_global_register_value("Vthin_AltFine", value & 255)  # take low word
    register.set_global_register_value("Vthin_AltCoarse", value >> 8)  # take high word
    commands.extend(register.get_commands("wrregister", name=["Vthin_AltFine", "Vthin_AltCoarse"]))
    commands.extend(register.get_commands("runmode"))
    register_utils.send_commands(commands)
    logging.info("Set GDAC to VthinAC/VthinAF = %d/%d" % (register.get_global_register_value("Vthin_AltCoarse"), register.get_global_register_value("Vthin_AltFine")))

if __name__ == "__main__":
    scan_identifier = "calibrate_threshold_gdac"

    startTime = datetime.now()

    scan_threshold_fast = ThresholdScanFast(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    for i, gdac in enumerate(gdac_range):
        set_gdac(gdac, scan_threshold_fast.register, scan_threshold_fast.register_utils)
        scan_threshold_fast.scan_identifier = scan_identifier + '_' + str(gdac)
        scan_threshold_fast.start(configure=True, scan_parameter_range=(scan_threshold_fast.scan_parameter_start, 800), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=10, ignore_columns=ignore_columns)
        scan_threshold_fast.stop()

    logging.info("Calibration finished in " + str(datetime.now() - startTime))

#  analyze and plot the data from all scans
    create_calibration(scan_identifier, is_FEI4B=False, create_plots=True)

    logging.info("Finished!")
