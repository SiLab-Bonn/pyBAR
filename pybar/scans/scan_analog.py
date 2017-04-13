import logging

from collections import Iterable

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import scan_loop, invert_pixel_mask
from pybar.analysis.analyze_raw_data import AnalyzeRawData


class AnalogScan(Fei4RunBase):
    '''Analog scan
    '''
    _default_run_conf = {
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "n_injections": 100,  # number of injections
        "scan_parameters": [('PlsrDAC', 280)],  # the PlsrDAC setting
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "enable_tdc": False,  # if True, enables TDC (use RX2)
        "same_mask_for_all_dc": True,  # if True, all columns have the same mask, if False, mask will be enabled only where injected
        "enable_double_columns": None,  # List of double columns which will be enabled during scan. None will select all double columns
        "enable_mask_steps": None,  # List of mask steps which will be applied. None will select all mask steps.
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        scan_parameter_value = self.scan_parameters.PlsrDAC[0] if isinstance(self.scan_parameters.PlsrDAC, Iterable) else self.scan_parameters.PlsrDAC
        self.register.set_global_register_value('PlsrDAC', scan_parameter_value)
        commands.extend(self.register.get_commands("WrRegister", name=['PlsrDAC']))
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
        self.register_utils.send_commands(commands)

    def scan(self):
        with self.readout():
            cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]

            if self.enable_tdc:
                # activate TDC arming
                self.tdc['EN_ARMING'] = True
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=self.enable_mask_steps, enable_double_columns=self.enable_double_columns, same_mask_for_all_dc=self.same_mask_for_all_dc, bol_function=self.activate_tdc, eol_function=self.deactivate_tdc, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)
            else:
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=self.enable_mask_steps, enable_double_columns=self.enable_double_columns, same_mask_for_all_dc=self.same_mask_for_all_dc, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

        # plotting data
#         filter_func = np.logical_and(self.raw_data_file._filter_funcs[self.current_single_handle], is_data_record)
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.fifo_readout.data), filter_func=filter_func, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = True
            if self.enable_tdc:
                analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
                analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

    def activate_tdc(self):
        self.tdc['ENABLE'] = True

    def deactivate_tdc(self):
        self.tdc['ENABLE'] = False

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(AnalogScan)
