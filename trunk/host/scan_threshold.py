import pprint
import time
import struct
import itertools

import numpy as np
import tables as tb
import BitVector

from fei4.output import FEI4Record
from daq.readout import Readout

from utils.utils import get_all_from_queue

from analysis.data_struct import MetaTable

from scan.scan import ScanBase


chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

class AnalogScan(ScanBase):
    def __init__(self, config_file, bit_file):
        super(AnalogScan, self).__init__(config_file, bit_file)
        
if __name__ == "__main__":
    scan = AnalogScan(config_file, bit_file)

    print 'Start readout thread...'
    #scan.readout.set_filter(scan.readout.data_record_filter)
    scan.readout.start()
    print 'Done!'
    
    data_words_lists = []
    
    scan_parameter = 'PlsrDAC'
    scan_paramter_value_range = range(0, 100, 1)
    
    
        
#    class ScanParameters(tb.IsDescription):
#        scan_parameter = tb.UInt32Col(pos=0)
        
    scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
    total_words = 0
    
    filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=True)
    with tb.openFile('threshold_scan.h5', mode = 'w', title = 'test file') as file_h5:
        raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data)
        meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables)
        scan_param_table_h5 = file_h5.createTable(file_h5.root, name = 'scan_parameters', description = scan_param_descr, title = 'scan_parameters', filters = filter_tables)
        
        row_meta = meta_data_table_h5.row
        row_scan_param = scan_param_table_h5.row
            
        for scan_paramter_value in scan_paramter_value_range:
            
            print 'Scan step:', scan_parameter, scan_paramter_value
            
            commands = []
            scan.register.set_global_register_value(scan_parameter, scan_paramter_value)
            commands.extend(scan.register.get_commands("wrregister", name = [scan_parameter]))
            scan.register_utils.send_commands(commands)
            
            #import cProfile
            #pr = cProfile.Profile()
            mask = 6
            repeat = 100
            wait_cycles = 336*2/mask*24/4*3
            cal_lvl1_command = scan.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+scan.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
            #pr.enable()
            scan.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = [], dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#scan.readout.read_once)
            #pr.disable()
            #pr.print_stats('cumulative')
            
            q_size = -1
            while scan.readout.data_queue.qsize() != q_size:
                time.sleep(0.5)
                q_size = scan.readout.data_queue.qsize()
            print 'Items in queue:', q_size
    
#            data_q = get_all_from_queue(scan.readout.data_queue)
#            print 'got all from queue'
#            
#            data_list = list(itertools.chain(*data_q))
#            print 'length data list:', len(data_list)

            data_q = list(get_all_from_queue(scan.readout.data_queue))
            for item in data_q:
                raw_data = item['raw_data']
#                for word in raw_data:
#                    print FEI4Record(word, 'fei4a')
                len_raw_data = len(raw_data)
                raw_data_earray_h5.append(raw_data)
                raw_data_earray_h5.flush()
                row_meta['timestamp'] = item['timestamp']
                row_meta['error'] = item['error']
                row_meta['length'] = len_raw_data
                total_words += len_raw_data
                row_meta['start_index'] = total_words-len_raw_data
                row_meta['stop_index'] = total_words
                row_meta.append()
                meta_data_table_h5.flush()
                row_scan_param[scan_parameter] = scan_paramter_value
                row_scan_param.append()
                scan_param_table_h5.flush()
            
            print 'Data remaining in memory:', scan.readout.get_fifo_size()
            print 'Lost data count:', scan.readout.get_lost_data_count()
        
        
        print 'Stopping readout thread...'
        scan.readout.stop()
        print 'Done!'
    
    def get_cols_rows(data_words):
        for item in data_words:
            yield ((item & 0xFE0000)>>17)-1, ((item & 0x1FF00)>>8)-1
            
    def get_rows_cols(data_words):
        for item in data_words:
            yield ((item & 0x1FF00)>>8)-1, ((item & 0xFE0000)>>17)-1
     
#    occupancy_plots = []
#    for data_word_list in data_words_lists:
#        #save_occupancy('scan_'+str(scan_paramter_value)+'.png', *zip(*get_cols_rows(data_words[scan_paramter_value])), max_occ = repeat*2)
#        #print str(scan_paramter_value), len(list(get_cols_rows(data_words[scan_paramter_value])))
#        dimension = (80,336)
#        occupancy_plot = np.zeros(dimension, dtype = np.uint8)
#        #print list(zip(*get_cols_rows(data_word_list)))[0]
#        for col, row in zip(*zip(*get_cols_rows(data_word_list))):
#            occupancy_plot[col][row] += 1
#        occupancy_plots.append(occupancy_plot)
#        
#    for occupancy_plot in occupancy_plots:
#        print occupancy_plot[11][80]
