import logging
import inspect

import numpy as np

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_xtalk_mask, make_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy


class CrosstalkScan(Fei4RunBase):
    '''Crosstalk Scan

    Implementation of a crosstalk scan. Injection in long edge pixels (row - 1, row + 1).
    Crosstalk exists when a threshold higher 0 can be measured (s-curve fit successful).
    '''
    _default_run_conf = {
        "mask_steps": 6,  # number of injections per PlsrDAC step
        "n_injections": 100,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', [None, 800])],  # the PlsrDAC range
        "step_size": 10,  # step size of the PlsrDAC during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "xtalk_shift_mask": ["C_High", "C_Low"],  # crosstalk mask derived from enable_shift_masks
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
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

    def scan(self):
        scan_parameter_range = [0, (2 ** self.register.global_registers['PlsrDAC']['bitlength'])]
        if self.scan_parameters.PlsrDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.PlsrDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        scan_parameter_range = list(range(scan_parameter_range[0], scan_parameter_range[1] + 1, self.step_size))
        logging.info("Scanning %s from %d to %d", 'PlsrDAC', scan_parameter_range[0], scan_parameter_range[-1])

        def set_xtalk_mask():
            frame = inspect.currentframe()
            if frame.f_back.f_locals['index'] == 0:
                mask = make_pixel_mask(steps=self.mask_steps, shift=frame.f_back.f_locals['mask_step'])
                mask = make_xtalk_mask(mask)
                list(map(lambda mask_name: self.register.set_pixel_register_value(mask_name, mask), self.disable_shift_masks))
                commands = []
                commands.append(self.register.get_commands("ConfMode")[0])
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=self.xtalk_shift_mask, joint_write=True))
                commands.append(self.register.get_commands("RunMode")[0])
                self.register_utils.send_commands(commands, concatenate=True)

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
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, fast_dc_loop=False, bol_function=set_xtalk_mask, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

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
            thr_hist = analyze_raw_data.out_file_h5.root.HistThresholdFitted[:, :].T
            xtalk_mask = np.zeros(shape=thr_hist.shape, dtype=np.dtype('>u1'))
            xtalk_mask[thr_hist > 0.0] = 1
            plot_occupancy(xtalk_mask.T, title='Crosstalk', z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(CrosstalkScan)
