import itertools
import struct
import time
import datetime

#import numpy
import numpy as np
#import pandas as pd
import tables as tb
#from tables import *
#from tables import atom

from fei4.output import FEI4Record
from daq.readout import Readout
from utils.utils import get_iso_time

from utils.utils import get_all_from_queue

from analysis.data_struct import MetaTable

from scan.scan import ScanBase

chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

class ExtTriggerScan(ScanBase):
    def __init__(self, config_file, bit_file):
        super(ExtTriggerScan, self).__init__(config_file, bit_file)


if __name__ == "__main__":
    scan = ExtTriggerScan(config_file, bit_file)
    
    print 'Start readout thread...'
    #readout_thread.set_filter(readout_thread.data_record_filter)
    scan.readout.start()
    print 'Done!'
    
    #scan_parameter = 'Vthin_AltFine'
    #scan_paramter_value = scan.register.get_global_register_value(scan_parameter)
    
    filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=True)
    with tb.openFile('ext_trigger_scan.h5', mode = 'w', title = 'test file') as file_h5:
        raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data)
        meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables)
        
        lvl1_command = scan.register.get_commands("lv1")[0]
        scan.register_utils.set_command(lvl1_command)
        scan.readout_utils.set_tlu_mode(mode = 1)
        scan.readout_utils.set_ext_cmd_start(True)
            
        consecutive_lvl1 = scan.register.get_global_register_value("Trig_Count")
        if consecutive_lvl1 == 0:
            consecutive_lvl1 = 16
        total_triggers = 0
        readout_counter = 0
        dh_count = 0
        unknown_count = 0
        
        total_words = 0
        
        row_meta = meta_data_table_h5.row
        
        wait_for_first_trigger = True
        while 1:
            fifo_size = scan.readout.get_fifo_size()
            if fifo_size:
                print 'FIFO Fill Level:', (float(fifo_size)/2**20)*100
                
            lost_data = scan.readout.get_lost_data_count()
            if lost_data:
                print 'Lost data count:', lost_data
            

            
            #data_q = get_all_from_queue(scan.readout.data_queue)
            #data_list = list(itertools.chain(*data_q))
            data_q = list(get_all_from_queue(scan.readout.data_queue))
            if len(data_q) == 0 and fifo_size != 0:
                continue
            elif len(data_q) == 0 and fifo_size == 0:
                if wait_for_first_trigger == False:
                    break
            else:
                wait_for_first_trigger = False
                readout_counter += 1
                for item in data_q:
                    raw_data = item['raw_data']
                    len_raw_data = len(raw_data)
                    raw_data_earray_h5.append(raw_data)
                    #raw_data_earray_h5.flush()
                    row_meta['timestamp'] = item['timestamp']
                    row_meta['error'] = item['error']
                    row_meta['length'] = len_raw_data
                    row_meta['start_index'] = total_words
                    total_words += len_raw_data
                    row_meta['start_index'] = total_words
                    row_meta['stop_index'] = total_words
                    row_meta.append()
                    #meta_data_table_h5.flush()
                raw_data_earray_h5.flush()
                meta_data_table_h5.flush()
                    
                
#                carray_h5 = file_h5.createCArray(file_h5.root, name = 'raw_data_'+str(readout_counter), atom = tb.UIntAtom(), shape = (len(data_list),), title = str(get_iso_time()), filters = filters)
#                carray_h5[:] = data_list
#                carray_h5.flush()
                
    
    #        for data_word in data_list:
    #            record = FEI4Record(data_word, chip_flavor)
    #            print record
    #            if record == "DH":
    #            #header = struct.unpack(4*'B', struct.pack('I', data_word))[2]
    #            #if header == 233:
    #                dh_count +=1
    #                if dh_count == consecutive_lvl1:
    #                    dh_count = 0
    #                    total_triggers += 1
    #                    if total_triggers%10000 == 0:
    #                        print total_triggers
    
        #        elif record == "UNKNOWN":
        #            unknown_count += 1
        #            print 'unknown:', unknown_count
        
 
    print 'Stopping readout thread...'
    scan.readout.stop()
    print 'Done!'
    
    print 'Data remaining in memory:', scan.readout.get_fifo_size()
    print 'Lost data count:', scan.readout.get_lost_data_count()
