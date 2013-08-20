from analysis.plotting.plotting import plot_occupancy

import logging

import BitVector

from fei4.output import FEI4Record

from scan.scan import ScanBase

class DefaultScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_default", outdir = None):
        super(DefaultScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(DefaultScan, self).start(configure)
        
        print 'Start readout thread...'
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
         
        print 'Data remaining in memory:', self.readout.get_fifo_size()
        print 'Lost data count:', self.readout.get_lost_data_count()
        
        
if __name__ == "__main__":
    import scan_configuration
    scan = DefaultScan(config_file = scan_configuration.config_file, bit_file = scan_configuration.bit_file, outdir = scan_configuration.outdir)
    scan.start()
