import BitVector

from daq.readout import get_col_row_array_from_data_record_array, save_raw_data, ArrayConverter, ArrayFilter, data_dict_to_data_array, is_data_record
from analysis.plotting.plotting import plot_occupancy

from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class DigitalScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_digital", scan_data_path = None):
        super(DigitalScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def scan(self, configure = True, mask = 6, repeat = 100, steps = []):        
        self.readout.start()
        
        wait_cycles = 336*2/mask*24/4*3
        cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 35)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
        self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = steps, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, enable_c_high = False, enable_c_low = False, digital_injection = True, read_function = None)
        
        self.readout.stop(timeout=10.0)
        
        # plotting data
        dr_filter = ArrayFilter(is_data_record)
        col_row_converter = ArrayConverter(get_col_row_array_from_data_record_array)
        plot_occupancy(*col_row_converter.convert_array(dr_filter.filter_array(data_dict_to_data_array(self.readout.data))), max_occ = repeat*2, filename = self.scan_data_filename+".pdf")
        
        # saving data
        save_raw_data(self.readout.data, filename = self.scan_data_filename, title=self.scan_identifier)
        
if __name__ == "__main__":
    import configuration
    scan = DigitalScan(config_file = configuration.config_file, bit_file  = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start(use_thread = False)
    scan.stop()
    from analysis.analyze_raw_data import AnalyzeRawData
    output_file = scan.scan_data_filename+"_interpreted.h5"
    with AnalyzeRawData(input_file = scan.scan_data_filename+".h5", output_file = output_file) as analyze_raw_data:
        analyze_raw_data.interpret_word_table(FEI4B = scan.register.fei4b)
        analyze_raw_data.plotHistograms(scan_data_filename = scan.scan_data_filename)
