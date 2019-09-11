"""This script is providing a ToT calibration scan.
The ToT calibration (mean ToT for each scan step) per pixel can be accessed via HistMeanTot from the interpreted hits file.
"""
import logging

import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import scan_loop, invert_pixel_mask
from pybar.analysis.analysis_utils import get_scan_parameter
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves, plot_tot_tdc_calibration


class TotCalibration(Fei4RunBase):
    ''' ToT calibration scan
    '''
    _default_run_conf = {
        "broadcast_commands": True,
        "mask_steps": 3,  # mask steps, the injected charge depends on the mask steps
        "n_injections": 200,  # number of injections per PlsrDAC, for higher precision close to the threshold increase n_injections
        "scan_parameters": [('PlsrDAC', [40, 50, 60, 80, 130, 180, 230, 280, 340, 440, 540, 640, 740])],  # 0 400 sufficient for most tunings
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_Low", "C_High"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in list(map(lambda x: x.lower(), self.enable_shift_masks)):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in list(map(lambda x: x.lower(), self.enable_shift_masks)):
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
                cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, fast_dc_loop=True, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = True
            analyze_raw_data.create_mean_tot_hist = True
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

            meta_data = analyze_raw_data.out_file_h5.root.meta_data[:]
            tot_mean = np.swapaxes(analyze_raw_data.out_file_h5.root.HistMeanTot[:], 1, 0)
            scan_parameters_dict = get_scan_parameter(meta_data)
            inner_loop_parameter_values = scan_parameters_dict[next(reversed(scan_parameters_dict))]  # inner loop parameter name is unknown
            # calculate mean ToT arrays
            tot_mean_all_pix = np.nanmean(tot_mean, axis=(0, 1))
            tot_error_all_pix = np.nanstd(tot_mean, axis=(0, 1))
            plot_scurves(tot_mean, inner_loop_parameter_values, "ToT calibration", "ToT", 15, "Charge [PlsrDAC]", filename=analyze_raw_data.output_pdf)
            plot_tot_tdc_calibration(scan_parameters=inner_loop_parameter_values, tot_mean=tot_mean_all_pix, tot_error=tot_error_all_pix, filename=analyze_raw_data.output_pdf, title="Mean charge calibration of %d pixel(s)" % np.count_nonzero(~np.all(np.isnan(tot_mean), axis=2)))
            # selecting pixels with non-nan entries
            col_row_non_nan = np.nonzero(~np.all(np.isnan(tot_mean), axis=2))
            plot_pixel_calibrations = np.dstack(col_row_non_nan)[0]
            # generate index array
            pixel_indices = np.arange(plot_pixel_calibrations.shape[0])
            plot_n_pixels = 10  # number of pixels at the beginning, center and end of the array
            np.random.seed(0)
            if pixel_indices.size - 2 * plot_n_pixels >= 0:
                random_pixel_indices = np.sort(np.random.choice(pixel_indices[plot_n_pixels:-plot_n_pixels], min(plot_n_pixels, pixel_indices.size - 2 * plot_n_pixels), replace=False))
            else:
                random_pixel_indices = np.array([], dtype=np.int)
            selected_pixel_indices = np.unique(np.hstack([pixel_indices[:plot_n_pixels], random_pixel_indices, pixel_indices[-plot_n_pixels:]]))
            # plotting individual pixels
            for (column, row) in plot_pixel_calibrations[selected_pixel_indices]:
                logging.info("Plotting charge calibration for pixel column " + str(column + 1) + " / row " + str(row + 1))
                tot_mean_single_pix = tot_mean[column, row, :]
                plot_tot_tdc_calibration(scan_parameters=inner_loop_parameter_values, tot_mean=tot_mean_single_pix, filename=analyze_raw_data.output_pdf, title="Charge calibration for pixel column " + str(column + 1) + " / row " + str(row + 1))


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(TotCalibration)
