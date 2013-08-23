from scan.scan import ScanBase

class DefaultScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_default", outdir = None):
        super(DefaultScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(DefaultScan, self).start(configure)
        
        print 'Starting readout thread...'
        #self.readout.set_filter(self.readout.data_record_filter)
        self.readout.start()
        print 'Done!'
        
        
        ######################################################################################
        #                                                                                    #
        #                                 Put your Code here!                                #
        #                                                                                    #
        ######################################################################################
        
         
        print 'Stopping readout thread...'
        self.readout.stop()
        print 'Done!'
        
if __name__ == "__main__":
    import scan_configuration
    scan = DefaultScan(config_file = scan_configuration.config_file, bit_file = scan_configuration.bit_file, outdir = scan_configuration.outdir)
    scan.start()
