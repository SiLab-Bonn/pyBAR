"""A script that changes a scan parameter (usually PlsrDAC, in inner loop) in a certain range for selected pixels and measures the length of the hit OR signal with the FPGA TDC.
This calibration can be used to measure charge information for single pixels with higher precision than with the quantized TOT information.
"""
import logging
import numpy as np
import tables as tb
import progressbar

from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4.register_utils import make_pixel_mask_from_col_row, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import scan_loop
from pybar.analysis.analysis_utils import get_scan_parameter, get_unique_scan_parameter_combinations, get_scan_parameters_table_from_meta_data, get_ranges_from_array
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves, plot_tot_tdc_calibration


class TotCalibration(Fei4RunBase):

    ''' Hit Or calibration scan
    '''
    _default_run_conf = {
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "n_injections": 25,
        "injection_delay": 5000,  # for really low feedbacks (ToT >> 300 ns) one needs to increase the injection delay
        "scan_parameters": [('PlsrDAC', [40, 50, 60, 80, 130, 180, 230, 280, 340, 440, 540, 640, 740])],  # 0 400 sufficient
        "use_enable_mask": False,
        "enable_shift_masks": ["Enable", "C_Low", "C_High"],
        "disable_shift_masks": [],
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        self.register_utils.send_commands(commands)

    def scan(self):
        scan_parameter_name = self.scan_parameters._fields[-1]  # scan parameter is in inner loop
        scan_parameters_values = self.scan_parameters[-1][:]  # create deep copy of scan_parameters, they are overwritten in self.readout
        logging.info("Scanning %s from %d to %d", scan_parameter_name, scan_parameters_values[0], scan_parameters_values[-1])

        for scan_parameter_value in scan_parameters_values:
            if self.stop_run.is_set():
                break

            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value(scan_parameter_name, scan_parameter_value)
            commands.extend(self.register.get_commands("WrRegister", name=[scan_parameter_name]))
            self.register_utils.send_commands(commands)

            with self.readout(**{scan_parameter_name: scan_parameter_value}):
                cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.injection_delay)[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, fast_dc_loop=True, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = True
            analyze_raw_data.create_mean_tot_hist = True
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

            with tb.open_file(analyze_raw_data._analyzed_data_file, 'r') as in_file_h5:
                meta_data = in_file_h5.root.meta_data[:]
                tot_mean = np.swapaxes(in_file_h5.root.HistMeanTot[:], 1, 0)
                scan_parameters_dict = get_scan_parameter(meta_data)
                inner_loop_parameter_values = scan_parameters_dict[next(reversed(scan_parameters_dict))]  # inner loop parameter name is unknown
        
                plot_tot_tdc_calibration(scan_parameters=inner_loop_parameter_values, tot_mean=tot_mean, filename=analyze_raw_data.output_pdf)
                plot_scurves(tot_mean, inner_loop_parameter_values, "ToT calibration", "ToT", 15, "Charge [PlsrDAC]", filename=analyze_raw_data.output_pdf)

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(TotCalibration)
