import pprint
import time
import struct
import itertools
import logging
from collections import deque

import numpy as np
import tables as tb
import BitVector

from utils.utils import get_all_from_queue, split_seq

from analysis.data_struct import MetaTable

from scan.scan import ScanBase

class ThresholdScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_threshold", scan_data_path = None):
        super(ThresholdScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def start(self, configure = True):
        super(ThresholdScan, self).start(configure)
        
        scan_parameter = 'PlsrDAC'
        scan_paramter_value_range = range(0, 100, 1)
        
        #    class ScanParameters(tb.IsDescription):
        #        scan_parameter = tb.UInt32Col(pos=0)
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
        data_q = deque()
        raw_data_q = deque()
        
        total_words = 0
        append_size = 50000
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        with tb.openFile(self.scan_data_filename+".h5", mode = 'w', title = 'first data') as file_h5:
            raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data, expectedrows = append_size)
            meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables, expectedrows = 10)
            scan_param_table_h5 = file_h5.createTable(file_h5.root, name = 'scan_parameters', description = scan_param_descr, title = 'scan_parameters', filters = filter_tables, expectedrows = 10)
            
            row_meta = meta_data_table_h5.row
            row_scan_param = scan_param_table_h5.row
                
            for scan_paramter_value in scan_paramter_value_range:
                self.readout.start()
                
                print 'Scan step:', scan_parameter, scan_paramter_value
                
                commands = []
                self.register.set_global_register_value(scan_parameter, scan_paramter_value)
                commands.extend(self.register.get_commands("wrregister", name = [scan_parameter]))
                self.register_utils.send_commands(commands)
                
                #import cProfile
                #pr = cProfile.Profile()
                mask = 6
                repeat = 100
                wait_cycles = 336*2/mask*24/4*3
                cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
                #pr.enable()
                self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = [], dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                #pr.disable()
                #pr.print_stats('cumulative')
                
                self.readout.stop()
        
        #            data_q = get_all_from_queue(self.readout.data_queue)
        #            print 'got all from queue'
        #            
        #            data_list = list(itertools.chain(*data_q))
        #            print 'length data list:', len(data_list)
        
#                 data_q = list(get_all_from_queue(self.readout.data_queue))
#                 for item in data_q:
                data_q.extend(list(get_all_from_queue(self.readout.data_queue))) # use list, it is faster
                while True:
                    try:
                        item = data_q.pop()
                    except IndexError:
                        break # jump out while loop
                    
                    raw_data = item['raw_data']
        #                for word in raw_data:
        #                    print FEI4Record(word, 'fei4a')
                    len_raw_data = len(raw_data)
                    raw_data_q.extend(split_seq(raw_data, append_size))
                    while True:
                        try:
                            data = raw_data_q.pop()
                        except IndexError:
                            break
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
                    row_scan_param[scan_parameter] = scan_paramter_value
                    row_scan_param.append()
                    scan_param_table_h5.flush()
         
        #    occupancy_plots = []
        #    for data_word_list in data_words_lists:
        #        #save_occupancy('scan_'+str(scan_paramter_value)+'.png', *zip(*self.readout.get_col_row(data_words[scan_paramter_value])), max_occ = repeat*2)
        #        #print str(scan_paramter_value), len(list(self.readout.get_col_row(data_words[scan_paramter_value])))
        #        dimension = (80,336)
        #        occupancy_plot = np.zeros(dimension, dtype = np.uint8)
        #        #print list(zip(*self.readout.get_col_row(data_word_list)))[0]
        #        for col, row in zip(*zip(*self.readout.get_col_row(data_word_list))):
        #            occupancy_plot[col][row] += 1
        #        occupancy_plots.append(occupancy_plot)
        #        
        #    for occupancy_plot in occupancy_plots:
        #        print occupancy_plot[11][80]
        
if __name__ == "__main__":
    import configuration
    scan = ThresholdScan(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start()
