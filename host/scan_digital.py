from daq.readout import get_col_row_array_from_data_record_array, save_raw_data_from_data_dict_iterable, convert_data_array, data_array_from_data_dict_iterable, is_data_record
from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from analysis.analyze_raw_data import AnalyzeRawData

from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "mask_steps": 3,
    "repeat_command": 100,
}


class DigitalScan(ScanBase):
    scan_identifier = "digital_scan"

    def scan(self, mask_steps=3, repeat_command=100, **kwargs):
        '''Scan loop

        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        '''
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", 0)  # has to be 0, otherwise you also have analog injections
        commands.extend(self.register.get_commands("wrregister", name=["PlsrDAC"]))
        self.register_utils.send_commands(commands)

        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
        self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, hardware_repeat=True, use_delay=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=True, enable_c_high=False, enable_c_low=False, enable_shift_masks=["Enable"], restore_shift_masks=False, mask=None)

        self.readout.stop(timeout=10.0)

        # plotting data
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

        # saving data
        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_identifier)

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)
            analyze_raw_data.interpreter.print_summary()

if __name__ == "__main__":
    import configuration
    scan = DigitalScan(**configuration.device_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
