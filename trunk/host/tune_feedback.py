""" Script to tune the feedback current to the charge@TOT. Charge in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Only the pixels used in the analog injection are taken into account.
"""
from analysis.plotting.plotting import plot_tot
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

class FeedbackTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_feedback", outdir = None):
        super(FeedbackTune, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        self.setFeedbackTuneBits()
        self.setTargetCharge()
        self.setTargetTot()
        self.setNinjections()
        self.setAbortPrecision()
        
    def setTargetCharge(self, PlsrDAC = 30):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", PlsrDAC)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def setTargetTot(self, Tot = 5):
        self.TargetTot = Tot
        
    def setAbortPrecision(self, delta_tot = 0.1):
        self.abort_precision = delta_tot
        
    def setPrmpVbpfBit(self, bit_position, bit_value = 1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_value == 1):
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf")|(1<<bit_position))
        else:
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf")&~(1<<bit_position))
        commands.extend(self.register.get_commands("wrregister", name = ["PrmpVbpf"]))
        self.register_utils.send_commands(commands)
        
    def setFeedbackTuneBits(self, FeedbackTuneBits = range(7,-1,-1)):
        self.FeedbackTuneBits = FeedbackTuneBits
        
    def setNinjections(self, Ninjections = 100):
        self.Ninjections = Ninjections
        
    def start(self, configure = True):
        super(FeedbackTune, self).start(configure)
        
        def get_cols_rows(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_rows_cols(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
                
        def get_tot(data_words):
            for item in self.readout.data_record_filter(data_words):
                yield ((item & 0x000F0)>>4)
        
        for PrmpVbpf_bit in self.FeedbackTuneBits: #reset all GDAC bits
            self.setPrmpVbpfBit(PrmpVbpf_bit, bit_value = 0)
            
        addedAdditionalLastBitScan = False
        lastBitResult = self.Ninjections
        
        scan_parameter = 'PrmpVbpf'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
        steps = [0]
        mask = 3      
        
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
            
            for PrmpVbpf_bit in self.FeedbackTuneBits:
                print 'Starting readout thread...'
                self.readout.start()
                print 'Done!'
                
                if(not addedAdditionalLastBitScan):
                    self.setPrmpVbpfBit(PrmpVbpf_bit)
                else:
                    self.setPrmpVbpfBit(PrmpVbpf_bit, bit_value=0)
                scan_paramter_value = self.register.get_global_register_value("PrmpVbpf")
                print 'PrmpVbpf setting:', scan_paramter_value," bit ",PrmpVbpf_bit
                          
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
                
                tots = [tot for tot in get_tot(data_words)]
                mean_tot=np.mean(tots)
                print "TOT mean =", mean_tot
                   
                if(PrmpVbpf_bit>0 and mean_tot < self.TargetTot):
                    print "mean =",mean_tot,"<",self.TargetTot,"TOT, set bit",PrmpVbpf_bit,"= 0"
                    self.setPrmpVbpfBit(PrmpVbpf_bit, bit_value = 0)
                      
                if(PrmpVbpf_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = mean_tot
                        self.FeedbackTuneBits.append(0) #bit 0 has to be scanned twice
                        print "scan bit 0 now with value 0"
                    else:
                        print "scanned bit 0 = 0 with",mean_tot," instead of ",lastBitResult
                        if(abs(mean_tot-self.TargetTot)>abs(lastBitResult-self.TargetTot)): #if bit 0 = 0 is worse than bit 0 = 1, so go back
                            self.setPrmpVbpfBit(PrmpVbpf_bit, bit_value = 1)
                            print "set bit 0 = 1"   

#                 TotArray, _ = np.histogram(a = tots, range = (0,16), bins = 16)
#                 plot_tot(tot_hist = TotArray, filename = None)#self.scan_data_path+".pdf")
                
                if(abs(mean_tot-self.TargetTot) < self.abort_precision): #abort if good value already found to save time
                    print 'good result already achieved, skipping missing bits'
                    break
            
            print 'Tuned PrmpVbpf to: ',self.register.get_global_register_value("PrmpVbpf")
            return self.register.get_global_register_value("PrmpVbpf")
        
if __name__ == "__main__":
    import configuration
    scan = FeedbackTune(config_file = configuration.config_file, bit_file = configuration.bit_file, outdir = configuration.outdir)
    scan.setTargetCharge(PlsrDAC = 250)
    scan.setTargetTot(Tot = 5)
    scan.setAbortPrecision(delta_tot = 0.1)
    scan.setFeedbackTuneBits(range(7,-1,-1))
    scan.start()
