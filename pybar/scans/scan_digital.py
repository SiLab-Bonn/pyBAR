import logging

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager


class DigitalScan(Fei4RunBase):
    '''Digital scan
    '''
    _default_run_conf = {
        "mask_steps": 3,  # mask steps
        "n_injections": 100,  # number of injections
        "use_enable_mask": False  # if True, use Enable mask during scan, if False, all pixels will be enabled
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("PrmpVbp", 0)
        self.register.set_global_register_value("Amp2Vbp", 0)
        self.register.set_global_register_value("DisVbn", 0)
        commands.extend(self.register.get_commands("WrRegister", name=["PrmpVbp", "Amp2Vbp", "DisVbn"]))
        self.register.set_pixel_register_value("C_High", 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name="C_High"))
        self.register.set_pixel_register_value("C_Low", 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name="C_Low"))
        self.register_utils.send_commands(commands)

    def scan(self):
        with self.readout():
            cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]
            scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=True, enable_shift_masks=["Enable", "EnableDigInj"], restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.interpreter.set_warning_output(True)
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(DigitalScan)
