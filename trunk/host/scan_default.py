from scan.scan import ScanBase

class DefaultScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_default", scan_data_path = None):
        super(DefaultScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def start(self, configure = True):
        super(DefaultScan, self).start(configure)
        
        self.readout.start()
        
        ######################################################################################
        #                                                                                    #
        #                                 Put your code here!                                #
        #                                                                                    #
        ######################################################################################
         
        self.readout.stop()
        
if __name__ == "__main__":
    import configuration
    scan = DefaultScan(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start()
