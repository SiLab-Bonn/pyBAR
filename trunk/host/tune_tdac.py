""" Script to tune the Tdac to the threshold value given in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
"""
from analysis.plotting.plotting import plot_occupancy, create_2d_pixel_hist, plot_pixel_dac_config, plotThreeWay
import time
import itertools
import matplotlib.pyplot as plt

import tables as tb
import numpy as np
import BitVector

from analysis.data_struct import MetaTable

from utils.utils import get_all_from_queue, split_seq
from collections import deque

from scan.scan import ScanBase

class TdacTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_Tdac", outdir = None):
        super(TdacTune, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        self.setTdacTuneBits()
        self.setTargetThreshold()
        self.setNinjections()
        
    def saveTdacConfig(self):
        self.register.save_configuration()
        
    def setTargetThreshold(self, PlsrDAC = 30):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", PlsrDAC)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def setTdacBit(self, bit_position, bit_value = 1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_value == 1):
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC")|(1<<bit_position))
        else:
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC")&~(1<<bit_position))      
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = ["TDAC"]))
        self.register_utils.send_commands(commands)
        
    def setStartTdac(self):
        commands = []
        start_tdac_setting = self.register.get_pixel_register_value("TDAC")
        for bit_position in self.TdacTuneBits: #reset all TDAC bits, FIXME: speed up
            start_tdac_setting = start_tdac_setting&~(1<<bit_position)
        self.register.set_pixel_register_value("TDAC",start_tdac_setting)
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = True, name = ["TDAC"]))
        self.register_utils.send_commands(commands)
        
    def setTdacTuneBits(self, TdacTuneBits = range(4,-1,-1)):
        self.TdacTuneBits = TdacTuneBits
        
    def setNinjections(self, Ninjections = 100):
        self.Ninjections = Ninjections
        
    def start(self, configure = True):
        super(TdacTune, self).start(configure)
        
        def get_cols_rows(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_rows_cols(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
        
        addedAdditionalLastBitScan = False
        lastBitResult = np.zeros(shape = self.register.get_pixel_register_value("TDAC").shape, dtype = self.register.get_pixel_register_value("TDAC").dtype)
        
        scan_parameter = 'Tdac'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
        self.setStartTdac();
       
        mask = 3
        steps = []
               
        data_q = deque()
        raw_data_q = deque()
            
        total_words = 0
        append_size = 50000
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        print "Out file",self.scan_data_path+".h5"
        with tb.openFile(self.scan_data_path+".h5", mode = 'w', title = 'first data') as file_h5:
            raw_data_earray_h5 = file_h5.createEArray(file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data, expectedrows = append_size)
            meta_data_table_h5 = file_h5.createTable(file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables, expectedrows = 10)
            scan_param_table_h5 = file_h5.createTable(file_h5.root, name = 'scan_parameters', description = scan_param_descr, title = 'scan_parameters', filters = filter_tables, expectedrows = 10)
            
            row_meta = meta_data_table_h5.row
            row_scan_param = scan_param_table_h5.row
            
            tdac_mask = []
            
            for index, Tdac_bit in enumerate(self.TdacTuneBits):
                print 'Starting readout thread...'
                self.readout.start()
                print 'Done!'
                
                if(not addedAdditionalLastBitScan):
                    self.setTdacBit(Tdac_bit)
                else:
                    self.setTdacBit(Tdac_bit, bit_value=0)
                scan_paramter_value = index
                print 'Tdac setting: bit ',Tdac_bit
                          
                repeat = self.Ninjections
                wait_cycles = 336*2/mask*24/4*3
                
                cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
                self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = steps, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                
                print 'Stopping readout thread...'
                self.readout.stop()
                print 'Done!'

                data_q.extend(list(get_all_from_queue(self.readout.data_queue))) # use list, it is faster
                data_words = itertools.chain(*(data_dict['raw_data'] for data_dict in data_q))
                            
                while True:
                    try:
                        item = data_q.pop()
                    except IndexError:
                        break # jump out while loop
                    
                    raw_data = item['raw_data']
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
                
                OccupancyArray, _, _ = np.histogram2d(*zip(*get_cols_rows(data_words)), bins = (80, 336), range = [[1,80], [1,336]])
#                 plotThreeWay(hist = OccupancyArray.transpose(), title = "Occupancy")
                
                tdac_mask=self.register.get_pixel_register_value("TDAC")
                if(Tdac_bit>0):
                    tdac_mask[OccupancyArray>self.Ninjections/2] = tdac_mask[OccupancyArray>self.Ninjections/2]&~(1<<Tdac_bit)
                    self.register.set_pixel_register_value("TDAC", tdac_mask)
                    
                if(Tdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = OccupancyArray
                        self.TdacTuneBits.append(0) #bit 0 has to be scanned twice
                        print "scan bit 0 now with value 0"
                    else:
                        print "scanned bit 0 = 0"
                        tdac_mask[abs(OccupancyArray-self.Ninjections/2)>abs(lastBitResult-self.Ninjections/2)] = tdac_mask[abs(OccupancyArray-self.Ninjections/2)>abs(lastBitResult-self.Ninjections/2)]|(1<<Tdac_bit)
                        OccupancyArray[abs(OccupancyArray-self.Ninjections/2)>abs(lastBitResult-self.Ninjections/2)] = lastBitResult[abs(OccupancyArray-self.Ninjections/2)>abs(lastBitResult-self.Ninjections/2)]   
            
            self.register.set_pixel_register_value("TDAC", tdac_mask)
            plotThreeWay(hist = OccupancyArray.transpose(), title = "Occupancy final")
#             plotThreeWay(hist = self.register.get_pixel_register_value("TDAC").transpose(), title = "TDAC distribution final")
            print "Tuned Tdac!"
            return OccupancyArray
        
if __name__ == "__main__":
    import configuration
    scan = TdacTune(config_file = configuration.config_file, bit_file = configuration.bit_file, outdir = configuration.outdir)
    scan.setNinjections(100) 
    scan.setTargetThreshold(PlsrDAC = 40)
    scan.setTdacTuneBits(range(4,-1,-1))
    scan.start()
