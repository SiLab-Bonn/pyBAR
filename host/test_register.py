from scan.scan import ScanBase

class TestRegisters(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "test_register", outdir = None):
        super(TestRegisters, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)

    def start(self, configure = True):
        super(TestRegisters, self).start(configure)
        
#         number_of_errors = scan.register_utils.test_global_register()
#         print 'Global Register Test: Found', number_of_errors, "error(s)"
        
        #number_of_errors = scan.register_utils.test_pixel_register()
        #print 'Pixel Register Test: Found', number_of_errors, "error(s)"
        
        sn = scan.register_utils.read_chip_sn()
        print "Chip S/N:", sn
        
        print 'Reset SRAM FIFO...'
        scan.readout_utils.reset_sram_fifo()
        print 'Done!'

if __name__ == "__main__":
    chip_flavor = 'fei4b'
    config_file = r'C:\pyats\trunk\host\config\fei4default\configs\plsr_cfg_'+chip_flavor+'.cfg'
    bit_file = r'C:\pyats\trunk\host\config\FPGA\top.bit'
    
    scan = TestRegisters(config_file = config_file, bit_file = bit_file)
    
    scan.start()

    