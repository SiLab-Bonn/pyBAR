import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, is_fe_word, logical_and, data_array_from_data_iterable, get_col_row_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_three_way


class TdacTuning(Fei4RunBase):
    '''TDAC Tuning

    Tuning the TDAC to target threshold value (threshold is given in units of PlsrDAC).
    The tuning uses a binary search algorithm. Bit 0 is always scanned twice with value 1 and 0. Due to the nonlinearity it can happen that the binary search does not give the best result.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "scan_parameters": [('TDAC', None)],
        "target_threshold": 30,
        "tdac_tune_bits": range(4, -1, -1),
        "n_injections_tdac": 100,
        "plot_intermediate_steps": False,
        "plots_filename": None,
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "same_mask_for_all_dc": True  # Increases scan speed, should be deactivated for very noisy FE
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
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        if not self.plots_filename:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
            self.close_plots = True
        else:
            self.close_plots = False

        enable_mask_steps = []
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=self.mask_steps)[0]

        self.write_target_threshold()
        additional_scan = True
        lastBitResult = np.zeros(shape=self.register.get_pixel_register_value("TDAC").shape, dtype=self.register.get_pixel_register_value("TDAC").dtype)

        self.set_start_tdac()

        self.occupancy_best = np.full(shape=(80, 336), fill_value=self.n_injections_tdac)  # array to store the best occupancy (closest to Ninjections/2) of the pixel
        self.tdac_mask_best = self.register.get_pixel_register_value("TDAC")
        tdac_tune_bits = self.tdac_tune_bits[:]
        for scan_parameter_value, tdac_bit in enumerate(tdac_tune_bits):
            if additional_scan:
                self.set_tdac_bit(tdac_bit)
                logging.info('TDAC setting: bit %d = 1', tdac_bit)
            else:
                self.set_tdac_bit(tdac_bit, bit_value=0)
                logging.info('TDAC setting: bit %d = 0', tdac_bit)

            self.write_tdac_config()

            with self.readout(TDAC=scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                scan_loop(self,
                          cal_lvl1_command,
                          repeat_command=self.n_injections_tdac,
                          mask_steps=self.mask_steps,
                          enable_mask_steps=enable_mask_steps,
                          enable_double_columns=None,
                          same_mask_for_all_dc=self.same_mask_for_all_dc,
                          eol_function=None,
                          digital_injection=False,
                          enable_shift_masks=self.enable_shift_masks,
                          disable_shift_masks=self.disable_shift_masks,
                          restore_shift_masks=True,
                          mask=None,
                          double_column_correction=self.pulser_dac_correction)

            occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=logical_and(is_fe_word, is_data_record), converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
            select_better_pixel_mask = abs(occupancy_array - self.n_injections_tdac / 2) <= abs(self.occupancy_best - self.n_injections_tdac / 2)
            pixel_with_too_high_occupancy_mask = occupancy_array > self.n_injections_tdac / 2
            self.occupancy_best[select_better_pixel_mask] = occupancy_array[select_better_pixel_mask]

            if self.plot_intermediate_steps:
                plot_three_way(occupancy_array.transpose(), title="Occupancy (TDAC tuning bit " + str(tdac_bit) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_tdac)

            tdac_mask = self.register.get_pixel_register_value("TDAC")
            self.tdac_mask_best[select_better_pixel_mask] = tdac_mask[select_better_pixel_mask]

            if tdac_bit > 0:
                tdac_mask[pixel_with_too_high_occupancy_mask] = tdac_mask[pixel_with_too_high_occupancy_mask] & ~(1 << tdac_bit)
                self.register.set_pixel_register_value("TDAC", tdac_mask)

            if tdac_bit == 0:
                if additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    lastBitResult = occupancy_array.copy()
                    tdac_tune_bits.append(0)  # bit 0 has to be scanned twice
                else:
                    tdac_mask[abs(occupancy_array - self.n_injections_tdac / 2) > abs(lastBitResult - self.n_injections_tdac / 2)] = tdac_mask[abs(occupancy_array - self.n_injections_tdac / 2) > abs(lastBitResult - self.n_injections_tdac / 2)] | (1 << tdac_bit)
                    occupancy_array[abs(occupancy_array - self.n_injections_tdac / 2) > abs(lastBitResult - self.n_injections_tdac / 2)] = lastBitResult[abs(occupancy_array - self.n_injections_tdac / 2) > abs(lastBitResult - self.n_injections_tdac / 2)]
                    self.occupancy_best[abs(occupancy_array - self.n_injections_tdac / 2) <= abs(self.occupancy_best - self.n_injections_tdac / 2)] = occupancy_array[abs(occupancy_array - self.n_injections_tdac / 2) <= abs(self.occupancy_best - self.n_injections_tdac / 2)]
                    self.tdac_mask_best[abs(occupancy_array - self.n_injections_tdac / 2) <= abs(self.occupancy_best - self.n_injections_tdac / 2)] = tdac_mask[abs(occupancy_array - self.n_injections_tdac / 2) <= abs(self.occupancy_best - self.n_injections_tdac / 2)]

        self.register.set_pixel_register_value("TDAC", self.tdac_mask_best)  # set value for meta scan
        self.write_tdac_config()

#         # additional analog scan to get final results, not needed, just for checking
#         logging.info('Do analog scan with actual TDAC settings after TDAC tuning')
#         self.write_tdac_config()
#         self.readout.start()
#         cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
#         self.scan_loop(cal_lvl1_command, repeat_command=self.n_injections_tdac, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)
#         self.readout.stop()
#         occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
#         plot_three_way(hist=occupancy_array.transpose(), title="Occupancy check", x_axis_title="Occupancy", filename=plots_filename, maximum = self.n_injections_tdac)
#         plot_three_way(hist=self.register.get_pixel_register_value("TDAC").transpose(), title="TDAC check distribution after tuning", x_axis_title="TDAC", filename=plots_filename, maximum = 32)

    def analyze(self):
        # set here because original value is restored after scan()
        self.register.set_pixel_register_value("TDAC", self.tdac_mask_best)

        plot_three_way(hist=self.occupancy_best.transpose(), title="Occupancy after TDAC tuning", x_axis_title="Occupancy", filename=self.plots_filename, maximum=self.n_injections_tdac)
        plot_three_way(hist=self.tdac_mask_best.transpose(), title="TDAC distribution after tuning", x_axis_title="TDAC", filename=self.plots_filename, maximum=32)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_tdac_bit(self, bit_position, bit_value=1):
        if(bit_value == 1):
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC") | (1 << bit_position))
        else:
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC") & ~(1 << bit_position))

    def set_start_tdac(self):
        start_tdac_setting = self.register.get_pixel_register_value("TDAC")
        for bit_position in self.tdac_tune_bits:  # reset all TDAC bits, FIXME: speed up
            start_tdac_setting = start_tdac_setting & ~(1 << bit_position)
        self.register.set_pixel_register_value("TDAC", start_tdac_setting)

    def write_tdac_config(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=["TDAC"]))
        self.register_utils.send_commands(commands)

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(TdacTuning)
