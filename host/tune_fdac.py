""" Script to tune the Fdac to the feedback current given as charge@TOT. Charge in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Pixel below threshold get TOT = 0.
"""
from analysis.plotting.plotting import plot_occupancy, create_2d_pixel_hist, plot_pixel_dac_config, plotOccupancy, plotThreeWay
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

class FdacTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_Fdac", outdir = None):
        super(FdacTune, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        self.setFdacTuneBits()
        self.setTargetTot()
        self.setTargetCharge()
        self.setNinjections()
        
    def setTargetCharge(self, PlsrDAC = 30):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", PlsrDAC)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def setTargetTot(self, Tot = 5):
        self.TargetTot = Tot
        
    def setFdacBit(self, bit_position, bit_value = 1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_value == 1):
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac")|(1<<bit_position))
        else:
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac")&~(1<<bit_position))      
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = ["Fdac"]))
        self.register_utils.send_commands(commands)
        
    def setFdacTuneBits(self, FdacTuneBits = range(7,-1,-1)):
        self.FdacTuneBits = FdacTuneBits
        
    def setStartFdac(self):
        commands = []
        start_fdac_setting = self.register.get_pixel_register_value("FDAC")
        for bit_position in self.FdacTuneBits: #reset all TDAC bits, FIXME: speed up
            start_fdac_setting = start_fdac_setting&~(1<<bit_position)
        self.register.set_pixel_register_value("FDAC",start_fdac_setting)
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = True, name = ["FDAC"]))
        self.register_utils.send_commands(commands)
        
    def setNinjections(self, Ninjections = 20):
        self.Ninjections = Ninjections
        
    def start(self, configure = True):
        super(FdacTune, self).start(configure)
        
        def get_cols_rows(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_cols_rows_tot(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield [((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8), ((item & 0x000F0)>>4)]
        
        def get_cols_rows_tot_test(data_words):
            ret = [] 
            for item in self.readout.data_record_filter(data_words):
                ret.append((((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8), ((item & 0x000F0)>>4)))
            return ret
                
        def get_rows_cols(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
        
        print 'Start readout thread...'
        self.readout.start()
        print 'Done!'
        
        self.setStartFdac()
            
        addedAdditionalLastBitScan = False
        lastBitResult = np.zeros(shape = self.register.get_pixel_register_value("Fdac").shape, dtype = self.register.get_pixel_register_value("Fdac").dtype)
        
        scan_parameter = 'Fdac'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
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
            
            Fdac_mask = []
            
            for index, Fdac_bit in enumerate(self.FdacTuneBits):
                if(not addedAdditionalLastBitScan):
                    self.setFdacBit(Fdac_bit)
                else:
                    self.setFdacBit(Fdac_bit, bit_value=0)
                scan_paramter_value = index
                print 'Fdac setting: bit ',Fdac_bit
                          
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

                TotArray = np.histogramdd(np.array(list(get_cols_rows_tot(data_words))), bins = (80, 336, 16), range = [[1,80], [1,336], [0,15]])[0]
                TotAvrArray = np.average(TotArray,axis = 2, weights=range(0,16))*sum(range(0,16))/self.Ninjections
                #plotThreeWay(hist = TotAvrArray.transpose(), title = "TOT mean", label = 'mean TOT', filename = None)
                
                Fdac_mask=self.register.get_pixel_register_value("Fdac")
                if(Fdac_bit>0):
                    Fdac_mask[TotAvrArray<self.TargetTot] = Fdac_mask[TotAvrArray<self.TargetTot]&~(1<<Fdac_bit)
                    self.register.set_pixel_register_value("Fdac", Fdac_mask)
                    
                if(Fdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = TotAvrArray
                        self.FdacTuneBits.append(0) #bit 0 has to be scanned twice
                        print "scan bit 0 now with value 0"
                    else:
                        print "scanned bit 0 = 0"
                        Fdac_mask[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)] = Fdac_mask[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)]|(1<<Fdac_bit)
                        TotAvrArray[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)] = lastBitResult[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)] 
            
            self.register.set_pixel_register_value("Fdac", Fdac_mask)
#             plotThreeWay(hist = TotAvrArray.transpose(), title = "TOT average final")
#             plotThreeWay(hist = self.register.get_pixel_register_value("FDAC").transpose(), title = "FDAC distribution final")
            print "Tuned Fdac!"
            print 'Stopping readout thread...'
            self.readout.stop()
            print 'Done!'
            return TotAvrArray      
        
if __name__ == "__main__":
    import scan_configuration
    #scan = FdacTune(scan_configuration.config_file, bit_file = scan_configuration.bit_file, outdir = scan_configuration.outdir)
    scan = FdacTune(scan_configuration.config_file, bit_file = None, outdir = scan_configuration.outdir)
    scan.setTargetCharge(PlsrDAC = 300)
    scan.setTargetTot(Tot = 5)
    scan.setNinjections(30)
    scan.setFdacTuneBits(range(3,-1,-1))
    scan.start()
