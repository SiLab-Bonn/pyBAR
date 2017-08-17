import logging

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, logical_and, data_array_from_data_iterable, get_col_row_tot_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_three_way


class FdacTuning(Fei4RunBase):
    '''FDAC Tuning

    Tuning the FDAC to target ToT at given charge (charge is given in units of PlsrDAC).

    The tuning uses a binary search algorithm. Bit 0 is always scanned twice with value 1 and 0. Due to the nonlinearity it can happen that the binary search does not give the best result.
    Pixel below threshold are set to ToT = 0.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "broadcast_commands": False,
        "threaded_scan": False,
        "scan_parameters": [('FDAC', None)],
        "target_charge": 280,
        "target_tot": 5,
        "fdac_tune_bits": range(3, -1, -1),
        "n_injections_fdac": 30,
        "plot_intermediate_steps": False,
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

        self.plots_filename = PdfPages(self.output_filename + '.pdf')
        self.close_plots = True

    def scan(self):
        enable_mask_steps = []

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

        self.write_target_charge()
        additional_scan = True
        lastBitResult = np.zeros(shape=self.register.get_pixel_register_value("FDAC").shape, dtype=self.register.get_pixel_register_value("FDAC").dtype)

        self.set_start_fdac()

        self.tot_mean_best = np.full(shape=(80, 336), fill_value=0)  # array to store the best occupancy (closest to Ninjections/2) of the pixel
        self.fdac_mask_best = self.register.get_pixel_register_value("FDAC")
        fdac_tune_bits = self.fdac_tune_bits[:]
        for scan_parameter_value, fdac_bit in enumerate(fdac_tune_bits):
            if self.stop_run.is_set():
                break
            if additional_scan:
                self.set_fdac_bit(fdac_bit)
                logging.info('FDAC setting: bit %d = 1', fdac_bit)
            else:
                self.set_fdac_bit(fdac_bit, bit_value=0)
                logging.info('FDAC setting: bit %d = 0', fdac_bit)

            self.write_fdac_config()

            with self.readout(FDAC=scan_parameter_value, fill_buffer=True):
                scan_loop(self,
                          command=cal_lvl1_command,
                          repeat_command=self.n_injections_fdac,
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

            data = convert_data_array(array=self.read_data(fe_word_filter=True), filter_func=is_data_record, converter_func=get_col_row_tot_array_from_data_record_array)
            col_row_tot = np.column_stack(data)
            tot_array = np.histogramdd(col_row_tot, bins=(80, 336, 16), range=[[1, 80], [1, 336], [0, 15]])[0]
            tot_mean_array = np.average(tot_array, axis=2, weights=range(0, 16)) * sum(range(0, 16)) / self.n_injections_fdac
            select_better_pixel_mask = abs(tot_mean_array - self.target_tot) <= abs(self.tot_mean_best - self.target_tot)
            pixel_with_too_small_mean_tot_mask = tot_mean_array < self.target_tot
            self.tot_mean_best[select_better_pixel_mask] = tot_mean_array[select_better_pixel_mask]

            if self.plot_intermediate_steps:
                plot_three_way(hist=tot_mean_array.transpose().transpose(), title="Mean ToT (FDAC tuning bit " + str(fdac_bit) + ")", x_axis_title='mean ToT', filename=self.plots_filename, minimum=0, maximum=15)

            fdac_mask = self.register.get_pixel_register_value("FDAC")
            self.fdac_mask_best[select_better_pixel_mask] = fdac_mask[select_better_pixel_mask]
            if fdac_bit > 0:
                fdac_mask[pixel_with_too_small_mean_tot_mask] = fdac_mask[pixel_with_too_small_mean_tot_mask] & ~(1 << fdac_bit)
                self.register.set_pixel_register_value("FDAC", fdac_mask)

            if fdac_bit == 0:
                if additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    lastBitResult = tot_mean_array.copy()
                    fdac_tune_bits.append(0)  # bit 0 has to be scanned twice
                else:
                    fdac_mask[abs(tot_mean_array - self.target_tot) > abs(lastBitResult - self.target_tot)] = fdac_mask[abs(tot_mean_array - self.target_tot) > abs(lastBitResult - self.target_tot)] | (1 << fdac_bit)
                    tot_mean_array[abs(tot_mean_array - self.target_tot) > abs(lastBitResult - self.target_tot)] = lastBitResult[abs(tot_mean_array - self.target_tot) > abs(lastBitResult - self.target_tot)]
                    self.tot_mean_best[abs(tot_mean_array - self.target_tot) <= abs(self.tot_mean_best - self.n_injections_fdac / 2)] = tot_mean_array[abs(tot_mean_array - self.target_tot) <= abs(self.tot_mean_best - self.n_injections_fdac / 2)]
                    self.fdac_mask_best[abs(tot_mean_array - self.target_tot) <= abs(self.tot_mean_best - self.n_injections_fdac / 2)] = fdac_mask[abs(tot_mean_array - self.target_tot) <= abs(self.tot_mean_best - self.n_injections_fdac / 2)]

        self.register.set_pixel_register_value("FDAC", self.fdac_mask_best)  # set value for meta scan
        self.write_fdac_config()

    def analyze(self):
        # set here because original value is restored after scan()
        self.register.set_pixel_register_value("FDAC", self.fdac_mask_best)

        plot_three_way(hist=self.tot_mean_best.transpose(), title="Mean ToT after FDAC tuning", x_axis_title="Mean ToT", filename=self.plots_filename, minimum=0, maximum=15)
        plot_three_way(hist=self.fdac_mask_best.transpose(), title="FDAC distribution after tuning", x_axis_title="FDAC", filename=self.plots_filename, minimum=0, maximum=15)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_charge(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_charge)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_fdac_bit(self, bit_position, bit_value=1):
        if bit_value == 1:
            self.register.set_pixel_register_value("FDAC", self.register.get_pixel_register_value("FDAC") | (1 << bit_position))
        else:
            self.register.set_pixel_register_value("FDAC", self.register.get_pixel_register_value("FDAC") & ~(1 << bit_position))

    def write_fdac_config(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=["FDAC"]))
        self.register_utils.send_commands(commands)

    def set_start_fdac(self):
        start_fdac_setting = self.register.get_pixel_register_value("FDAC")
        for bit_position in self.fdac_tune_bits:  # reset all FDAC bits, TODO: speed up
            start_fdac_setting = start_fdac_setting & ~(1 << bit_position)
        self.register.set_pixel_register_value("FDAC", start_fdac_setting)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(FdacTuning)
