import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, is_fe_word, logical_and, data_array_from_data_iterable, get_col_row_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_three_way


class GdacTuningStandard(Fei4RunBase):
    '''Global Threshold Tuning

    Tuning the global threshold to target threshold value (threshold is given in units of PlsrDAC).
    The tuning uses a binary search algorithm.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "scan_parameters": [('GDAC', [255, 40])],
        "step_size": -1,  # step size of the GDAC during scan
        "target_threshold": 30,  # target threshold in PlsrDAC to tune to
        "n_injections_gdac": 50,  # number of injections per GDAC bit setting
        "max_delta_threshold": 5,  # minimum difference to the target_threshold to abort the tuning
        "enable_mask_steps_gdac": [0],  # mask steps to do per GDAC setting
        "plot_intermediate_steps": False,  # plot intermediate steps (takes time)
        "plots_filename": None,  # file name to store the plot to, if None show on screen
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "fail_on_warning": False,  # the scan throws a RuntimeWarning exception if the tuning fails
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
        self.write_target_threshold()

    def scan(self):
        if not self.plots_filename:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
            self.close_plots = True
        else:
            self.close_plots = False

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

        scan_parameter_range = [(2 ** self.register.global_registers['Vthin_AltFine']['bitlength']), 0]  # high to low
        if self.scan_parameters.GDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.GDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        scan_parameter_range = range(scan_parameter_range[0], scan_parameter_range[1] - 1, self.step_size)
        logging.info("Scanning %s from %d to %d", 'GDAC', scan_parameter_range[0], scan_parameter_range[-1])

        # calculate selected pixels from the mask and the disabled columns
        select_mask_array = np.zeros(shape=(80, 336), dtype=np.uint8)
        if not self.enable_mask_steps_gdac:
            self.enable_mask_steps_gdac = range(self.mask_steps)
        for mask_step in self.enable_mask_steps_gdac:
            select_mask_array += make_pixel_mask(steps=self.mask_steps, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        occupancy_best = 0.0
        median_occupancy_last_step = 0.0
        gdac_best = self.register_utils.get_gdac()
        for gdac_scan_step, scan_parameter_value in enumerate(scan_parameter_range):
            self.register_utils.set_gdac(scan_parameter_value)
            with self.readout(GDAC=scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                scan_loop(self,
                          command=cal_lvl1_command,
                          repeat_command=self.n_injections_gdac,
                          mask_steps=self.mask_steps,
                          enable_mask_steps=self.enable_mask_steps_gdac,
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
            occ_array_sel_pixels = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by using the mask
            occ_array_desel_pixels = np.ma.array(occupancy_array, mask=np.ma.make_mask(select_mask_array))  # take only de-selected pixel into account by using the inverted mask
            median_occupancy = np.ma.median(occ_array_sel_pixels)
            noise_occupancy = np.ma.median(occ_array_desel_pixels)
            occupancy_almost_zero = np.allclose(median_occupancy, 0)
            no_noise = np.allclose(noise_occupancy, 0)
            if no_noise and not occupancy_almost_zero and abs(median_occupancy - self.n_injections_gdac / 2) < abs(occupancy_best - self.n_injections_gdac / 2):
                occupancy_best = median_occupancy
                gdac_best = self.register_utils.get_gdac()
                self.occ_array_sel_pixels_best = occ_array_sel_pixels
                self.occ_array_desel_pixels_best = occ_array_desel_pixels

            if self.plot_intermediate_steps:
                plot_three_way(self.occ_array_sel_pixel.transpose(), title="Occupancy (GDAC " + str(scan_parameter_value) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)

            if no_noise and not occupancy_almost_zero and median_occupancy >= median_occupancy_last_step and median_occupancy >= self.n_injections_gdac / 2:
                break
            if no_noise and not occupancy_almost_zero:
                median_occupancy_last_step = median_occupancy
            else:
                median_occupancy_last_step = 0.0

        self.register_utils.set_gdac(gdac_best, send_command=False)
        median_occupancy = occupancy_best
        self.gdac_best = self.register_utils.get_gdac()

        if abs(median_occupancy - self.n_injections_gdac / 2) > self.max_delta_threshold:
            if np.all((((self.gdac_best & (1 << np.arange(self.register.global_registers['Vthin_AltFine']['bitlength'] + self.register.global_registers['Vthin_AltFine']['bitlength'])))) > 0).astype(int)[self.gdac_tune_bits] == 1):
                if self.fail_on_warning:
                    raise RuntimeWarning('Selected GDAC bits reached maximum value')
                else:
                    logging.warning('Selected GDAC bits reached maximum value')
            elif np.all((((self.gdac_best & (1 << np.arange(self.register.global_registers['Vthin_AltFine']['bitlength'] + self.register.global_registers['Vthin_AltFine']['bitlength'])))) > 0).astype(int)[self.gdac_tune_bits] == 0):
                if self.fail_on_warning:
                    raise RuntimeWarning('Selected GDAC bits reached minimum value')
                else:
                    logging.warning('Selected GDAC bits reached minimum value')
            else:
                if self.fail_on_warning:
                    raise RuntimeWarning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d' %(abs(median_occupancy - self.n_injections_gdac / 2), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
                else:
                    logging.warning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d', abs(median_occupancy - self.n_injections_gdac / 2), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))
        else:
            logging.info('Tuned GDAC to Vthin_AltCoarse / Vthin_AltFine = %d / %d', self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))

    def analyze(self):
        # set here because original value is restored after scan()
        self.register_utils.set_gdac(self.gdac_best, send_command=False)

        plot_three_way(self.occ_array_sel_pixels_best.transpose(), title="Occupancy after GDAC tuning of selected pixels (GDAC " + str(self.scan_parameters.GDAC) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)

        plot_three_way(self.occ_array_desel_pixels_best.transpose(), title="Occupancy after GDAC tuning of not selected pixels (GDAC " + str(self.scan_parameters.GDAC) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(GdacTuningStandard)
