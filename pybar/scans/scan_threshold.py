import logging

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager


class ThresholdScan(Fei4RunBase):
    '''Standard Threshold Scan

    Implementation of a standard threshold scan.
    '''
    _default_run_conf = {
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "n_injections": 100,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', [None, 100])],  # the PlsrDAC range
        "step_size": 1,  # step size of the PlsrDAC during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
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
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        scan_parameter_range = [0, (2 ** self.register.global_registers['PlsrDAC']['bitlength'])]
        if self.scan_parameters.PlsrDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.PlsrDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        scan_parameter_range = range(scan_parameter_range[0], scan_parameter_range[1] + 1, self.step_size)
        logging.info("Scanning %s from %d to %d", 'PlsrDAC', scan_parameter_range[0], scan_parameter_range[-1])

        for scan_parameter_value in scan_parameter_range:
            if self.stop_run.is_set():
                break

            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value('PlsrDAC', scan_parameter_value)
            commands.extend(self.register.get_commands("WrRegister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)

            with self.readout(PlsrDAC=scan_parameter_value):
                cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, fast_dc_loop=True, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(ThresholdScan)
