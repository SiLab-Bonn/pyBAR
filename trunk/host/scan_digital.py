from daq.readout import get_col_row_array_from_data_record_array, save_raw_data_from_data_dict_iterable, convert_data_array, data_array_from_data_dict_iterable, is_data_record
from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from analysis.analyze_raw_data import AnalyzeRawData
from fei4.register_utils import invert_pixel_mask
from scan.scan import ScanBase
from scan.scan_utils import scan_loop
from scan.run_manager import RunManager
import logging


class DigitalScan(ScanBase):
    _scan_id = "digital_scan"

    _default_scan_configuration = {
        "mask_steps": 3,
        "repeat_command": 100,
        "use_enable_mask": False
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PrmpVbp", 0)
        self.register.set_global_register_value("Amp2Vbp", 0)
        self.register.set_global_register_value("DisVbn", 0)
        commands.extend(self.register.get_commands("wrregister", name=["PrmpVbp", "Amp2Vbp", "DisVbn"]))
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        self.register_utils.send_commands(commands)

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        '''
        with self.readout():
            cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
            scan_loop(self, cal_lvl1_command, repeat_command=self.repeat_command, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=True, enable_shift_masks=["Enable", "EnableDigInj"], restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)

        # plotting data
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

if __name__ == "__main__":
    wait = RunManager.run_run(DigitalScan, 'configuration.yaml')
    wait()
