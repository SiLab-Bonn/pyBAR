""" Script to tune the feedback current to the charge@TOT. Charge in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Only the pixels used in the analog injection are taken into account.
"""
import tables as tb
import numpy as np
import BitVector
import logging

from daq.readout import open_raw_data_file, get_tot_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plot_tot
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class FeedbackTune(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "tune_feedback", scan_data_path = None):
        super(FeedbackTune, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        self.set_target_charge()
        self.set_target_tot()
        self.set_n_injections()
        self.set_feedback_tune_bits()
        self.set_abort_precision()
        
    def set_target_charge(self, plsr_dac = 250):
        self.target_charge = plsr_dac
        
    def write_target_charge(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", self.target_charge)
        commands.extend(self.register.get_commands("wrregister", name = "PlsrDAC"))
        self.register_utils.send_commands(commands)
        
    def set_target_tot(self, Tot = 5):
        self.TargetTot = Tot
        
    def set_abort_precision(self, delta_tot = 0.1):
        self.abort_precision = delta_tot
        
    def set_prmp_vbpf_bit(self, bit_position, bit_value = 1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_value == 1):
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf")|(1<<bit_position))
        else:
            self.register.set_global_register_value("PrmpVbpf", self.register.get_global_register_value("PrmpVbpf")&~(1<<bit_position))
        commands.extend(self.register.get_commands("wrregister", name = ["PrmpVbpf"]))
        self.register_utils.send_commands(commands)
        
    def set_feedback_tune_bits(self, FeedbackTuneBits = range(7,-1,-1)):
        self.FeedbackTuneBits = FeedbackTuneBits
        
    def set_n_injections(self, Ninjections = 100):
        self.Ninjections = Ninjections
        
    def scan(self, configure = True):       
        self.write_target_charge()
        
        for PrmpVbpf_bit in self.FeedbackTuneBits: #reset all GDAC bits
            self.set_prmp_vbpf_bit(PrmpVbpf_bit, bit_value = 0)
            
        addedAdditionalLastBitScan = False
        lastBitResult = self.Ninjections
        
        steps = [0]
        mask = 3
        
        scan_parameter = 'PrmpVbpf'
        scan_param_descr = {scan_parameter:tb.UInt32Col(pos=0)}
        
        with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:            
            for PrmpVbpf_bit in self.FeedbackTuneBits:                                
                if(not addedAdditionalLastBitScan):
                    self.set_prmp_vbpf_bit(PrmpVbpf_bit)
                    logging.info('PrmpVbpf setting: %d, bit %d = 1' % (self.register.get_global_register_value("PrmpVbpf"),PrmpVbpf_bit))
                else:
                    self.set_prmp_vbpf_bit(PrmpVbpf_bit, bit_value=0)
                    logging.info('PrmpVbpf setting: %d, bit %d = 0' % (self.register.get_global_register_value("PrmpVbpf"),PrmpVbpf_bit))
                          
                scan_paramter_value = self.register.get_global_register_value("PrmpVbpf")
                
                self.readout.start()
                repeat = self.Ninjections
                wait_cycles = 336*2/mask*24/4*3
                
                cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 40)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = wait_cycles)
                self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = steps, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                
                self.readout.stop()
                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_paramter_value})
                
                tots = get_tot_array_from_data_record_array(convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4))))
                mean_tot=np.mean(tots)
                
                logging.info('TOT mean = %f' % mean_tot)
                   
                if(PrmpVbpf_bit>0 and mean_tot < self.TargetTot):
                    self.set_prmp_vbpf_bit(PrmpVbpf_bit, bit_value = 0)
                    logging.info('mean = %f < %d TOT, set bit %d = 0' % (mean_tot,self.TargetTot,PrmpVbpf_bit))
                      
                if(PrmpVbpf_bit == 0):
                    if not(addedAdditionalLastBitScan):  #scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan=True
                        lastBitResult = mean_tot
                        self.FeedbackTuneBits.append(0) #bit 0 has to be scanned twice
                    else:
                        logging.info('scanned bit 0 = 0 with %f instead of %f for scanned bit 0 = 1' % (mean_tot,lastBitResult))
                        if(abs(mean_tot-self.TargetTot)>abs(lastBitResult-self.TargetTot)): #if bit 0 = 0 is worse than bit 0 = 1, so go back
                            self.set_prmp_vbpf_bit(PrmpVbpf_bit, bit_value = 1)
                            mean_tot = lastBitResult
                            logging.info('set bit 0 = 1')
                        else:
                            logging.info('set bit 0 = 0')

                TotArray, _ = np.histogram(a = tots, range = (0,16), bins = 16)
#                 plot_tot(tot_hist = TotArray, filename = None)#self.scan_data_filename+".pdf")
                
                if(abs(mean_tot-self.TargetTot) < self.abort_precision): #abort if good value already found to save time
                    logging.info('good result already achieved, skipping missing bits')  
                    break
            
            if(abs(mean_tot-self.TargetTot) > 2 * self.abort_precision):
                logging.warning('Tuning of PrmpVbpf to %d tot failed. Difference = %f tot. PrmpVbpf = %d' % (self.TargetTot, abs(mean_tot-self.TargetTot), self.register.get_global_register_value("PrmpVbpf")))
            else:
                logging.info('Tuned PrmpVbpf to %d' % self.register.get_global_register_value("PrmpVbpf"))
            
            plot_tot(tot_hist = TotArray, filename = None)
        
if __name__ == "__main__":
    import configuration
    scan = FeedbackTune(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.set_n_injections(100)
    scan.set_target_charge(plsr_dac = 270)
    scan.set_target_tot(Tot = 5)
    scan.set_abort_precision(delta_tot = 0.1)
    scan.set_feedback_tune_bits(range(7,-1,-1))
    scan.start(use_thread = False)
    scan.stop()
    scan.register.save_configuration(configuration.config_file)
