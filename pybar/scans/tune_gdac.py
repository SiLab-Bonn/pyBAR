import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, data_array_from_data_iterable, get_col_row_array_from_data_record_array
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

    def scan(self):
        if not self.plots_filename:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
            self.close_plots = True
        else:
            self.close_plots = False
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=self.mask_steps)[0]

        self.write_target_threshold()
        for gdac_bit in self.gdac_tune_bits:  # reset all GDAC bits
            self.set_gdac_bit(gdac_bit, bit_value=0, send_command=False)

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

        additional_scan = True
        occupancy_best = 0.0
        last_good_gdac_bit = self.gdac_tune_bits[0]
        last_good_gdac_scan_step = 0
        gdac_tune_bits_permutation = 0
        repeat_last_good_gdac_bit = True
        gdac_best = self.register_utils.get_gdac()
        gdac_tune_bits = self.gdac_tune_bits[:]
        min_gdac_with_occupancy = None
        for gdac_scan_step, gdac_bit in enumerate(gdac_tune_bits):
            if additional_scan:
                self.set_gdac_bit(gdac_bit, bit_value=1)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, set bit %d = 1', scan_parameter_value, gdac_bit)
            else:
                self.set_gdac_bit(gdac_bit, bit_value=0)
                scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                logging.info('GDAC setting: %d, set bit %d = 0', scan_parameter_value, gdac_bit)

            with self.readout(GDAC=scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                scan_loop(self,
                          cal_lvl1_command,
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

            occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
            self.occ_array_sel_pixel = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by creating a mask
            median_occupancy = np.ma.median(self.occ_array_sel_pixel)
            occupancy_almost_zero = np.allclose([median_occupancy], [0])
            if abs(median_occupancy - self.n_injections_gdac / 2) < abs(occupancy_best - self.n_injections_gdac / 2):
                occupancy_best = median_occupancy
                gdac_best = self.register_utils.get_gdac()

            if self.plot_intermediate_steps:
                plot_three_way(self.occ_array_sel_pixel.transpose(), title="Occupancy (GDAC " + str(scan_parameter_value) + " with tuning bit " + str(gdac_bit) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)

#            if abs(median_occupancy - self.n_injections_gdac / 2) < self.max_delta_threshold and gdac_bit > 0:  # abort if good value already found to save time
#                logging.info('Median = %.2f, good result already achieved (median - Ninj/2 < %.2f), skipping not varied bits', median_occupancy, self.max_delta_threshold)
#                break

            if not occupancy_almost_zero:
                if min_gdac_with_occupancy is None:
                    min_gdac_with_occupancy = self.register_utils.get_gdac()
                else:
                    min_gdac_with_occupancy = min(min_gdac_with_occupancy, self.register_utils.get_gdac())

            if gdac_bit > 0:
                # GDAC too low, no hits
                if occupancy_almost_zero and self.register_utils.get_gdac() < min_gdac_with_occupancy:
                    logging.info('Median = %.2f > %.2f, GDAC possibly too low, keep bit %d = 1', median_occupancy, self.n_injections_gdac / 2, gdac_bit)
                # GDAC too high, less hits, decrease GDAC
                elif median_occupancy < (self.n_injections_gdac / 2):  # set GDAC bit to 0 if the occupancy is too low, thus decrease threshold
                    logging.info('Median = %.2f < %.2f, set bit %d = 0', median_occupancy, self.n_injections_gdac / 2, gdac_bit)
                    self.set_gdac_bit(gdac_bit, bit_value=0)
                # GDAC too low, more hits
                else:
                    logging.info('Median = %.2f > %.2f, keep bit %d = 1', median_occupancy, self.n_injections_gdac / 2, gdac_bit)
            elif gdac_bit == 0:
                if occupancy_almost_zero and len(self.gdac_tune_bits) > last_good_gdac_scan_step + 2:# and min_gdac_occupancy is None:
                    self.set_gdac_bit(0, bit_value=0, send_command=False)  # turn off LSB
                    if len(gdac_tune_bits) == gdac_scan_step + 1 and gdac_tune_bits_permutation == 0:  # min. 2 bits for bin search
                        self.set_gdac_bit(last_good_gdac_bit, bit_value=1, send_command=False) # always enable highest bit
                        gdac_tune_bits.extend(self.gdac_tune_bits[last_good_gdac_scan_step + 1:])  # repeat all scan stept from last bit
                        for gdac_clear_bit in self.gdac_tune_bits[:last_good_gdac_scan_step]:
                            self.set_gdac_bit(gdac_clear_bit, bit_value=0, send_command=False)
                        if 2**last_good_gdac_scan_step == 1:  # last step, cleanup
                            last_good_gdac_bit = self.gdac_tune_bits[last_good_gdac_scan_step + 1]
                            last_good_gdac_scan_step += 1
                        else:
                            gdac_tune_bits_permutation += 1
                    else:
                        gdac_tune_bits_permutation_header = map(int,bin(gdac_tune_bits_permutation)[2:].zfill(last_good_gdac_scan_step))
                        for gdac_permutation_bit, gdac_permutation_bit_value in enumerate(gdac_tune_bits_permutation_header):
                            self.set_gdac_bit(self.gdac_tune_bits[gdac_permutation_bit], bit_value=gdac_permutation_bit_value, send_command=False)
                        gdac_tune_bits.extend(self.gdac_tune_bits[last_good_gdac_scan_step + 1:])
                        if 2**last_good_gdac_scan_step > gdac_tune_bits_permutation + 1:
                            gdac_tune_bits_permutation += 1
                        else:  # last step, cleanup
                            gdac_tune_bits_permutation = 0
                            last_good_gdac_bit = self.gdac_tune_bits[last_good_gdac_scan_step + 1]
                            last_good_gdac_scan_step += 1
                elif additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    last_occ_array_sel_pixel = self.occ_array_sel_pixel.copy()
                    gdac_tune_bits.append(0)  # the last tune bit has to be scanned twice
                else:
                    last_median_occupancy = np.ma.median(last_occ_array_sel_pixel)
                    logging.info('Measured bit 0 = 0 with %.2f and bit 0 = 1 with %.2f', median_occupancy, last_median_occupancy)
                    if abs(median_occupancy - self.n_injections_gdac / 2) > abs(last_median_occupancy - self.n_injections_gdac / 2):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                        self.set_gdac_bit(0, bit_value=1)
                        logging.info('Set bit 0 = 1')
                        self.occ_array_sel_pixel = last_occ_array_sel_pixel.copy()
                        median_occupancy = last_median_occupancy
                    else:
                        logging.info('Keep bit 0 = 0')

        # select best GDAC value
        if abs(occupancy_best - self.n_injections_gdac / 2) < abs(median_occupancy - self.n_injections_gdac / 2):
            logging.info("Binary search converged to non-optimal value, apply best GDAC value")
            median_occupancy = occupancy_best
            self.register_utils.set_gdac(gdac_best, send_command=False)

        self.gdac_best = self.register_utils.get_gdac()

        if np.all((((self.gdac_best & (1 << np.arange(self.register.global_registers['Vthin_AltFine']['bitlength'] + self.register.global_registers['Vthin_AltFine']['bitlength'])))) > 0).astype(int)[self.gdac_tune_bits] == 1):
            if self.fail_on_warning:
                raise RuntimeWarning('Selected GDAC bits reached maximum value')
            else:
                logging.warning('Selected GDAC bits reached maximum value')
        if np.all((((self.gdac_best & (1 << np.arange(self.register.global_registers['Vthin_AltFine']['bitlength'] + self.register.global_registers['Vthin_AltFine']['bitlength'])))) > 0).astype(int)[self.gdac_tune_bits] == 0):
            if self.fail_on_warning:
                raise RuntimeWarning('Selected GDAC bits reached minimum value')
            else:
                logging.warning('Selected GDAC bits reached minimum value')
        if abs(median_occupancy - self.n_injections_gdac / 2) > 2 * self.max_delta_threshold:
            if self.fail_on_warning:
                raise RuntimeWarning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d' %(abs(median_occupancy - self.n_injections_gdac / 2), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
            else:
                logging.warning('Global threshold tuning failed. Delta threshold = %.2f > %.2f. Vthin_AltCoarse / Vthin_AltFine = %d / %d', abs(median_occupancy - self.n_injections_gdac / 2), self.max_delta_threshold, self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))
        else:
            logging.info('Tuned GDAC to Vthin_AltCoarse / Vthin_AltFine = %d / %d', self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine"))

    def analyze(self):
        # set here because original value is restored after scan()
        self.register_utils.set_gdac(self.gdac_best, send_command=False)

        plot_three_way(self.occ_array_sel_pixel.transpose(), title="Occupancy after GDAC tuning (GDAC " + str(self.scan_parameters.GDAC) + ")", x_axis_title='Occupancy', filename=self.plots_filename, maximum=self.n_injections_gdac)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_gdac_bit(self, bit_position, bit_value=1, send_command=True):
        gdac = self.register_utils.get_gdac()
        if bit_value:
            gdac |= (1 << bit_position)
        else:
            gdac &= ~(1 << bit_position)
        self.register_utils.set_gdac(gdac, send_command=send_command)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(GdacTuning)
