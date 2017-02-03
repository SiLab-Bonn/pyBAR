import logging

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop, make_pixel_mask
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, is_fe_word, logical_and, data_array_from_data_iterable, get_col_row_tot_array_from_data_record_array
from pybar.analysis.plotting.plotting import plot_tot


class FeedbackTuning(Fei4RunBase):
    '''Global Feedback Tuning

    Tuning the global feedback to target ToT at given charge (charge is given in units of PlsrDAC).
    The tuning uses a binary search algorithm.

    Note:
    Use pybar.scans.tune_fei4 for full FE-I4 tuning.
    '''
    _default_run_conf = {
        "scan_parameters": [('PrmpVbpf', None)],
        "target_charge": 280,
        "target_tot": 5,
        "feedback_tune_bits": range(7, -1, -1),
        "n_injections_feedback": 50,
        "max_delta_tot": 0.1,
        "enable_mask_steps_feedback": [0],  # mask steps to do per PrmpVbpf setting
        "plot_intermediate_steps": False,
        "plots_filename": None,
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "fail_on_warning": False,  # the scan throws a RuntimeWarning exception if the tuning fails
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "same_mask_for_all_dc": True  # Increases scan speed, should be deactivated for very noisy FE
    }

    # Parallel mode not supported in tunings
    def set_scan_mode(self):
        self.parallel = False

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
        if not self.enable_mask_steps_feedback:
            self.enable_mask_steps_feedback = range(self.mask_steps)
        for mask_step in self.enable_mask_steps_feedback:
            select_mask_array += make_pixel_mask(steps=self.mask_steps, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

        self.write_target_charge()

        for feedback_bit in self.feedback_tune_bits:  # reset all feedback bits
            self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)

        additional_scan = True
        tot_mean_best = 0.0
        feedback_best = self.register.get_global_register_value("PrmpVbpf")
        feedback_tune_bits = self.feedback_tune_bits[:]
        for feedback_bit in feedback_tune_bits:
            if additional_scan:
                self.set_prmp_vbpf_bit(feedback_bit, bit_value=1)
                logging.info('PrmpVbpf setting: %d, set bit %d = 1', self.register.get_global_register_value("PrmpVbpf"), feedback_bit)
            else:
                self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)
                logging.info('PrmpVbpf setting: %d, set bit %d = 0', self.register.get_global_register_value("PrmpVbpf"), feedback_bit)

            scan_parameter_value = self.register.get_global_register_value("PrmpVbpf")

            with self.readout(PrmpVbpf=scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                scan_loop(self,
                          command=cal_lvl1_command,
                          repeat_command=self.n_injections_feedback,
                          mask_steps=self.mask_steps,
                          enable_mask_steps=self.enable_mask_steps_feedback,
                          enable_double_columns=None,
                          same_mask_for_all_dc=self.same_mask_for_all_dc,
                          eol_function=None,
                          digital_injection=False,
                          enable_shift_masks=self.enable_shift_masks,
                          disable_shift_masks=self.disable_shift_masks,
                          restore_shift_masks=True,
                          mask=None,
                          double_column_correction=self.pulser_dac_correction)

            col_row_tot_array = np.column_stack(convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=logical_and(is_fe_word, is_data_record), converter_func=get_col_row_tot_array_from_data_record_array))
            occupancy_array, _, _ = np.histogram2d(col_row_tot_array[:, 0], col_row_tot_array[:, 1], bins=(80, 336), range=[[1, 80], [1, 336]])
            occupancy_array = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by creating a mask
            occupancy_array = np.ma.masked_where(occupancy_array > self.n_injections_feedback, occupancy_array)
            col_row_tot_hist = np.histogramdd(col_row_tot_array, bins=(80, 336, 16), range=[[1, 80], [1, 336], [0, 15]])[0]
            tot_mean_array = np.average(col_row_tot_hist, axis=2, weights=range(0, 16)) * sum(range(0, 16)) / self.n_injections_feedback
            tot_mean_array = np.ma.array(tot_mean_array, mask=occupancy_array.mask)
            # keep noisy pixels out
            mean_tot = np.ma.mean(tot_mean_array)

            if abs(mean_tot - self.target_tot) < abs(tot_mean_best - self.target_tot):
                tot_mean_best = mean_tot
                feedback_best = self.register.get_global_register_value("PrmpVbpf")

            logging.info('Mean ToT = %.2f', mean_tot)
            tot_array = col_row_tot_array[:, 2]
            self.tot_hist, _ = np.histogram(a=tot_array, range=(0, 16), bins=16)
            if self.plot_intermediate_steps:
                plot_tot(hist=self.tot_hist, title='ToT distribution (PrmpVbpf ' + str(scan_parameter_value) + ')', filename=self.plots_filename)

