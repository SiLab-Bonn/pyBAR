from scan.scan import ScanBase

from analysis.analyze_raw_data import AnalyzeRawData
from fei4.register_utils import invert_pixel_mask
from scan.scan_utils import scan_loop

from scan.run_manager import RunManager

import logging


class ThresholdScan(ScanBase):
    _scan_id = "threshold_scan"

    _default_scan_configuration = {
        "mask_steps": 3,
        "repeat_command": 100,
        "scan_parameters": {'PlsrDAC': (None, 100)},
        "step_size": 1,
        "use_enable_mask": False,
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],
        "disable_shift_masks": []
    }

    def configure(self):
        pass

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        repeat_command : int
            Number of injections per scan step.
        scan_parameters : dict
            Dictionary containing scan parameters.
        step_size : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        '''
        scan_parameter_range = [0, (2 ** self.register.get_global_register_objects(name=['PlsrDAC'])[0].bitlength)]
        if self.scan_parameters.PlsrDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.PlsrDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        scan_parameter_range = range(scan_parameter_range[0], scan_parameter_range[1] + 1, self.step_size)
        logging.info("Scanning %s from %d to %d" % ('PlsrDAC', scan_parameter_range[0], scan_parameter_range[-1]))

        for scan_parameter_value in scan_parameter_range:
            if self.stop_run.is_set():
                break
            logging.info('Scan step: %s %d' % ('PlsrDAC', scan_parameter_value))

            commands = []
            commands.extend(self.register.get_commands("confmode"))
            self.register.set_global_register_value('PlsrDAC', scan_parameter_value)
            commands.extend(self.register.get_commands("wrregister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)

            with self.readout(PlsrDAC=scan_parameter_value):
                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.repeat_command, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

if __name__ == "__main__":
    wait = RunManager.run_scan(ThresholdScan, 'configuration.yaml')
    wait()
