import itertools
import tables as tb
import numpy as np
import BitVector

from analysis.data_struct import MetaTable
from utils.utils import get_all_from_queue, split_seq
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
        
        self.readout.stop()
        
        data_q = list(get_all_from_queue(self.readout.data_queue))
        data_words = itertools.chain(*(data_dict['raw_data'] for data_dict in data_q))
        total_words = 0
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        with tb.openFile(self.scan_data_filename+".h5", mode = "w", title = "test file") as file_h5:
            raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data)
            meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables)
            row_meta = meta_data_table_h5.row
            for item in data_q:
                raw_data = item['raw_data']
                len_raw_data = len(raw_data)
                for data in split_seq(raw_data, 50000):
                    raw_data_earray_h5.append(data)
                    raw_data_earray_h5.flush()
                row_meta['timestamp'] = item['timestamp']
                row_meta['error'] = item['error']
                row_meta['length'] = len_raw_data
                row_meta['start_index'] = total_words
                total_words += len_raw_data
                row_meta['stop_index'] = total_words
                row_meta.append()
                meta_data_table_h5.flush()
        
if __name__ == "__main__":
    import configuration
    scan = DigitalScan(config_file = configuration.config_file, bit_file  = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start(use_thread = False)
    scan.stop()
    from analysis.analyze_raw_data import AnalyzeRawData
    output_file = scan.scan_data_filename+"_interpreted.h5"
    with AnalyzeRawData(input_file = scan.scan_data_filename+".h5", output_file = output_file) as analyze_raw_data:
        analyze_raw_data.interpret_word_table(FEI4B = True if(configuration.chip_flavor == 'fei4b') else False)
        analyze_raw_data.plotHistograms(scan_data_filename = scan.scan_data_filename)

