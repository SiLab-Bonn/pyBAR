from daq.readout import get_col_row_array_from_data_record_array, save_raw_data_from_data_dict_iterable, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel
from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from analysis.analyze_raw_data import AnalyzeRawData

from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "mask_steps": 3,
    "repeat_command": 100,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_value": 200
}


class AnalogScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(AnalogScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="analog_scan")

    def scan(self, mask_steps=3, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_value=100):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        repeat_command : int
            Number of injections.
        scan_parameter : string
            Name of global register.
        scan_parameter_value : int
            Specify scan steps. These values will be written into global register scan_parameter.

        Note
        ----
        This scan is very similar to the threshold scan.
        This scan can also be used for ToT verification: change scan_parameter_value to desired injection charge (in units of PulsrDAC).
        '''
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value(scan_parameter, scan_parameter_value)
        commands.extend(self.register.get_commands("wrregister", name=[scan_parameter]))
        self.register_utils.send_commands(commands)

        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
        self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, use_delay=True, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

        self.readout.stop(timeout=10.0)

        # plotting data
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

        # saving data
        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_identifier)

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = True
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)
#             analyze_raw_data.interpreter.print_summary()

if __name__ == "__main__":
    import configuration
    scan = AnalogScan(**configuration.device_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
