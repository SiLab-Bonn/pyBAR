"""Full tuning of the FE chip (global and pixel registers) to target values defined below. This script just runs other scripts which will do the work.
"""
from datetime import datetime
import configuration
import logging
import os

from tune_gdac import GdacTune
from tune_feedback import FeedbackTune
from tune_tdac import TdacTune
from tune_fdac import FdacTune
from analysis.plotting.plotting import plotThreeWay

from matplotlib.backends.backend_pdf import PdfPages

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

# threshold
target_threshold = 50  # in PlsrDAC
# gain
target_charge = 270  # in PlsrDAC
target_tot = 5  # ToT code
# iteration of tunings
global_iterations = 3  # set -1..5, 0 is global threshold tuning only, -1 disables global tuning
local_iterations = 1  # set -1..5, 0 is local threshold tuning only, -1 disables local tuning
# configuration filename
cfg_name = "new_tuning"

if __name__ == "__main__":
    startTime = datetime.now()

    gdac_tune_scan = GdacTune(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    gdac_tune_scan.set_target_threshold(target_threshold)

    feedback_tune_scan = FeedbackTune(config_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    feedback_tune_scan.set_target_charge(target_charge)
    feedback_tune_scan.set_target_tot(target_tot)

    tdac_tune_scan = TdacTune(config_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    tdac_tune_scan.set_target_threshold(target_threshold)
    tdac_tune_scan.set_start_tdac()  # set TDAC = 0
    tdac_tune_scan.set_tdac_bit(bit_position=4, bit_value=1)  # set start value TDAC = 16

    fdac_tune_scan = FdacTune(config_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    fdac_tune_scan.set_target_charge(target_charge)
    fdac_tune_scan.set_target_tot(target_tot)
    fdac_tune_scan.set_start_fdac()  # set FDAC = 0
    fdac_tune_scan.set_fdac_bit(bit_position=3, bit_value=1)  # set start value FDAC = 8

    difference_bit = 1

    output_pdf_filename = os.path.join(configuration.scan_data_path, cfg_name)
    output_pdf = PdfPages(output_pdf_filename + '.pdf')

    PrmpVbpf = 0
    Vthin_AC = 0
    Vthin_AF = 0

    start_bit = 7
    for iteration in range(0, global_iterations):  # tune iteratively with decreasing range to save time
        start_bit = 7 - difference_bit * iteration
        logging.info("Global tuning iteration step %d" % iteration)
        gdac_tune_scan.set_gdac_tune_bits(range(start_bit, -1, -1))
        feedback_tune_scan.set_feedback_tune_bits(range(start_bit, -1, -1))
        gdac_tune_scan.start(configure=True, plots_filename=output_pdf)
        gdac_tune_scan.stop()
        feedback_tune_scan.start(configure=True, plots_filename=output_pdf)
        feedback_tune_scan.stop()

    if global_iterations >= 0:
        gdac_tune_scan.set_gdac_tune_bits(range(start_bit, -1, -1))  # needed to reset the last extra bit 0 = 0 test
        gdac_tune_scan.start(configure=True, plots_filename=output_pdf)
        gdac_tune_scan.stop()

    Vthin_AC = gdac_tune_scan.register.get_global_register_value("Vthin_AltCoarse")
    Vthin_AF = gdac_tune_scan.register.get_global_register_value("Vthin_AltFine")
    PrmpVbpf = feedback_tune_scan.register.get_global_register_value("PrmpVbpf")
    logging.info("Results of global tuning PrmpVbpf/Vthin_AltCoarse,Vthin_AltFine = %d/%d,%d" % (PrmpVbpf, Vthin_AC, Vthin_AF))

    difference_bit = int(5 / (local_iterations if local_iterations > 0 else 1))

    start_bit = 4
    for iteration in range(0, local_iterations):  # tune iteratively
        logging.info("Local tuning iteration step %d" % iteration)
        start_bit = 4  # -difference_bit*iteration
        tdac_tune_scan.set_tdac_tune_bits(range(start_bit, -1, -1))
        fdac_tune_scan.set_fdac_tune_bits(range(start_bit - 1, -1, -1))
        tdac_tune_scan.start(configure=True, plots_filename=output_pdf)
        tdac_tune_scan.stop()
        fdac_tune_scan.start(configure=True, plots_filename=output_pdf)
        fdac_tune_scan.stop()

    if local_iterations >= 0:
        tdac_tune_scan.set_tdac_tune_bits(range(start_bit, -1, -1))  # needed to reset the last extra bit 0 = 0 test
        tdac_tune_scan.start(configure=True, plots_filename=output_pdf)
        tdac_tune_scan.stop()

    gdac_tune_scan.register.save_configuration(name=cfg_name)  # save the final config

    if(local_iterations > 0):
        plotThreeWay(hist=fdac_tune_scan.register.get_pixel_register_value("FDAC").transpose(), title="FDAC distribution after last FDAC tuning", x_axis_title='FDAC', filename=output_pdf, maximum=16)
        plotThreeWay(hist=fdac_tune_scan.result.transpose(), title="Mean ToT after last FDAC tuning", x_axis_title='mean ToT', filename=output_pdf)
    if(global_iterations > 0):
        plotThreeWay(hist=tdac_tune_scan.register.get_pixel_register_value("TDAC").transpose(), title="TDAC distribution after complete tuning", x_axis_title='TDAC', filename=output_pdf, maximum=32)
        plotThreeWay(hist=tdac_tune_scan.result.transpose(), title="Occupancy after complete tuning", x_axis_title='Occupancy', filename=output_pdf, maximum=100)

    output_pdf.close()
    logging.info("Tuning finished in " + str(datetime.now() - startTime))
