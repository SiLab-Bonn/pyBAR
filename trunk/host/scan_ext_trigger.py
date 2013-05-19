import itertools
import struct
import time
import datetime
import logging
from collections import deque

import numpy as np
#import pandas as pd
import tables as tb
#from tables import *
#from tables import atom
import BitVector

from daq.readout import Readout
from utils.utils import get_iso_time

from threading import Lock

from utils.utils import get_all_from_queue, split_seq

from analysis.data_struct import MetaTable

from scan.scan import ScanBase

class ExtTriggerScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "ext_trigger_scan", outdir = None):
        super(ExtTriggerScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(ExtTriggerScan, self).start(configure)
        
        print self.scan_identifier, 'Start readout thread...'
        #self.readout.set_filter(self.readout.tlu_data_filter)
        self.readout.start()
        print self.scan_identifier, 'Done!'
        
        #scan_parameter = 'Vthin_AltFine'
        #scan_paramter_value = self.register.get_global_register_value(scan_parameter)
        append_size = 50000
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        with tb.openFile(self.scan_data_path+".h5", mode = 'w', title = 'test file') as file_h5:
            raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data, expectedrows = append_size)
            meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables, expectedrows = 10)
            
            lvl1_command = BitVector.BitVector(size = 24)+self.register.get_commands("lv1")[0]#+BitVector.BitVector(size = 10000)
            self.register_utils.set_command(lvl1_command)
            self.readout_utils.set_tlu_mode(mode = 3, disable_veto = False, enable_reset = False, tlu_trigger_clock_cycles = 16, trigger_data_delay = 2, tlu_trigger_low_timeout = 255)
            self.readout_utils.set_ext_cmd_start(True)
                
            consecutive_lvl1 = self.register.get_global_register_value("Trig_Count")
            if consecutive_lvl1 == 0:
                consecutive_lvl1 = 16
            
            row_meta = meta_data_table_h5.row
            
            total_words = 0
            
            wait_for_first_trigger = True
            
            saw_no_data_at_time = time.time()
            saw_data_at_time = time.time()
            timeout_no_data = 10 # secs
            #data_q = []
            data_q = deque()
            raw_data_q = deque()
            
            while self.stop_thread_event.wait(0.05) or not self.stop_thread_event.is_set():
                if self.stop_thread_event.is_set():
                    break
#                 lost_data = self.readout.get_lost_data_count()
#                 if lost_data != 0:
#                     print 'Lost data count:', lost_data

                #print 'FIFO fill level:', (float(fifo_size)/2**20)*100
                #print 'Trigger number:', bin(current_trigger_number)

                data_q.extend(list(get_all_from_queue(self.readout.data_queue))) # use list, it is faster
                
                while True:
                    try:
                        item = data_q.pop()
                    except IndexError:
                        if wait_for_first_trigger == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                            print self.scan_identifier, 'Done!'
                            print self.scan_identifier, 'Total amount of triggers collected:', self.readout_utils.get_trigger_number()
                            self.readout_utils.set_tlu_mode(mode = 0)
                            self.stop_thread_event.set()
                        elif wait_for_first_trigger == False:
                            saw_no_data_at_time = time.time()
                              
                        break # jump out while loop
                    
                    saw_data_at_time = time.time()
                    
                    if wait_for_first_trigger == True:
                        print self.scan_identifier, 'Taking data...'
                        wait_for_first_trigger = False

                    raw_data = item['raw_data']
#                         for word in raw_data:
#                             print FEI4Record(word, 'fei4a')
                    len_raw_data = len(raw_data) 
                    #for data in split_seq(raw_data, append_size):
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
        
        self.stop_thread_event.set()
     
        print self.scan_identifier, 'Stopping readout thread...'
        self.readout.stop()
        print self.scan_identifier, 'Done!'
        
        print self.scan_identifier, 'Data remaining in memory:', self.readout.get_fifo_size()
        print self.scan_identifier, 'Lost data count:', self.readout.get_lost_data_count()

        
if __name__ == "__main__":
    chip_flavor = 'fei4a'
    config_file = r'C:\Users\silab\Dropbox\pyats\trunk\host\config\fei4default\configs\std_cfg_'+chip_flavor+'_simple.cfg'
    bit_file = r'C:\Users\silab\Dropbox\pyats\trunk\device\MultiIO\FPGA\ise\top.bit'
    
    scan = ExtTriggerScan(config_file, bit_file)
    
    scan.start()
