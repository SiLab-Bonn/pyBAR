import itertools
import struct
import time
import datetime
import logging
from collections import deque
import math

import numpy as np
#import pandas as pd
import tables as tb
#from tables import *
#from tables import atom
import BitVector

from daq.readout import Readout
from utils.utils import get_iso_time

from utils.utils import get_all_from_queue, split_seq

from analysis.data_struct import MetaTable

from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class ExtTriggerScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_ext_trigger", scan_data_path = None):
        super(ExtTriggerScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def start(self, configure = True):
        super(ExtTriggerScan, self).start(configure)
        
        logging.info('Starting readout thread...')
        self.readout.start()
        logging.info('Done!')
        
        #scan_parameter = 'Vthin_AltFine'
        #scan_paramter_value = self.register.get_global_register_value(scan_parameter)
        append_size = 50000
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        with tb.openFile(self.scan_data_filename+".h5", mode = 'w', title = 'test file') as file_h5:
            raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data, expectedrows = append_size)
            meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables, expectedrows = 10)
            
            lvl1_command = BitVector.BitVector(size = 24)+self.register.get_commands("lv1")[0]#+BitVector.BitVector(size = 10000)
            self.register_utils.set_command(lvl1_command)
            self.readout_utils.set_tlu_mode(mode = 3, disable_veto = False, enable_reset = False, tlu_trigger_clock_cycles = 16, trigger_data_delay = 4, tlu_trigger_low_timeout = 255)
            self.readout_utils.set_ext_cmd_start(True)
                
            consecutive_lvl1 = self.register.get_global_register_value("Trig_Count")
            if consecutive_lvl1 == 0:
                consecutive_lvl1 = 16
            
            row_meta = meta_data_table_h5.row
            
            total_words = 0
            wait_for_first_trigger = True
            
            
            timeout_no_data = 60 # secs
            max_triggers = 6000000
            scan_timeout = 1200
            show_trigger_message_at = 10**(int(math.ceil(math.log10(max_triggers)))-1)
            last_iteration = time.time()
            saw_no_data_at_time = last_iteration
            saw_data_at_time = last_iteration
            scan_start_time = last_iteration
            no_data_at_time = last_iteration
            time_from_last_iteration = 0
            scan_stop_time = scan_start_time + scan_timeout
            #data_q = []
            data_q = deque()
            raw_data_q = deque()
            current_trigger_number = 0
            last_trigger_number = 0
            while not self.stop_thread_event.wait(0.05):
                
#                 if logger.isEnabledFor(logging.DEBUG):
#                     lost_data = self.readout.get_lost_data_count()
#                     if lost_data != 0:
#                         logging.debug('Lost data count: %d', lost_data)
#                         logging.debug('FIFO fill level: %4f', (float(fifo_size)/2**20)*100)
#                         logging.debug('Collected triggers: %d', self.readout_utils.get_trigger_number())
                
                current_trigger_number = self.readout_utils.get_trigger_number()
                if (current_trigger_number%show_trigger_message_at < last_trigger_number%show_trigger_message_at):
                    logging.info('Collected triggers: %d', current_trigger_number)
                last_trigger_number = current_trigger_number
                if max_triggers is not None and current_trigger_number >= max_triggers:
                    logging.info('Reached maximum triggers. Stopping Scan...')
                    self.stop_thread_event.set()
                if scan_start_time is not None and time.time() > scan_stop_time:
                    logging.info('Reached maximum scan time. Stopping Scan...')
                    self.stop_thread_event.set()
                # TODO: read 8b10b decoder err cnt
#                 if not self.readout_utils.read_rx_status():
#                     logging.info('Lost data sync. Starting synchronization...')
#                     self.readout_utils.set_ext_cmd_start(False)
#                     if not self.readout_utils.reset_rx(1000):
#                         logging.info('Failed. Stopping scan...')
#                         self.stop_thread_event.set()
#                     else:
#                         logging.info('Done!')
#                         self.readout_utils.set_ext_cmd_start(True)
                        
                if self.stop_thread_event.is_set():
                    q_size = -1
                    while self.readout.data_queue.qsize() != q_size or self.readout.get_fifo_size() != 0:
                        time.sleep(0.5)
                        q_size = self.readout.data_queue.qsize()
                    print 'Items in queue:', q_size

                data_q.extend(list(get_all_from_queue(self.readout.data_queue))) # use list, it is faster
                time_from_last_iteration = time.time() - last_iteration
                last_iteration = time.time()
                while True:
                    try:
                        item = data_q.pop()
                    except IndexError:
                        no_data_at_time = last_iteration
                        if wait_for_first_trigger == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                            logging.info('Reached no data timeout. Stopping Scan...')
                            self.stop_thread_event.set()
                        elif wait_for_first_trigger == False:
                            saw_no_data_at_time = no_data_at_time
                        
                        if no_data_at_time > (saw_data_at_time + 10):
                            scan_stop_time += time_from_last_iteration
                              
                        break # jump out while loop
                    
                    saw_data_at_time = last_iteration
                    
                    if wait_for_first_trigger == True:
                        logging.info('Taking data...')
                        wait_for_first_trigger = False

                    raw_data = item['raw_data']
                    len_raw_data = len(raw_data)
                    #for data in split_seq(raw_data, append_size):
                    raw_data_q.extend(split_seq(raw_data, append_size))
                    while True:
                        try:
                            data = raw_data_q.pop()
                        except IndexError:
                            break
                        self.lock.acquire()
                        raw_data_earray_h5.append(data)
                        raw_data_earray_h5.flush()
                        self.lock.release()
                    row_meta['timestamp'] = item['timestamp']
                    row_meta['error'] = item['error']
                    row_meta['length'] = len_raw_data
                    row_meta['start_index'] = total_words
                    total_words += len_raw_data
                    row_meta['stop_index'] = total_words
                    self.lock.acquire()
                    row_meta.append()
                    meta_data_table_h5.flush()
                    self.lock.release()
                
            self.readout_utils.set_ext_cmd_start(False)
            self.readout_utils.set_tlu_mode(mode = 0)
            
            logging.info('Total amount of triggers collected: %d', self.readout_utils.get_trigger_number())
                
        
        self.stop_thread_event.set()
     
        logging.info('Stopping readout thread...')
        self.readout.stop()
        logging.info('Done!')

        
if __name__ == "__main__":
    import configuration
    scan = ExtTriggerScan(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start()
