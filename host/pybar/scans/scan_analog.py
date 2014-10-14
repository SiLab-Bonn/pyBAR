import logging

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager


class AnalogScan(Fei4RunBase):
    '''Analog scan
    '''
    _scan_id = "analog_scan"
    _default_scan_configuration = {
        "mask_steps": 3,  # mask steps
        "n_injections": 100,  # number of injections
        "scan_parameters": {'PlsrDAC': 200},  # the PlsrDAC setting
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_tdc": False  # if True, enables TDC (use RX2)
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value('PlsrDAC', self.scan_parameters.PlsrDAC)
        commands.extend(self.register.get_commands("wrregister", name=['PlsrDAC']))
        self.register_utils.send_commands(commands)

    def scan(self):
        with self.readout():
            cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]

            if self.enable_tdc:
                # activate TDC arming
                self.dut['tdc_rx2']['EN_ARMING'] = True
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, bol_function=self.activate_tdc, eol_function=self.deactivate_tdc, digital_injection=False, enable_shift_masks=["Enable", "C_Low", "C_High"], restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)
            else:
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, digital_injection=False, enable_shift_masks=["Enable", "C_Low", "C_High"], restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)

        # plotting data
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = True
            if self.enable_tdc:
                analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
                analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
                analyze_raw_data.interpreter.use_tdc_word(True)  # align events at the TDC word
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()

    def activate_tdc(self):
        self.dut['tdc_rx2']['ENABLE'] = True

    def deactivate_tdc(self):
        self.dut['tdc_rx2']['ENABLE'] = False

if __name__ == "__main__":
    join = RunManager('../configuration.yaml').run_run(AnalogScan)
    join()
