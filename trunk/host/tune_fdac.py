""" Script to tune the Fdac to the feedback current given as charge@TOT. Charge in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Pixel below threshold get TOT = 0.
"""
import tables as tb
import numpy as np
import BitVector
import logging

from daq.readout import open_raw_data_file, get_col_row_tot_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plotThreeWay
from scan.scan import ScanBase

class FdacTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_fdac", scan_data_path = None):
        super(FdacTune, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        self.set_target_charge()
        self.set_target_tot()
        self.set_n_injections()
        self.set_fdac_tune_bits()
        
    def set_target_charge(self, plsr_dac = 30):
        self.target_charge = plsr_dac
        
    def write_target_charge(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", self.target_charge)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def set_target_tot(self, tot = 5):
        self.TargetTot = tot
        
    def set_fdac_bit(self, bit_position, bit_value = 1):
        if(bit_value == 1):
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac")|(1<<bit_position))
        else:
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac")&~(1<<bit_position))      
          
    def write_fdac_config(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = ["Fdac"]))
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)
        
    def set_fdac_tune_bits(self, FdacTuneBits = range(3,-1,-1)):
        self.FdacTuneBits = FdacTuneBits
        
    def set_start_fdac(self):
        start_fdac_setting = self.register.get_pixel_register_value("FDAC")
        for bit_position in self.FdacTuneBits: #reset all TDAC bits, FIXME: speed up
            start_fdac_setting = start_fdac_setting&~(1<<bit_position)
        self.register.set_pixel_register_value("FDAC",start_fdac_setting)
        
    def set_n_injections(self, Ninjections = 20):
        self.Ninjections = Ninjections
        
    def scan(self, configure = True):
        self.write_target_charge()
        self.set_start_fdac()
        
        addedAdditionalLastBitScan = False
        lastBitResult = np.zeros(shape = self.register.get_pixel_register_value("Fdac").shape, dtype = self.register.get_pixel_register_value("Fdac").dtype)
        
        mask = 3
        mask_steps = []
        
        scan_parameter = 'Fdac'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}

        with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:            
            Fdac_mask = []
            
            for index, Fdac_bit in enumerate(self.FdacTuneBits):
                if(not addedAdditionalLastBitScan):
                    self.set_fdac_bit(Fdac_bit)
                    logging.info('FDAC setting: bit %d = 1' % Fdac_bit)
                else:
                    self.set_fdac_bit(Fdac_bit, bit_value=0)
                    logging.info('FDAC setting: bit %d = 0' % Fdac_bit)
                    
                self.write_fdac_config()
                self.readout.start()
                scan_paramter_value = index
                
                repeat = self.Ninjections
                wait_cycles = 336*2/mask*24/4*3
                
                cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
                self.scan_loop(cal_lvl1_command, repeat = repeat, mask = mask, mask_steps = mask_steps, double_columns = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                
                self.readout.stop()

                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_paramter_value})

                col_row_tot = np.column_stack(get_col_row_tot_array_from_data_record_array(convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)))))
                TotArray = np.histogramdd(col_row_tot, bins = (80, 336, 16), range = [[1,80], [1,336], [0,15]])[0]
                TotAvrArray = np.average(TotArray,axis = 2, weights=range(0,16))*sum(range(0,16))/self.Ninjections
                plotThreeWay(hist = TotAvrArray.transpose(), title = "TOT mean", x_axis_title = 'mean TOT', filename = None)
            
                Fdac_mask=self.register.get_pixel_register_value("Fdac")
                if(Fdac_bit>0):
                    Fdac_mask[TotAvrArray<self.TargetTot] = Fdac_mask[TotAvrArray<self.TargetTot]&~(1<<Fdac_bit)
                    self.register.set_pixel_register_value("Fdac", Fdac_mask)
                    
                if(Fdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = TotAvrArray
                        self.FdacTuneBits.append(0) #bit 0 has to be scanned twice
                    else:
                        Fdac_mask[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)] = Fdac_mask[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)]|(1<<Fdac_bit)
                        TotAvrArray[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)] = lastBitResult[abs(TotAvrArray-self.TargetTot)>abs(lastBitResult-self.TargetTot)]
            
            self.register.set_pixel_register_value("Fdac", Fdac_mask)
            plotThreeWay(hist = TotAvrArray.transpose(), title = "TOT average final", label = "TOT average")
            plotThreeWay(hist = self.register.get_pixel_register_value("FDAC").transpose(), title = "FDAC distribution final", label = "FDAC")
            logging.info('Tuned Fdac!')
        
if __name__ == "__main__":
    import configuration
    #scan = FdacTune(configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan = FdacTune(config_file = configuration.config_file, bit_file = None, scan_data_path = configuration.scan_data_path)
    scan.set_target_charge(plsr_dac = 280)
    scan.set_target_tot(tot = 5)
    scan.set_n_injections(30)
    scan.set_fdac_tune_bits(range(3,-1,-1))
    scan.start(use_thread = False)
    scan.stop()
    scan.register.save_configuration(configuration.config_file)
