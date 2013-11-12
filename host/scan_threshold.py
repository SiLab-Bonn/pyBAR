from daq.readout import open_raw_data_file
from scan.scan import ScanBase
from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class ThresholdScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_threshold", scan_data_path = None):
        super(ThresholdScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def scan(self, configure = True, mask = 3, repeat = 100, steps = []):
        scan_parameter = 'PlsrDAC'
        scan_paramter_value_range = range(0, 101, 1)
        
        with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:
            
            for scan_paramter_value in scan_paramter_value_range:
                logging.info('Scan step: %s %d' % (scan_parameter, scan_paramter_value))
                
                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(scan_parameter, scan_paramter_value)
                commands.extend(self.register.get_commands("wrregister", name = [scan_parameter]))
                self.register_utils.send_commands(commands)
                
                self.readout.start()
                
                cal_lvl1_command = self.register.get_commands("cal")[0]+self.register.get_commands("zeros", length=40)[0]+self.register.get_commands("lv1")[0]+self.register.get_commands("zeros", mask_steps=mask)[0]
                self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = mask, steps = [], dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = False, read_function = None)#self.readout.read_once)
                
                self.readout.stop(timeout=10)
                
                # saving data
                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_paramter_value})
                
    def analyze(self):
        with AnalyzeRawData(input_file = scan.scan_data_filename+".h5", output_file = output_file) as analyze_raw_data:
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(FEI4B = scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename = scan.scan_data_filename)
        
if __name__ == "__main__":
    import configuration
    scan = ThresholdScan(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start(use_thread = False)
    scan.stop()
    scan.analyze()
