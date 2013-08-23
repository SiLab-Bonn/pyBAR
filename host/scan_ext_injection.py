""" Scan to inject charge with an external pulser. A trigger signal (3.3V logic level, TX1 at MultiIO board) 
    is generated when the CAL command is issued. This trigger can is used to trigger the external pulser.
"""

import time
import tables as tb
import BitVector

from analysis.data_struct import MetaTable
from utils.utils import get_all_from_queue, split_seq
from scan.scan import ScanBase

class ExtInjScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_ext_inj", outdir = None):
        super(ExtInjScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(ExtInjScan, self).start(configure)
        
        self.lock.acquire()
        
        print 'Starting readout thread...'
        self.readout.start()
        print 'Done!'
        
        mask = 6
        repeat = 1000
        wait_cycles = 336*2/mask*24/4*3
        cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
        self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = [], dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)

        print 'Stopping readout thread...'
        self.readout.stop()
        print 'Done!'
              
        def get_cols_rows(data_words):
            for item in data_words:
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_rows_cols(data_words):
            for item in data_words:
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
        
        data_q = list(get_all_from_queue(self.readout.data_queue))
        print 'got all from queue'
    
        total_words = 0
        
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        with tb.openFile(self.scan_data_path+".h5", mode = "w", title = "test file") as file_h5:
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
        
        self.lock.release()

if __name__ == "__main__":
    import scan_configuration
    scan = ExtInjScan(config_file = scan_configuration.config_file, bit_file = scan_configuration.bit_file, outdir = scan_configuration.outdir)
    scan.start()
