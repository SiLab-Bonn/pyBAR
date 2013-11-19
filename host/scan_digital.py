from daq.readout import get_col_row_array_from_data_record_array, save_raw_data_from_data_dict_iterable, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel
from analysis.plotting.plotting import plot_occupancy
from analysis.analyze_raw_data import AnalyzeRawData

from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class DigitalScan(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_digital", scan_data_path=None):
        super(DigitalScan, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, configure=True, mask=3, repeat=100):
        '''Scan loop

        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        '''
        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=35)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask)[0]
        self.scan_loop(cal_lvl1_command, repeat=repeat, mask=mask, mask_steps=[], double_columns=[], same_mask_for_all_dc=True, hardware_repeat=True, enable_c_high=False, enable_c_low=False, digital_injection=True, eol_function=None)

        self.readout.stop(timeout=10.0)

        # plotting data
        plot_occupancy(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), max_occ=repeat * 2, filename=self.scan_data_filename + "_occupancy.pdf")

        # saving data
        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_identifier)

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table(FEI4B=scan.register.fei4b)
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = DigitalScan(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(use_thread=False)
    scan.stop()
    scan.analyze()
