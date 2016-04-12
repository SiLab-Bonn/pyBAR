import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import convert_data_array, is_data_record, data_array_from_data_iterable, get_tot_array_from_data_record_array
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
        "plot_intermediate_steps": False,
        "plots_filename": None,
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

        enable_mask_steps = [0]  # one mask step to increase speed, no effect on precision
        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=self.mask_steps)[0]

        self.write_target_charge()

        for feedback_bit in self.feedback_tune_bits:  # reset all GDAC bits
            self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)

        additional_scan = True
        last_bit_result = self.n_injections_feedback

        tot_mean_best = 0
        feedback_best = self.register.get_global_register_value("PrmpVbpf")
        for feedback_bit in self.feedback_tune_bits:
            if additional_scan:
                self.set_prmp_vbpf_bit(feedback_bit)
                logging.info('PrmpVbpf setting: %d, bit %d = 1', self.register.get_global_register_value("PrmpVbpf"), feedback_bit)
            else:
                self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)
                logging.info('PrmpVbpf setting: %d, bit %d = 0', self.register.get_global_register_value("PrmpVbpf"), feedback_bit)

            scan_parameter_value = self.register.get_global_register_value("PrmpVbpf")

            with self.readout(PrmpVbpf=scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                scan_loop(self,
                          cal_lvl1_command,
                          repeat_command=self.n_injections_feedback,
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

            tots = convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_tot_array_from_data_record_array)
            mean_tot = np.mean(tots)
            if np.isnan(mean_tot):
                logging.error("No hits, ToT calculation not possible, tuning will fail")

            if abs(mean_tot - self.target_tot) < abs(tot_mean_best - self.target_tot):
                tot_mean_best = mean_tot
                feedback_best = self.register.get_global_register_value("PrmpVbpf")

            logging.info('Mean ToT = %f', mean_tot)
            self.tot_array, _ = np.histogram(a=tots, range=(0, 16), bins=16)
            if self.plot_intermediate_steps:
                plot_tot(hist=self.tot_array, title='ToT distribution (PrmpVbpf ' + str(scan_parameter_value) + ')', filename=self.plots_filename)

            if abs(mean_tot - self.target_tot) < self.max_delta_tot and feedback_bit > 0:  # abort if good value already found to save time
                logging.info('Good result already achieved, skipping missing bits')
                break

            if feedback_bit > 0 and mean_tot < self.target_tot:
                self.set_prmp_vbpf_bit(feedback_bit, bit_value=0)
                logging.info('Mean ToT = %f < %d ToT, set bit %d = 0', mean_tot, self.target_tot, feedback_bit)

            if feedback_bit == 0:
                if additional_scan:  # scan bit = 0 with the correct value again
                    additional_scan = False
                    last_bit_result = mean_tot
                    self.feedback_tune_bits.append(0)  # bit 0 has to be scanned twice
                else:
                    logging.info('Scanned bit 0 = 0 with %f instead of %f for scanned bit 0 = 1', mean_tot, last_bit_result)
                    if(abs(mean_tot - self.target_tot) > abs(last_bit_result - self.target_tot)):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                        self.set_prmp_vbpf_bit(feedback_bit, bit_value=1)
                        mean_tot = last_bit_result
                        logging.info('Set bit 0 = 1')
                    else:
                        logging.info('Set bit 0 = 0')
                if abs(mean_tot - self.target_tot) > abs(tot_mean_best - self.target_tot):
                    logging.info("Binary search converged to non optimal value, take best measured value instead")
                    mean_tot = tot_mean_best
                    self.register.set_global_register_value("PrmpVbpf", feedback_best)

        if self.register.get_global_register_value("PrmpVbpf") == 0 or self.register.get_global_register_value("PrmpVbpf") == 254:
            logging.warning('PrmpVbpf reached minimum/maximum value')
            if self.fail_on_warning:
                raise RuntimeWarning('PrmpVbpf reached minimum/maximum value')
        if abs(mean_tot - self.target_tot) > 2 * self.max_delta_tot:
            logging.warning('Global feedback tuning failed. Delta ToT = %f > %f. PrmpVbpf = %d', abs(mean_tot - self.target_tot), self.max_delta_tot, self.register.get_global_register_value("PrmpVbpf"))
            if self.fail_on_warning:
                raise RuntimeWarning('Global feedback tuning failed.')
        else:
            logging.info('Tuned PrmpVbpf to %d', self.register.get_global_register_value("PrmpVbpf"))

        self.feedback_best = self.register.get_global_register_value("PrmpVbpf")

    def analyze(self):
        self.register.set_global_register_value("PrmpVbpf", self.feedback_best)
        plot_tot(hist=self.tot_array, title='ToT distribution after feedback tuning (PrmpVbpf %d)' % self.scan_parameters.PrmpVbpf, filename=self.plots_filename)
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
