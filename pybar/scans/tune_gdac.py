import logging

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import is_data_record, is_fe_word, logical_and, get_col_row_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_three_way


class GdacTuning(Fei4RunBase):
    '''Global Threshold Tuning

    Tuning the global threshold to target threshold value (threshold is given in units of PlsrDAC).
    The tuning uses a binary search algorithm.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "scan_parameters": [('GDAC', None)],
        "target_threshold": 30,  # target threshold in PlsrDAC to tune to
        "gdac_tune_bits": range(7, -1, -1),  # GDAC bits to change during tuning
        "gdac_lower_limit": 30,  # set GDAC lower limit to prevent FEI4 from becoming noisy, set to 0 or None to disable
        "n_injections_gdac": 50,  # number of injections per GDAC bit setting
        "max_delta_threshold": 10,  # minimum difference to the target_threshold to abort the tuning, in percent of n_injections_gdac
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
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

        self.write_target_threshold()

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
        if not self.enable_mask_steps_gdac:
            self.enable_mask_steps_gdac = range(self.mask_steps)
        for mask_step in self.enable_mask_steps_gdac:
            select_mask_array += make_pixel_mask(steps=self.mask_steps, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        gdacs_above_threshold = []
        additional_scan_ongoing = False
        last_good_gdac_bit = self.gdac_tune_bits[0]
        last_good_gdac_scan_step = 0
        gdac_tune_bits_permutation = 0
        gdac_values = []
        gdac_occupancies = []
        gdac_occ_array_sel_pixels = []
        gdac_occ_array_desel_pixels = []
        gdac_tune_bits = self.gdac_tune_bits[:]
        min_gdac_with_occupancy = None
        for gdac_scan_step, gdac_bit in enumerate(gdac_tune_bits):
            if self.stop_run.is_set():
                break
            # set all higher GDAC bits
            gdac_tune_bits_permutation_header = map(int, bin(2**last_good_gdac_scan_step - 1 - gdac_tune_bits_permutation)[2:].zfill(last_good_gdac_scan_step))[-last_good_gdac_scan_step:]
            for gdac_permutation_bit, gdac_permutation_bit_value in enumerate(gdac_tune_bits_permutation_header):
                self.set_gdac_bit(self.gdac_tune_bits[gdac_permutation_bit], bit_value=gdac_permutation_bit_value, send_command=False)
            # clear all lower GDAC bits
            for clear_gdac_bit in self.gdac_tune_bits:
                if clear_gdac_bit < gdac_bit:
                    self.set_gdac_bit(clear_gdac_bit, bit_value=0, send_command=False)
            if additional_scan_ongoing:
                self.set_gdac_bit(gdac_bit, bit_value=0, send_command=True)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, set bit %d = 0', scan_parameter_value, gdac_bit)
            else:  # default
                self.set_gdac_bit(gdac_bit, bit_value=1, send_command=False)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, set bit %d = 1', scan_parameter_value, gdac_bit)
            # check if GDAC values are too low or were already scanned
            if not additional_scan_ongoing and ((self.register_utils.get_gdac() in gdac_values) or (self.gdac_lower_limit and self.register_utils.get_gdac() < self.gdac_lower_limit) or (min_gdac_with_occupancy and self.register_utils.get_gdac() <= min_gdac_with_occupancy)):
                if gdac_tune_bits_permutation + 1 == 2**last_good_gdac_scan_step:  # next permutation step
                    gdac_tune_bits_permutation = 0
                    last_good_gdac_scan_step += 1
                else:
                    gdac_tune_bits_permutation += 1
                for i in range(len(gdac_tune_bits) - (gdac_scan_step + 1)):
                    gdac_tune_bits.pop()
                gdac_tune_bits.extend(self.gdac_tune_bits[last_good_gdac_scan_step:])  # repeat all scan steps from last bit
                continue
            # write GDAC
            self.register_utils.set_gdac(self.register_utils.get_gdac(), send_command=True)
            # start scan loop
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
            # calculate arrays from data
            occupancy_array, _, _ = np.histogram2d(*self.fifo_readout.get_raw_data_from_buffer(filter_func=logical_and(is_fe_word, is_data_record), converter_func=get_col_row_array_from_data_record_array)[0], bins=(80, 336), range=[[1, 80], [1, 336]])
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

            if len(gdac_values) >= 2:
                for index, scanned_gdac in enumerate(gdac_values[:-1]):
                    if (self.register_utils.get_gdac() < scanned_gdac and median_occupancy <= gdac_occupancies[index] and gdac_occupancies[index] != 0):
                        if min_gdac_with_occupancy is None:
                            min_gdac_with_occupancy = self.register_utils.get_gdac()
                        else:
                            min_gdac_with_occupancy = max(min_gdac_with_occupancy, self.register_utils.get_gdac())
                    if (scanned_gdac < self.register_utils.get_gdac() and gdac_occupancies[index] <= median_occupancy and median_occupancy != 0):
                        if min_gdac_with_occupancy is None:
                            min_gdac_with_occupancy = scanned_gdac
                        else:
                            min_gdac_with_occupancy = max(min_gdac_with_occupancy, scanned_gdac)
                    for gdac_above_threshold in gdacs_above_threshold:
                        if gdac_above_threshold <= min_gdac_with_occupancy:  # check for valid values
                            gdacs_above_threshold.remove(gdac_above_threshold)

            if gdac_scan_step + 1 == len(gdac_tune_bits):  # last GDAC scan step
                if not additional_scan_ongoing and ((occupancy_almost_zero and no_noise) or not gdacs_above_threshold or (self.gdac_lower_limit and self.register_utils.get_gdac() < self.gdac_lower_limit) or (min_gdac_with_occupancy and self.register_utils.get_gdac() <= min_gdac_with_occupancy) or not no_noise) and len(self.gdac_tune_bits) >= last_good_gdac_scan_step + 2:  # min. 2 bits for bin search
                    self.set_gdac_bit(gdac_bit, bit_value=0, send_command=False)  # clear current tuning bit
                    if gdac_tune_bits_permutation + 1 == 2**last_good_gdac_scan_step:  # next permutation step
                        gdac_tune_bits_permutation = 0
                        last_good_gdac_scan_step += 1
                    else:
                        gdac_tune_bits_permutation += 1
                    gdac_tune_bits.extend(self.gdac_tune_bits[last_good_gdac_scan_step:])  # repeat all scan steps from last bit
                elif gdac_bit == 0 and not additional_scan_ongoing:  # scan bit 0 = 1
                    additional_scan_ongoing = True
                    last_occ_array_sel_pixels = occ_array_sel_pixels.copy()
                    last_occ_array_desel_pixels = occ_array_desel_pixels.copy()
                    last_median_occupancy = median_occupancy
                    gdac_tune_bits.append(0)  # the last tune bit has to be scanned twice
                elif gdac_bit == 0 and additional_scan_ongoing:  # scan bit 0 = 0
                    additional_scan_ongoing = False
                    logging.info('Measured %.2f with bit 0 = 0 with and %.2f with bit 0 = 1', median_occupancy, last_median_occupancy)
                    if (abs(median_occupancy - self.n_injections_gdac / 2.0) >= abs(last_median_occupancy - self.n_injections_gdac / 2.0)) or (last_median_occupancy >= self.n_injections_gdac / 2.0):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                        logging.info('Set bit 0 = 1')
                        self.set_gdac_bit(0, bit_value=1, send_command=True)  # write GDAC value
                        occ_array_sel_pixels = last_occ_array_sel_pixels.copy()
                        occ_array_desel_pixels = last_occ_array_desel_pixels.copy()
                        median_occupancy = last_median_occupancy
                    else:
                        logging.info('Keep bit 0 = 0')
            else:  # regular GDAC scan step
                # GDAC too low, no hits
                if (self.gdac_lower_limit and self.register_utils.get_gdac() < self.gdac_lower_limit) or (min_gdac_with_occupancy and self.register_utils.get_gdac() <= min_gdac_with_occupancy) or not no_noise:
                    logging.info('Median = %.2f > %.2f, GDAC possibly too low, keep bit %d = 1', median_occupancy, self.n_injections_gdac / 2.0, gdac_bit)
                # GDAC too high, less hits, decrease GDAC
                elif median_occupancy < self.n_injections_gdac / 2.0:  # set GDAC bit to 0 if the occupancy is too low, thus decrease threshold
                    logging.info('Median = %.2f < %.2f, set bit %d = 0', median_occupancy, self.n_injections_gdac / 2.0, gdac_bit)
                    self.set_gdac_bit(gdac_bit, bit_value=0, send_command=False)  # do not write, might be too low, do this in next iteration
                # GDAC too low, more hits, increase GDAC
                else:
                    gdacs_above_threshold.append(self.register_utils.get_gdac())
                    logging.info('Median = %.2f > %.2f, keep bit %d = 1', median_occupancy, self.n_injections_gdac / 2.0, gdac_bit)

        if not self.stop_run.is_set():
            # select best GDAC value
            sorted_indices = np.argsort(np.array(gdac_values))
            occupancy_sorted = np.array(gdac_occupancies)[sorted_indices]
            gdac_sorted = np.sort(gdac_values)
            try:
                diff_occupancy = occupancy_sorted[1:] - occupancy_sorted[:-1]
                gdac_min_idx = np.where(diff_occupancy > 0)[0][-1] + 1
            except IndexError:
                gdac_min_idx = None
            occupancy_sorted_sel = occupancy_sorted[gdac_min_idx:]
            best_index_sel = np.abs(np.array(occupancy_sorted_sel[::-1]) - self.n_injections_gdac / 2.0).argmin()
            best_index = sorted_indices[gdac_min_idx:][::-1][best_index_sel]
            gdac_best = gdac_values[best_index]
            median_occupancy = gdac_occupancies[best_index]
            # for plotting
            self.occ_array_sel_pixels_best = gdac_occ_array_sel_pixels[best_index]
            self.occ_array_desel_pixels_best = gdac_occ_array_desel_pixels[best_index]
            if gdac_best != self.register_utils.get_gdac():
                logging.info("Binary search converged to non-optimal value, apply best GDAC value, change GDAC from %d to %d", self.register_utils.get_gdac(), gdac_best)
                self.register_utils.set_gdac(gdac_best, send_command=False)
            self.gdac_best = self.register_utils.get_gdac()

            if abs(median_occupancy - self.n_injections_gdac / 2.0) > abs(self.n_injections_gdac * 0.01 * self.max_delta_threshold) and not self.stop_run.is_set():
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
                        raise RuntimeWarning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d' % (abs(median_occupancy - self.n_injections_gdac / 2.0), abs(self.n_injections_gdac * 0.01 * self.max_delta_threshold), self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
                    else:
                        logging.warning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d', abs(median_occupancy - self.n_injections_gdac / 2.0), abs(self.n_injections_gdac * 0.01 * self.max_delta_threshold), self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))
            else:
                logging.info('Tuned GDAC to Vthin_AltCoarse / Vthin_AltFine = %d / %d', self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))

    def analyze(self):
        # set here because original value is restored after scan()
        self.register_utils.set_gdac(self.gdac_best, send_command=False)
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

    def set_gdac_bit(self, bit_position, bit_value, send_command=True):
        gdac = self.register_utils.get_gdac()
        if bit_value:
            gdac |= (1 << bit_position)
        else:
            gdac &= ~(1 << bit_position)
        self.register_utils.set_gdac(gdac, send_command=send_command)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(GdacTuning)
