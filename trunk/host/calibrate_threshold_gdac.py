"""A script that runs a threshold scan for different GDAC settings to get a calibration. To save time the start position is the start position determined from the previous threshold scan.
"""
from datetime import datetime
import configuration
import logging
import os

import tables as tb
import numpy as np

from scan_threshold_fast import ThresholdScanFast
from analysis.analysis_utils import AnalysisUtils
from analysis.RawDataConverter import data_struct

from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting.plotting import plotThreeWay,plot_scurves

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

gdac_range = range(100, 689, 15)  # has to be from low to high value
ignore_columns = (0, 1, 77, 78, 79)  # columns to ignore in analysis and during data taking


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
    startTime = datetime.now()

#     scan_threshold_fast = ThresholdScanFast(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan_identifier = "calibrate_threshold_gdac"
#     for i, gdac in enumerate(gdac_range):
#         set_gdac(gdac, scan_threshold_fast.register, scan_threshold_fast.register_utils)
#         scan_threshold_fast.scan_identifier = scan_identifier + '_' + str(gdac)
#         scan_threshold_fast.start(configure=True, scan_parameter_range=(scan_threshold_fast.scan_parameter_start, 800), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=10, ignore_columns=ignore_columns)
#         scan_threshold_fast.stop()
#         scan_threshold_fast.analyze(create_plots=False)  # for stability do not plot data

    logging.info("Calibration finished in " + str(datetime.now() - startTime))

# plot and analyze the data from all scans
    logging.info("Analyzing and plotting results...")
    output_h5_filename = 'data/' + scan_identifier + '.h5'
    output_pdf_filename = 'data/' + scan_identifier + '.pdf'
    logging.info('Saving calibration in: %s' % output_h5_filename)
    logging.info('Saving plot in: %s' % output_pdf_filename)
    output_pdf = PdfPages(output_pdf_filename)

    mean_threshold_calibration = np.empty(shape=(len(gdac_range), ), dtype='<f8')  # array to hold the analyzed data in ram, t store it in a table in different order
    threshold_calibration = np.empty(shape=(80, 336, len(gdac_range)), dtype='<f8')  # array to hold the analyzed data in ram, t store it in a table in different order

    for gdac_index, gdac in enumerate(gdac_range):
        logging.info("Analysing GDAC %d" % gdac)
        file_name = 'data/' + scan_identifier + '_' + str(gdac) + '_0_interpreted.h5'
        with tb.openFile(file_name, mode="r") as in_file_h5:
            # mask the not scanned columns for analysis and plotting
            occupancy = in_file_h5.root.HistOcc[:]
            idx = np.array(ignore_columns)
            m = np.zeros_like(occupancy)
            m[:, idx] = 1
            occupancy_masked = np.ma.masked_array(occupancy, m)
            thresholds = in_file_h5.root.HistThresholdFitted[:]
            n = np.zeros_like(thresholds)
            n[:, idx] = 1
            thresholds_masked = np.ma.masked_array(thresholds, n)
            # plot the threshold distribution and the s curves
            plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for GDAC = ' + str(gdac), filename=output_pdf)
            analysis_utils = AnalysisUtils()
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_parameters = parameter_settings['PlsrDAC']
            plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_paramter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[gdac_index] = np.ma.mean(thresholds_masked)
            for column in range(0, 80):
                for row in range(0, 336):
                    threshold_calibration[column, row, gdac_index] = thresholds_masked[row, column]
    output_pdf.close()

    # store the calibration data into hdf5 files, resort them
    with tb.openFile(output_h5_filename, mode="w") as out_file_h5:
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
            mean_threshold_calib_table.row.append()

        threshold_calib_table.flush()
        mean_threshold_calib_table.flush()

    logging.info("Finished!")

 
# 
#     for gdac in gdac_range:
#         file_name = 'data/' + scan_identifier + '_' + str(gdac) + '_0_interpreted.h5'
#         with tb.openFile(file_name, mode="r") as in_file_h5:
#             # mask the not scanned columns for analysis, plotting
#             occupancy = in_file_h5.root.HistOcc[:]
#             idx = np.array(ignore_columns)
#             m = np.zeros_like(occupancy)
#             m[:, idx] = 1
#             occupancy_masked = np.ma.masked_array(occupancy, m)
#             thresholds = in_file_h5.root.HistThresholdFitted[:]
#             n = np.zeros_like(thresholds)
#             n[:, idx] = 1
#             thresholds_masked = np.ma.masked_array(thresholds, n)
# 
#             # plot the threshold distribution and the s curves
#             plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for GDAC = ' + str(gdac), filename=output_pdf)
#             analysis_utils = AnalysisUtils()
#             meta_data_array = in_file_h5.root.meta_data[:]
#             parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
#             scan_parameters = parameter_settings['PlsrDAC']
#             plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_paramter_name='PlsrDAC', filename=output_pdf)
# 

    