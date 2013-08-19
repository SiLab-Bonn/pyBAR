""" Script to tune the GDAC to the threshold value given in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Only the pixels used in the analog injection are taken into account.
"""
from analysis.plotting.plotting import plot_occupancy
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

class GdacTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_gdac", outdir = None):
        super(GdacTune, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        self.setGdacTuneBits()
        self.setTargetThreshold()
        self.setNinjections()
        self.setAbortPrecision()
        
    def setAbortPrecision(self, delta_occupancy = 2):
        self.abort_precision = delta_occupancy    
        
    def setTargetThreshold(self, PlsrDAC = 30):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", PlsrDAC)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def setGdacBit(self, bit_position, bit_value = 1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_position < 8):
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine")|(1<<bit_position))
            else:
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine")&~(1<<bit_position))
        else:
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse")|(1<<(bit_position-8)))
            else:
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse")&~(1<<bit_position))       
        commands.extend(self.register.get_commands("wrregister", name = ["Vthin_AltFine", "Vthin_AltCoarse"]))
        self.register_utils.send_commands(commands)
        
    def setGdacTuneBits(self, GdacTuneBits = range(7,-1,-1)):
        self.GdacTuneBits = GdacTuneBits
        
    def setNinjections(self, Ninjections = 100):
        self.Ninjections = Ninjections
        
    def start(self, configure = True):
        super(GdacTune, self).start(configure)
        
        def get_cols_rows(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_rows_cols(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
        
        print 'Start readout thread...'
        self.readout.start()
        print 'Done!'
        
        for gdac_bit in self.GdacTuneBits: #reset all GDAC bits
            self.setGdacBit(gdac_bit, bit_value = 0)
            
        addedAdditionalLastBitScan = False
        lastBitResult = self.Ninjections
        
        scan_parameter = 'GDAC'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
        steps = [0]
        mask = 3      
        
        #calculate selected pixels
        select_mask_array=np.zeros(shape=(80,336),dtype=np.uint8)    
        if steps == None or steps == []:
            mask_steps = range(mask)
        else:
            mask_steps = steps   
        for mask_step in mask_steps:    
            select_mask_array += self.register_utils.make_pixel_mask(mask = mask, row_offset = mask_step)
        
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
            
            for gdac_bit in self.GdacTuneBits:
                if(not addedAdditionalLastBitScan):
                    self.setGdacBit(gdac_bit)
                else:
                    self.setGdacBit(gdac_bit, bit_value=0)
                scan_paramter_value = (self.register.get_global_register_value("Vthin_AltCoarse")<<8) + self.register.get_global_register_value("Vthin_AltFine")
                print 'GDAC setting:', scan_paramter_value," bit ",gdac_bit
                          
                repeat = self.Ninjections
                wait_cycles = 336*2/mask*24/4*3
                
                cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
                self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = steps, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                
                q_size = -1
                while self.readout.data_queue.qsize() != q_size:
                    time.sleep(0.5)
                    q_size = self.readout.data_queue.qsize()
                print 'Items in queue:', q_size

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
                
                print 'Data remaining in memory:', self.readout.get_fifo_size()
                print 'Lost data count:', self.readout.get_lost_data_count()
                
                OccupancyArray, _, _ = np.histogram2d(*zip(*get_cols_rows(data_words)), bins = (80, 336), range = [[1,80], [1,336]])
                OccArraySelPixel = OccupancyArray[select_mask_array>0]  #take only selected pixel
                median_occupancy = np.median(OccArraySelPixel)
                   
                if(gdac_bit>0 and median_occupancy < self.Ninjections/2):
                    print "median =",median_occupancy,"<",self.Ninjections/2,"set bit",gdac_bit,"= 0"
                    self.setGdacBit(gdac_bit, bit_value = 0)
                    
                if(gdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = median_occupancy
                        self.GdacTuneBits.append(0) #bit 0 has to be scanned twice
                        print "scan bit 0 now with value 0"
                    else:
                        print "scanned bit 0 = 0 with",median_occupancy," instead of ",lastBitResult
                        if(abs(median_occupancy-self.Ninjections/2)>abs(lastBitResult-self.Ninjections/2)): #if bit 0 = 0 is worse than bit 0 = 1, so go back
                            self.setGdacBit(gdac_bit, bit_value = 1)
                            print "set bit 0 = 1"   

                #plot_occupancy(*zip(*get_cols_rows(data_words)), max_occ = repeat*2, filename = None)#self.scan_data_path+".pdf")
                if(abs(median_occupancy-self.Ninjections/2) < self.abort_precision): #abort if good value already found to save time
                    print 'good result already achieved, skipping missing bits'
                    break
            
            print 'Tuned GDAC to: Vthin_AltCoarse/Vthin_AltFine', self.register.get_global_register_value("Vthin_AltCoarse"),"/", self.register.get_global_register_value("Vthin_AltFine")       
            print 'Stopping readout thread...'
            self.readout.stop()
            print 'Done!'      
        
if __name__ == "__main__":
    import scan_configuration
    scan = GdacTune(scan_configuration.config_file, bit_file = scan_configuration.bit_file, outdir = scan_configuration.outdir)
    scan.setTargetThreshold(PlsrDAC = 40)
    scan.setAbortPrecision(delta_occupancy = 2)
    scan.setGdacTuneBits(range(7,-1,-1))
    scan.start()

    
