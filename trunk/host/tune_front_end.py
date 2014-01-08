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


def tune_front_end(cfg_name, target_threshold=20, target_charge=270, target_tot=7, global_iterations=3, local_iterations=2, create_plots=True):
    '''Metascript that calls other scripts to tune the FE.

    Parameters
    ----------
    cfg_name : string
        Name of the config to be created. This config holds the tuning results.
    target_threshold : int
        The target threshold value in PlsrDAC.
    target_charge : int
        The target charge in PlsrDAC value to tune to.
    target_tot : int
        The target tot value to tune to.
    global_iterations : int
        Defines how often global threshold/global feedback current tuning is repeated.
        -1: the global tuning is disabled
        0: the global tuning consists of the global threshold tuning only
        1: global threshold/global feedback current/global threshold tuning
        2: global threshold/global feedback current/global threshold tuning/global feedback current/global threshold tuning
        ...
    local_iterations : int
        Defines how often local threshold (TDAC) / feedback current (FDAC) tuning is repeated.
            -1: the local tuning is disabled
            0: the local tuning consists of the local threshold tuning only (TDAC)
            1: TDAC/FDAC/TDAC
            2: TDAC/FDAC/TDAC/FDAC/TDAC
            ...
    '''
    gdac_tune_scan = GdacTune(configuration_file=configuration.configuration_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    gdac_tune_scan.set_target_threshold(target_threshold)

    feedback_tune_scan = FeedbackTune(configuration_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    feedback_tune_scan.set_target_charge(target_charge)
    feedback_tune_scan.set_target_tot(target_tot)

    tdac_tune_scan = TdacTune(configuration_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    tdac_tune_scan.set_target_threshold(target_threshold)
    tdac_tune_scan.set_start_tdac()  # set TDAC = 0
    tdac_tune_scan.set_tdac_bit(bit_position=4, bit_value=1)  # set start value TDAC = 16

    fdac_tune_scan = FdacTune(configuration_file=gdac_tune_scan.register, bit_file=None, scan_data_path=configuration.scan_data_path, device=gdac_tune_scan.device)
    fdac_tune_scan.set_target_charge(target_charge)
    fdac_tune_scan.set_target_tot(target_tot)
    fdac_tune_scan.set_start_fdac()  # set FDAC = 0
    fdac_tune_scan.set_fdac_bit(bit_position=3, bit_value=1)  # set start value FDAC = 8

    difference_bit = 1

    if create_plots:
        output_pdf_filename = os.path.join(configuration.scan_data_path, cfg_name)
        output_pdf = PdfPages(output_pdf_filename + '.pdf')

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

    if create_plots:
        if(local_iterations > 0):
            plotThreeWay(hist=fdac_tune_scan.register.get_pixel_register_value("FDAC").transpose(), title="FDAC distribution after last FDAC tuning", x_axis_title='FDAC', filename=output_pdf, maximum=16)
            plotThreeWay(hist=fdac_tune_scan.result.transpose(), title="Mean ToT after last FDAC tuning", x_axis_title='mean ToT', filename=output_pdf)
        if(global_iterations > 0):
            plotThreeWay(hist=tdac_tune_scan.register.get_pixel_register_value("TDAC").transpose(), title="TDAC distribution after complete tuning", x_axis_title='TDAC', filename=output_pdf, maximum=32)
            plotThreeWay(hist=tdac_tune_scan.result.transpose(), title="Occupancy after complete tuning", x_axis_title='Occupancy', filename=output_pdf, maximum=100)
        output_pdf.close()

if __name__ == "__main__":
    startTime = datetime.now()
    tune_front_end(cfg_name='tuned_config', target_threshold=20, target_charge=270, target_tot=7, global_iterations=3, local_iterations=2)
    logging.info("Tuning finished in " + str(datetime.now() - startTime))
