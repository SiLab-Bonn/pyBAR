""" Scan to inject charge with an external pulser. A trigger signal (3.3V logic level, TX1 at MultiIO board)
    is generated when the CAL command is issued. This trigger can be used to trigger the external pulser.
"""
import logging

from daq.readout import save_raw_data_from_data_dict_iterable

from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "mask_steps": 6,
    "repeat_command": 1000,
    "enable_double_columns": None
}


class ExtInjScan(ScanBase):
    scan_id = "ext_injection_scan"

    def scan(self, mask_steps=6, repeat_command=1000, enable_double_columns=None, **kwargs):
        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
        self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=enable_double_columns, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

        self.readout.stop()

        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_id)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = ExtInjScan(**configuration.default_configuration)
    scan.start(use_thread=False, **local_configuration)
    scan.stop()
    scan.analyze()