#             if abs(mean_tot - self.target_tot) < self.max_delta_tot and feedback_bit > 0:  # abort if good value already found to save time
#                 logging.info('Good result already achieved, skipping missing bits')
#                 break

            if feedback_bit > 0:
                # TODO: if feedback is to high, no hits
                if mean_tot < self.target_tot:
                    self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)
                    logging.info('Mean ToT = %.2f < %.2f ToT, set bit %d = 0', mean_tot, self.target_tot, feedback_bit)
                else:
                    logging.info('Mean ToT = %.2f > %.2f ToT, keep bit %d = 1', mean_tot, self.target_tot, feedback_bit)
            elif feedback_bit == 0:
                if additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    last_mean_tot = mean_tot
                    last_tot_hist = self.tot_hist.copy()
                    feedback_tune_bits.append(0)  # bit 0 has to be scanned twice
                else:
                    logging.info('Measured %.2f with bit 0 = 0 and %.2f with bit 0 = 1', mean_tot, last_mean_tot)
                    if(abs(mean_tot - self.target_tot) > abs(last_mean_tot - self.target_tot)):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                        logging.info('Set bit 0 = 1')
                        self.set_prmp_vbpf_bit(0, bit_value=1)
                        self.tot_hist = last_tot_hist.copy()
                        mean_tot = last_mean_tot
                    else:
                        logging.info('Keep bit 0 = 0')

        # select best Feedback value
        if abs(mean_tot - self.target_tot) > abs(tot_mean_best - self.target_tot):
            logging.info("Binary search converged to non-optimal value, apply best Feedback value, change PrmpVbpf from %d to %d", self.register.get_global_register_value("PrmpVbpf"), feedback_best)
            mean_tot = tot_mean_best
            self.register.set_global_register_value("PrmpVbpf", feedback_best)

        self.feedback_best = self.register.get_global_register_value("PrmpVbpf")

        if abs(mean_tot - self.target_tot) > 2 * self.max_delta_tot:
            if np.all((((self.feedback_best & (1 << np.arange(self.register.global_registers['PrmpVbpf']['bitlength'])))) > 0).astype(int)[self.feedback_tune_bits] == 1):
                if self.fail_on_warning:
                    raise RuntimeWarning('Selected Feedback bits reached maximum value')
                else:
                    logging.warning('Selected Feedback bits reached maximum value')
            elif np.all((((self.feedback_best & (1 << np.arange(self.register.global_registers['PrmpVbpf']['bitlength'])))) > 0).astype(int)[self.feedback_tune_bits] == 0):
                if self.fail_on_warning:
                    raise RuntimeWarning('Selected Feedback bits reached minimum value')
                else:
                    logging.warning('Selected Feedback bits reached minimum value')
            else:
                if self.fail_on_warning:
                    raise RuntimeWarning('Global feedback tuning failed. Delta ToT = %.2f > %.2f. PrmpVbpf = %d' %(abs(mean_tot - self.target_tot), self.max_delta_tot, self.register.get_global_register_value("PrmpVbpf")))
                else:
                    logging.warning('Global feedback tuning failed. Delta ToT = %.2f > %.2f. PrmpVbpf = %d', abs(mean_tot - self.target_tot), self.max_delta_tot, self.register.get_global_register_value("PrmpVbpf"))
        else:
            logging.info('Tuned PrmpVbpf to %d', self.register.get_global_register_value("PrmpVbpf"))

    def analyze(self):
        # set here because original value is restored after scan()
        self.register.set_global_register_value("PrmpVbpf", self.feedback_best)

        plot_tot(hist=self.tot_hist, title='ToT distribution after feedback tuning (PrmpVbpf %d)' % self.scan_parameters.PrmpVbpf, filename=self.plots_filename)
        if self.close_plots:
            self.plots_filename.close()

    def write_target_charge(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PlsrDAC", self.target_charge)
        commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_prmp_vbpf_bit(self, bit_position, bit_value=1):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        if bit_value == 1:
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf") | (1 << bit_position))
        else:
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf") & ~(1 << bit_position))
        commands.extend(self.register.get_commands("WrRegister", name=["PrmpVbpf"]))
        self.register_utils.send_commands(commands)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(FeedbackTuning)
