import logging

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_fe_word, is_data_record, logical_and, get_col_row_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_three_way


class GdacTuningStandard(Fei4RunBase):
    '''Global Threshold Tuning

    Tuning the global threshold to target threshold value (threshold is given in units of PlsrDAC).
    The tuning uses a binary search algorithm.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "broadcast_commands": False,
        "threaded_scan": True,
        "scan_parameters": [('GDAC', None)],
        "start_gdac": 150,  # start value of GDAC tuning
        "gdac_lower_limit": 30,  # set GDAC lower limit to prevent FEI4 from becoming noisy, set to 0 or None to disable
        "step_size": -1,  # step size of the GDAC during scan
        "target_threshold": 30,  # target threshold in PlsrDAC to tune to
        "n_injections_gdac": 50,  # number of injections per GDAC bit setting
        "max_delta_threshold": 10,  # minimum difference to the target_threshold to abort the tuning
        "enable_mask_steps_gdac": [0],  # mask steps to do per GDAC setting
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
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

        self.plots_filename = PdfPages(self.output_filename + '.pdf')
        self.close_plots = True

    def scan(self):
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

        self.write_target_threshold()

        scan_parameter_range = [(2 ** self.register.global_registers['Vthin_AltFine']['bitlength']), 0]  # high to low
        if self.start_gdac:
            scan_parameter_range[0] = self.start_gdac
        if self.gdac_lower_limit:
            scan_parameter_range[1] = self.gdac_lower_limit

        scan_parameter_range = np.arange(scan_parameter_range[0], scan_parameter_range[1] - 1, self.step_size)

        logging.info("Scanning %s from %d to %d", 'GDAC', scan_parameter_range[0], scan_parameter_range[-1])

        def bits_set(int_type):
            int_type = int(int_type)
            position = 0
            bits_set = []
            while(int_type):
                if(int_type & 1):
                    bits_set.append(position)
                position += 1
                int_type = int_type >> 1
            return bits_set

        # calculate selected pixels from the mask and the disabled columns
        select_mask_array = np.zeros(shape=(80, 336), dtype=np.uint8)
        self.occ_array_sel_pixels_best = select_mask_array.copy()
        self.occ_array_desel_pixels_best = select_mask_array.copy()
        if not self.enable_mask_steps_gdac:
            self.enable_mask_steps_gdac = list(range(self.mask_steps))
        for mask_step in self.enable_mask_steps_gdac:
            select_mask_array += make_pixel_mask(steps=self.mask_steps, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        gdac_values = []
        gdac_occupancies = []
        gdac_occ_array_sel_pixels = []
        gdac_occ_array_desel_pixels = []
        median_occupancy_last_step = None
        for scan_parameter_value in scan_parameter_range:
            if self.stop_run.is_set():
                break
            self.register_utils.set_gdac(scan_parameter_value)
            with self.readout(GDAC=scan_parameter_value, fill_buffer=True):
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

            data = convert_data_array(array=self.read_data(), filter_func=logical_and(is_fe_word, is_data_record), converter_func=get_col_row_array_from_data_record_array)
            occupancy_array, _, _ = np.histogram2d(*data, bins=(80, 336), range=[[1, 80], [1, 336]])
            occ_array_sel_pixels = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by using the mask
            occ_array_desel_pixels = np.ma.array(occupancy_array, mask=np.ma.make_mask(select_mask_array))  # take only de-selected pixel into account by using the inverted mask
            median_occupancy = np.ma.median(occ_array_sel_pixels)
            percentile_noise_occupancy = np.percentile(occ_array_desel_pixels.compressed(), 99.0)
            occupancy_almost_zero = np.allclose(median_occupancy, 0)
            no_noise = np.allclose(percentile_noise_occupancy, 0)
            gdac_values.append(self.register_utils.get_gdac())
            gdac_occupancies.append(median_occupancy)
            gdac_occ_array_sel_pixels.append(occ_array_sel_pixels.copy())
            gdac_occ_array_desel_pixels.append(occ_array_desel_pixels.copy())
            self.occ_array_sel_pixels_best = occ_array_sel_pixels.copy()
            self.occ_array_desel_pixels_best = occ_array_desel_pixels.copy()

            # abort early if threshold is found
            if no_noise and not occupancy_almost_zero and (median_occupancy_last_step is not None and median_occupancy >= median_occupancy_last_step) and median_occupancy >= self.n_injections_gdac / 2.0:
                break

            if no_noise and not occupancy_almost_zero:
                median_occupancy_last_step = median_occupancy
            else:
                median_occupancy_last_step = 0.0

        if not self.stop_run.is_set():
            # select best GDAC value
            sorted_indices = np.argsort(np.array(gdac_values))
            occupancy_sorted = np.array(gdac_occupancies)[sorted_indices]
            gdac_sorted = np.sort(gdac_values)
            gdac_min_idx = np.where(occupancy_sorted >= self.n_injections_gdac / 2.0)[0][-1]
            occupancy_sorted_sel = occupancy_sorted[gdac_min_idx:]
            gdac_sorted_sel = gdac_sorted[gdac_min_idx:]
            best_index_sel = np.abs(np.array(occupancy_sorted_sel) - self.n_injections_gdac / 2.0).argmin()
            best_index = sorted_indices[gdac_min_idx:][::-1][best_index_sel]
            gdac_best = gdac_values[best_index]
            median_occupancy = gdac_occupancies[best_index]
            self.register_utils.set_gdac(gdac_best, send_command=False)
            # for plotting
            self.occ_array_sel_pixels_best = gdac_occ_array_sel_pixels[best_index]
            self.occ_array_desel_pixels_best = gdac_occ_array_desel_pixels[best_index]
            self.gdac_best = self.register_utils.get_gdac()

            if abs(median_occupancy - self.n_injections_gdac / 2.0) > self.max_delta_threshold and not self.stop_run.is_set():
                if np.all((((self.gdac_best & (1 << np.arange(self.register.global_registers['Vthin_AltFine']['bitlength'] + self.register.global_registers['Vthin_AltFine']['bitlength'])))) > 0).astype(int) == 0):
                    if self.fail_on_warning:
                        raise RuntimeWarning('Selected GDAC bits reached minimum value')
                    else:
                        logging.warning('Selected GDAC bits reached minimum value')
                else:
                    if self.fail_on_warning:
                        raise RuntimeWarning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d' % (abs(median_occupancy - self.n_injections_gdac / 2.0), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
                    else:
                        logging.warning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d', abs(median_occupancy - self.n_injections_gdac / 2.0), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))
            else:
                logging.info('Tuned GDAC to Vthin_AltCoarse / Vthin_AltFine = %d / %d', self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))

    def analyze(self):
        # set here because original value is restored after scan()
        self.register_utils.set_gdac(self.gdac_best, send_command=False)
        # write configuration to avoid high current states
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltCoarse", "Vthin_AltFine"]))
        self.register_utils.send_commands(commands)

        plot_three_way(self.occ_array_sel_pixels_best.transpose(), title="Occupancy after GDAC tuning of selected pixels (GDAC " + str(self.gdac_best) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)
        plot_three_way(self.occ_array_desel_pixels_best.transpose(), title="Occupancy after GDAC tuning of not selected pixels (GDAC " + str(self.gdac_best) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(GdacTuningStandard)
