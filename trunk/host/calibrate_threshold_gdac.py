"""A script that runs a threshold scan for different GDAC settings to get a calibration. To save time the start position is the start position determined from the previous threshold scan.
"""
from datetime import datetime
import configuration
import logging
import os

import tables as tb

from scan_threshold_fast import ThresholdScanFast
from analysis.analysis_utils import AnalysisUtils

from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting.plotting import plotThreeWay,plot_scurves

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

gdac_range = range(100, 101, 10)  # has to be from low to high value


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

    scan_threshold_fast = ThresholdScanFast(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan_identifier = "calibrate_threshold_gdac"
    for i, gdac in enumerate(gdac_range):
        set_gdac(gdac, scan_threshold_fast.register, scan_threshold_fast.register_utils)
        scan_threshold_fast.scan_identifier = scan_identifier + '_' + str(gdac)
        scan_threshold_fast.start(configure=True, scan_parameter_range=(scan_threshold_fast.scan_parameter_start, 800), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=10)
        scan_threshold_fast.stop()
        scan_threshold_fast.analyze(create_plots=False)  # for stability do not plot data

    logging.info("Calibration finished in " + str(datetime.now() - startTime))
    logging.info("Plotting results...")

    output_pdf_filename = 'data/' + scan_identifier + '.pdf'
    logging.info('Saving output file: %s' % output_pdf_filename)
    output_pdf = PdfPages(output_pdf_filename)
    for gdac in gdac_range:
        file_name = 'data/' + scan_identifier + '_' + str(gdac) + '_0_interpreted.h5'
        with tb.openFile(file_name, mode="r") as in_file_h5:
            occupancy = in_file_h5.root.HistOcc[:]
            thresholds = in_file_h5.root.HistThresholdFitted[:]
            plotThreeWay(hist=thresholds, title='Threshold Fitted for GDAC = ' + str(gdac), filename=output_pdf)
            analysis_utils = AnalysisUtils()
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_paramter_name = 'PlsrDAC'
            scan_parameters = parameter_settings[scan_paramter_name]
            plot_scurves(occupancy_hist=occupancy, scan_parameters=scan_parameters, scan_paramter_name=scan_paramter_name, filename=output_pdf)
    output_pdf.close()
    logging.info("Finished!")
    